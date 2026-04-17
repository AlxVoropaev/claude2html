"""Crawl external links from Claude chats to local readable copies."""

from __future__ import annotations

import hashlib
import json
import re
import threading
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Callable, Iterable
from urllib.parse import urljoin, urlparse

DEFAULT_BLACKLIST = frozenset({"reddit.com", "youtube.com", "youtu.be"})

_URL_RE = re.compile(r"""https?://[^\s<>"'\)\]]+""")
_TRAILING_PUNCT = ".,);:!?\"'"
_IMG_MD_RE = re.compile(r"!\[([^\]]*)\]\(([^)]+)\)")


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
    return _page(url, body, asset_prefix="../../")


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
) -> dict[str, str]:
    """Download and convert URLs to local readable HTML under ``out_dir/crawled/``.

    Returns ``{url: relative_path_from_out_dir}`` for all URLs that have a local copy
    (either just downloaded or previously cached). Idempotent.
    """
    import trafilatura

    fetcher = fetcher or _default_fetcher
    img_fetcher = img_fetcher or _default_img_fetcher
    out_dir = Path(out_dir)
    crawled_dir = out_dir / "crawled"
    crawled_dir.mkdir(parents=True, exist_ok=True)
    index_file = crawled_dir / "index.json"

    result_map = load_link_map(out_dir)

    work: list[str] = []
    for url in urls:
        if is_blacklisted(url, blacklist):
            continue
        h = url_hash(url)
        rel = f"crawled/{h}/index.html"
        if (out_dir / rel).is_file():
            result_map[url] = rel
            continue
        work.append(url)

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

    def worker(url: str) -> None:
        sem = get_sem(_host(url))
        with sem:
            try:
                html_text = fetcher(url)
            except Exception:
                return
            if not html_text:
                return
            try:
                md_text = trafilatura.extract(
                    html_text,
                    output_format="markdown",
                    include_images=True,
                    include_links=True,
                )
            except Exception:
                md_text = None
            if not md_text:
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

    if work:
        with ThreadPoolExecutor(max_workers=workers) as pool:
            list(pool.map(worker, work))

    index_file.write_text(
        json.dumps(result_map, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    return result_map
