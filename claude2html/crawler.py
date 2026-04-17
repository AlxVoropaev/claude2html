"""Crawl external links from Claude chats to local readable copies."""

from __future__ import annotations

import hashlib
import json
import random
import re
import sys
import threading
import time
import urllib.request
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Callable, Iterable
from urllib.parse import urljoin, urlparse

DEFAULT_BLACKLIST = frozenset({"reddit.com", "youtube.com", "youtu.be"})

_URL_RE = re.compile(r"""https?://[^\s<>"'\)\]]+""")
_TRAILING_PUNCT = ".,);:!?\"'"
_IMG_MD_RE = re.compile(r"!\[([^\]]*)\]\(([^)]+)\)")

_ARXIV_HOSTS = frozenset({"arxiv.org", "www.arxiv.org"})
_ARXIV_PATH_RE = re.compile(r"^/(abs|pdf|html)/([^/?#]+?)(?:\.pdf)?/?$")
_ARXIV_VER_RE = re.compile(r"v\d+$")
_ARXIV_API_URL = "https://export.arxiv.org/api/query?id_list={ids}&max_results={n}"
_ARXIV_PDF_URL = "https://arxiv.org/pdf/{aid}"
_ARXIV_API_BATCH = 100
_ATOM_NS = {"atom": "http://www.w3.org/2005/Atom"}
_FNAME_BAD_RE = re.compile(r'[<>:"/\\|?*\x00-\x1f]+')


def url_hash(url: str) -> str:
    return hashlib.sha256(url.encode("utf-8")).hexdigest()[:16]


def _host(url: str) -> str:
    return (urlparse(url).hostname or "").lower()


def is_blacklisted(url: str, blacklist: Iterable[str] = DEFAULT_BLACKLIST) -> bool:
    h = _host(url)
    return any(h == b or h.endswith("." + b) for b in blacklist)


def _extract_urls(text: str) -> list[str]:
    out: list[str] = []
    for m in _URL_RE.finditer(text or ""):
        u = m.group(0).rstrip(_TRAILING_PUNCT)
        if u:
            out.append(u)
    return out


def collect_urls(convs: list[dict]) -> set[str]:
    """URLs from message `text` blocks and artifact `content`. Skips md_citations."""
    urls: set[str] = set()
    for conv in convs:
        for msg in conv.get("chat_messages") or []:
            for block in msg.get("content") or []:
                btype = block.get("type")
                name = block.get("name")
                if btype == "text":
                    urls.update(_extract_urls(block.get("text", "")))
                elif btype == "tool_use" and name == "artifacts":
                    content = (block.get("input") or {}).get("content") or ""
                    urls.update(_extract_urls(content))
    return urls


def _arxiv_id(url: str) -> str | None:
    """Return the version-less arxiv ID for abs/pdf/html URLs, else None."""
    p = urlparse(url)
    if (p.hostname or "").lower() not in _ARXIV_HOSTS:
        return None
    m = _ARXIV_PATH_RE.match(p.path)
    if not m:
        return None
    return _ARXIV_VER_RE.sub("", m.group(2))


def _sanitize_filename(s: str, max_len: int = 120) -> str:
    s = _FNAME_BAD_RE.sub(" ", s).strip().strip(".")
    s = " ".join(s.split())
    if len(s) > max_len:
        s = s[:max_len].rstrip()
    return s or "untitled"


def _parse_arxiv_titles(xml: bytes) -> dict[str, str]:
    """Parse an arxiv Atom response into {id: title}. Strips version suffixes."""
    out: dict[str, str] = {}
    root = ET.fromstring(xml)
    for entry in root.findall("atom:entry", _ATOM_NS):
        id_url = entry.findtext("atom:id", default="", namespaces=_ATOM_NS)
        m = _ARXIV_PATH_RE.match(urlparse(id_url).path)
        if not m:
            continue
        aid = _ARXIV_VER_RE.sub("", m.group(2))
        title = " ".join(
            entry.findtext("atom:title", default="", namespaces=_ATOM_NS).split()
        )
        if aid and title:
            out[aid] = title
    return out


def _default_arxiv_titles(ids: list[str]) -> dict[str, str]:
    """Batch-fetch arxiv titles via one API call per ``_ARXIV_API_BATCH`` IDs."""
    out: dict[str, str] = {}
    for i in range(0, len(ids), _ARXIV_API_BATCH):
        chunk = ids[i : i + _ARXIV_API_BATCH]
        url = _ARXIV_API_URL.format(ids=",".join(chunk), n=len(chunk))
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=30) as resp:
                xml = resp.read()
            out.update(_parse_arxiv_titles(xml))
        except Exception as exc:
            print(
                f"arxiv title batch failed ({len(chunk)} ids): {exc}",
                file=sys.stderr, flush=True,
            )
    return out


def _default_arxiv_pdf_fetcher(aid: str) -> bytes | None:
    try:
        req = urllib.request.Request(
            _ARXIV_PDF_URL.format(aid=aid),
            headers={"User-Agent": "Mozilla/5.0"},
        )
        with urllib.request.urlopen(req, timeout=60) as resp:
            return resp.read()
    except Exception:
        return None


def _default_fetcher(url: str) -> str | None:
    import trafilatura
    try:
        return trafilatura.fetch_url(url)
    except Exception:
        return None


def _default_img_fetcher(url: str) -> bytes | None:
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            return resp.read()
    except Exception:
        return None


def _download_images(md: str, page_dir: Path, base_url: str,
                     img_fetcher: Callable[[str], bytes | None]) -> str:
    img_dir = page_dir / "img"

    def repl(m: re.Match) -> str:
        alt, src = m.group(1), m.group(2).strip()
        if src.startswith(("data:", "javascript:")):
            return m.group(0)
        abs_url = urljoin(base_url, src)
        try:
            data = img_fetcher(abs_url)
        except Exception:
            data = None
        if not data:
            return m.group(0)
        ext = Path(urlparse(abs_url).path).suffix
        if not ext or len(ext) > 6 or "/" in ext:
            ext = ".bin"
        name = url_hash(abs_url) + ext
        img_dir.mkdir(parents=True, exist_ok=True)
        (img_dir / name).write_bytes(data)
        return f"![{alt}](img/{name})"

    return _IMG_MD_RE.sub(repl, md)


def _render_crawled_page(url: str, md_text: str) -> str:
    from .render import E, _page, make_md

    md = make_md()
    banner = (
        '<p class="crawled-banner">Original: '
        f'<a href="{E(url)}">{E(url)}</a></p>'
    )
    body = banner + f'<div class="md">{md(md_text)}</div>'
    return _page(url, body)


def _load_index(index_file: Path) -> dict[str, str]:
    if not index_file.exists():
        return {}
    try:
        data = json.loads(index_file.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return {k: v for k, v in data.items() if isinstance(k, str) and isinstance(v, str)}


def load_link_map(out_dir: Path) -> dict[str, str]:
    """Load previously-crawled URL→local-path map, keeping only entries whose file exists."""
    out_dir = Path(out_dir)
    index_file = out_dir / "crawled" / "index.json"
    raw = _load_index(index_file)
    return {u: p for u, p in raw.items() if (out_dir / p).exists()}


def crawl(
    urls: Iterable[str],
    out_dir: Path,
    blacklist: Iterable[str] = DEFAULT_BLACKLIST,
    workers: int = 16,
    per_host: int = 2,
    fetcher: Callable[[str], str | None] | None = None,
    img_fetcher: Callable[[str], bytes | None] | None = None,
    arxiv_titles: Callable[[list[str]], dict[str, str]] | None = None,
    arxiv_pdf_fetcher: Callable[[str], bytes | None] | None = None,
) -> dict[str, str]:
    """Download and convert URLs to local readable HTML under ``out_dir/crawled/``.

    Returns ``{url: relative_path_from_out_dir}`` for all URLs that have a local copy
    (either just downloaded or previously cached). Idempotent.
    """
    import trafilatura

    fetcher = fetcher or _default_fetcher
    img_fetcher = img_fetcher or _default_img_fetcher
    arxiv_titles = arxiv_titles or _default_arxiv_titles
    arxiv_pdf_fetcher = arxiv_pdf_fetcher or _default_arxiv_pdf_fetcher
    out_dir = Path(out_dir)
    crawled_dir = out_dir / "crawled"
    crawled_dir.mkdir(parents=True, exist_ok=True)
    index_file = crawled_dir / "index.json"

    result_map = load_link_map(out_dir)

    url_list = list(urls)
    total = len(url_list)
    blacklisted: list[str] = []
    cached: list[str] = []
    work: list[str] = []
    for url in url_list:
        if is_blacklisted(url, blacklist):
            blacklisted.append(url)
            continue
        is_arxiv = _arxiv_id(url) is not None
        prev = result_map.get(url)
        if prev and (out_dir / prev).is_file():
            # An arxiv URL cached from before the arxiv feature still points at
            # a crawled HTML stub — force re-download as a PDF.
            if not is_arxiv or prev.startswith("arxiv/"):
                cached.append(url)
                continue
            result_map.pop(url, None)
        if not is_arxiv:
            h = url_hash(url)
            rel = f"crawled/{h}/index.html"
            if (out_dir / rel).is_file():
                cached.append(url)
                result_map[url] = rel
                continue
        work.append(url)

    width = max(len(str(total)), 1)

    def log(tag: str, url: str, extra: str = "") -> None:
        with progress_lock:
            progress[0] += 1
            i = progress[0]
        line = f"[{i:>{width}}/{total}] {tag:<11} {url}"
        if extra:
            line += f"  ({extra})"
        print(line, file=sys.stderr, flush=True)

    progress = [0]
    progress_lock = threading.Lock()
    stats = {"ok": 0, "fail": 0}
    stats_lock = threading.Lock()

    print(
        f"Crawling {total} URLs ({len(blacklisted)} blacklisted, "
        f"{len(cached)} cached, {len(work)} new) — "
        f"{workers} workers, {per_host}/host",
        file=sys.stderr,
        flush=True,
    )
    for url in blacklisted:
        log("blacklisted", url)
    for url in cached:
        log("cached", url)

    host_sems: dict[str, threading.Semaphore] = {}
    host_sems_lock = threading.Lock()

    def get_sem(host: str) -> threading.Semaphore:
        with host_sems_lock:
            sem = host_sems.get(host)
            if sem is None:
                sem = threading.Semaphore(per_host)
                host_sems[host] = sem
            return sem

    results_lock = threading.Lock()

    arxiv_ids_in_work = sorted({
        aid for aid in (_arxiv_id(u) for u in work) if aid is not None
    })
    arxiv_title_map = arxiv_titles(arxiv_ids_in_work) if arxiv_ids_in_work else {}

    def worker(url: str) -> None:
        sem = get_sem(_host(url))
        t0 = time.monotonic()
        aid = _arxiv_id(url)
        if aid is not None:
            with sem:
                try:
                    pdf = arxiv_pdf_fetcher(aid)
                except Exception as exc:
                    with stats_lock:
                        stats["fail"] += 1
                    log("fail", url, f"arxiv error: {exc}")
                    return
            if not pdf:
                with stats_lock:
                    stats["fail"] += 1
                log("fail", url, "arxiv pdf fetch failed")
                return
            title = arxiv_title_map.get(aid)
            name = _sanitize_filename(title or aid) + ".pdf"
            rel = f"arxiv/{name}"
            path = out_dir / rel
            if not path.exists():
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(pdf)
            with results_lock:
                result_map[url] = rel
            with stats_lock:
                stats["ok"] += 1
            log("ok", url, f"{time.monotonic() - t0:.2f}s arxiv")
            return
        with sem:
            try:
                html_text = fetcher(url)
            except Exception as exc:
                with stats_lock:
                    stats["fail"] += 1
                log("fail", url, f"fetch error: {exc}")
                return
            if not html_text:
                with stats_lock:
                    stats["fail"] += 1
                log("fail", url, "fetch returned nothing")
                return
            try:
                md_text = trafilatura.extract(
                    html_text,
                    output_format="markdown",
                    include_images=True,
                    include_links=True,
                )
            except Exception as exc:
                md_text = None
                extract_err = str(exc)
            else:
                extract_err = ""
            if not md_text:
                with stats_lock:
                    stats["fail"] += 1
                log("fail", url, extract_err or "no extractable content")
                return

        h = url_hash(url)
        page_dir = crawled_dir / h
        page_dir.mkdir(parents=True, exist_ok=True)
        md_rewritten = _download_images(md_text, page_dir, url, img_fetcher)
        page_html = _render_crawled_page(url, md_rewritten)
        (page_dir / "index.html").write_text(page_html, encoding="utf-8")
        (page_dir / "meta.json").write_text(
            json.dumps({"url": url}, ensure_ascii=False), encoding="utf-8"
        )
        rel = f"crawled/{h}/index.html"
        with results_lock:
            result_map[url] = rel
        with stats_lock:
            stats["ok"] += 1
        log("ok", url, f"{time.monotonic() - t0:.2f}s")

    if work:
        random.shuffle(work)  # spread hosts out so workers don't pile onto one semaphore
        with ThreadPoolExecutor(max_workers=workers) as pool:
            list(pool.map(worker, work))

    index_file.write_text(
        json.dumps(result_map, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    print(
        f"Done: {stats['ok']} ok, {stats['fail']} failed, "
        f"{len(blacklisted)} blacklisted, {len(cached)} cached",
        file=sys.stderr,
        flush=True,
    )
    return result_map
