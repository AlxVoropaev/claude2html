"""Tests for the crawler module."""

import threading
import time

import pytest

from claude2html.crawler import (
    DEFAULT_BLACKLIST,
    _arxiv_id,
    _parse_arxiv_titles,
    _sanitize_filename,
    collect_urls,
    crawl,
    is_blacklisted,
    url_hash,
)


# ---------- collect_urls ----------

def test_collect_urls_from_message_text():
    convs = [{"chat_messages": [{
        "content": [{"type": "text",
                     "text": "see https://habr.com/ru/articles/1002878/ for details"}]
    }]}]
    assert "https://habr.com/ru/articles/1002878/" in collect_urls(convs)


def test_collect_urls_from_artifact_content():
    convs = [{"chat_messages": [{
        "content": [{
            "type": "tool_use",
            "name": "artifacts",
            "input": {"content": "# T\n\nLink: https://example.com/a"},
        }]
    }]}]
    assert "https://example.com/a" in collect_urls(convs)


def test_collect_urls_ignores_md_citations():
    convs = [{"chat_messages": [{
        "content": [{
            "type": "tool_use",
            "name": "artifacts",
            "input": {
                "content": "no links here",
                "md_citations": [{"url": "https://cited.example/x"}],
            },
        }]
    }]}]
    assert collect_urls(convs) == set()


def test_collect_urls_ignores_tool_results_and_web_search():
    convs = [{"chat_messages": [{
        "content": [
            {"type": "tool_use", "name": "web_search",
             "input": {"query": "https://ignored-query.com/x"}},
            {"type": "tool_result", "name": "web_search",
             "content": [{"url": "https://search.example/r", "text": "snippet"}]},
        ]
    }]}]
    assert collect_urls(convs) == set()


def test_collect_urls_dedupes_across_messages():
    convs = [{"chat_messages": [
        {"content": [{"type": "text", "text": "https://x.example/a"}]},
        {"content": [{"type": "text", "text": "again https://x.example/a !"}]},
    ]}]
    assert collect_urls(convs) == {"https://x.example/a"}


def test_collect_urls_strips_trailing_punctuation():
    convs = [{"chat_messages": [{
        "content": [{"type": "text",
                     "text": "see (https://example.com/a), and https://example.com/b."}]
    }]}]
    urls = collect_urls(convs)
    assert "https://example.com/a" in urls
    assert "https://example.com/b" in urls


def test_collect_urls_extracts_from_markdown_link_syntax():
    convs = [{"chat_messages": [{
        "content": [{"type": "text",
                     "text": "check [this](https://md.example/post) out"}]
    }]}]
    assert "https://md.example/post" in collect_urls(convs)


def test_collect_urls_from_bare_text_and_artifact_mixed():
    convs = [{"chat_messages": [
        {"content": [{"type": "text", "text": "start https://a.example/1"}]},
        {"content": [
            {"type": "tool_use", "name": "artifacts",
             "input": {"content": "## Report\n\nSources: https://b.example/2"}},
        ]},
    ]}]
    assert collect_urls(convs) == {"https://a.example/1", "https://b.example/2"}


# ---------- blacklist ----------

@pytest.mark.parametrize("url", [
    "https://reddit.com/r/python",
    "https://www.reddit.com/r/py",
    "https://old.reddit.com/x",
    "https://youtube.com/watch?v=1",
    "https://m.youtube.com/watch?v=1",
    "https://youtu.be/abc",
])
def test_is_blacklisted_matches(url):
    assert is_blacklisted(url)


@pytest.mark.parametrize("url", [
    "https://notreddit.com/p",
    "https://reddit.com.evil.com/p",
    "https://example.com/p",
    "https://habr.com/ru/articles/1",
])
def test_is_blacklisted_does_not_match(url):
    assert not is_blacklisted(url)


def test_is_blacklisted_custom_list():
    assert is_blacklisted("https://twitter.com/x", blacklist={"twitter.com"})
    assert not is_blacklisted("https://reddit.com/x", blacklist={"twitter.com"})


# ---------- url_hash ----------

def test_url_hash_deterministic_and_distinct():
    assert url_hash("https://a.example/x") == url_hash("https://a.example/x")
    assert url_hash("https://a.example/x") != url_hash("https://a.example/y")
    assert len(url_hash("https://a.example/x")) >= 8


# ---------- crawl: basic behavior ----------

HTML_OK = '<html><body><article><p>Hello from {url}.</p></article></body></html>'


def _make_fetcher(pages=None, record=None):
    pages = pages or {}

    def fetch(url):
        if record is not None:
            record.append(url)
        if url in pages:
            return pages[url]
        return HTML_OK.format(url=url)

    return fetch


def _null_img(url):
    return None


def test_crawl_writes_cache_dir_and_returns_mapping(tmp_path):
    fetch = _make_fetcher()
    result = crawl({"https://example.com/a"}, tmp_path,
                   fetcher=fetch, img_fetcher=_null_img)
    assert "https://example.com/a" in result
    local = result["https://example.com/a"]
    assert local.startswith("crawled/")
    assert local.endswith("/index.html")
    assert (tmp_path / local).is_file()


def test_crawl_local_page_shows_original_url(tmp_path):
    fetch = _make_fetcher()
    result = crawl({"https://example.com/a"}, tmp_path,
                   fetcher=fetch, img_fetcher=_null_img)
    page = (tmp_path / result["https://example.com/a"]).read_text()
    assert "https://example.com/a" in page
    # Banner has a link back to the original
    assert 'href="https://example.com/a"' in page


def test_crawl_renders_extracted_content(tmp_path):
    pages = {"https://example.com/a":
             "<html><body><article><h1>Hi</h1><p>Body text here.</p>"
             "</article></body></html>"}
    fetch = _make_fetcher(pages=pages)
    result = crawl({"https://example.com/a"}, tmp_path,
                   fetcher=fetch, img_fetcher=_null_img)
    page = (tmp_path / result["https://example.com/a"]).read_text()
    assert "Body text here" in page


def test_crawl_is_idempotent(tmp_path):
    record = []
    fetch = _make_fetcher(record=record)
    urls = {"https://example.com/a"}
    crawl(urls, tmp_path, fetcher=fetch, img_fetcher=_null_img)
    assert len(record) == 1
    crawl(urls, tmp_path, fetcher=fetch, img_fetcher=_null_img)
    assert len(record) == 1  # cached, no new fetch


def test_crawl_skips_blacklisted(tmp_path):
    record = []
    fetch = _make_fetcher(record=record)
    urls = {
        "https://reddit.com/r/py",
        "https://www.youtube.com/watch?v=1",
        "https://youtu.be/abc",
        "https://ok.example/p",
    }
    result = crawl(urls, tmp_path, fetcher=fetch, img_fetcher=_null_img)
    assert record == ["https://ok.example/p"]
    assert "https://ok.example/p" in result
    for u in urls - {"https://ok.example/p"}:
        assert u not in result


def test_crawl_handles_fetch_failure(tmp_path):
    def fetch(url):
        return None  # simulate network failure

    result = crawl({"https://bad.example/p"}, tmp_path,
                   fetcher=fetch, img_fetcher=_null_img)
    assert "https://bad.example/p" not in result


def test_crawl_handles_empty_extraction(tmp_path):
    # Page with no extractable article content
    def fetch(url):
        return "<html><body></body></html>"

    result = crawl({"https://empty.example/p"}, tmp_path,
                   fetcher=fetch, img_fetcher=_null_img)
    assert "https://empty.example/p" not in result


# ---------- crawl: concurrency ----------

def test_crawl_per_host_limit(tmp_path):
    """No more than `per_host` concurrent fetches to the same host."""
    in_flight = 0
    max_concurrent = 0
    lock = threading.Lock()

    def fetch(url):
        nonlocal in_flight, max_concurrent
        with lock:
            in_flight += 1
            if in_flight > max_concurrent:
                max_concurrent = in_flight
        time.sleep(0.05)
        with lock:
            in_flight -= 1
        return HTML_OK.format(url=url)

    urls = {f"https://same.example/p{i}" for i in range(10)}
    crawl(urls, tmp_path, fetcher=fetch, img_fetcher=_null_img,
          workers=16, per_host=2)
    assert max_concurrent <= 2


def test_crawl_different_hosts_run_in_parallel(tmp_path):
    """Different hosts are not throttled against each other."""
    in_flight = 0
    max_concurrent = 0
    lock = threading.Lock()

    def fetch(url):
        nonlocal in_flight, max_concurrent
        with lock:
            in_flight += 1
            if in_flight > max_concurrent:
                max_concurrent = in_flight
        time.sleep(0.05)
        with lock:
            in_flight -= 1
        return HTML_OK.format(url=url)

    urls = {f"https://host{i}.example/p" for i in range(8)}
    crawl(urls, tmp_path, fetcher=fetch, img_fetcher=_null_img,
          workers=16, per_host=2)
    assert max_concurrent >= 2  # at least some parallelism


# ---------- crawl: images ----------

def test_crawl_downloads_images_and_rewrites(tmp_path):
    pages = {"https://ex.example/p":
             '<html><body><article>'
             '<h1>Real Heading Title</h1>'
             '<p>First paragraph with enough words to count as substance.</p>'
             '<p>Second paragraph elaborates on the topic at hand.</p>'
             '<img src="https://img.example/a.png" alt="pic">'
             '<p>Third paragraph continues after the image.</p>'
             '<p>Fourth paragraph wraps up the article nicely.</p>'
             '</article></body></html>'}
    img_calls = []

    def img_fetch(url):
        img_calls.append(url)
        return b"\x89PNG\r\n\x1a\nfake-bytes"

    result = crawl({"https://ex.example/p"}, tmp_path,
                   fetcher=_make_fetcher(pages=pages),
                   img_fetcher=img_fetch)
    assert "https://ex.example/p" in result
    local = tmp_path / result["https://ex.example/p"]
    page_dir = local.parent
    img_dir = page_dir / "img"
    assert img_dir.is_dir()
    assert any(p.is_file() for p in img_dir.iterdir())
    assert img_calls == ["https://img.example/a.png"]
    # Page references local image, not remote
    page = local.read_text()
    assert 'src="img/' in page
    assert "https://img.example/a.png" not in page


def test_crawl_handles_image_fetch_failure(tmp_path):
    """Image download failure doesn't abort the whole page."""
    pages = {"https://ex.example/p":
             '<html><body><article>'
             '<h1>Another Article Heading</h1>'
             '<p>Body paragraph with real content for the extractor to notice.</p>'
             '<p>Second body paragraph extends the article further.</p>'
             '<img src="https://img.example/a.png" alt="pic">'
             '<p>Third paragraph after the image to keep context.</p>'
             '<p>Final paragraph closes things out.</p>'
             '</article></body></html>'}

    def img_fetch(url):
        return None  # fail

    result = crawl({"https://ex.example/p"}, tmp_path,
                   fetcher=_make_fetcher(pages=pages),
                   img_fetcher=img_fetch)
    assert "https://ex.example/p" in result
    page = (tmp_path / result["https://ex.example/p"]).read_text()
    assert "Body" in page


# ---------- arxiv ----------

@pytest.mark.parametrize("url,expected", [
    ("https://arxiv.org/abs/2604.14312", "2604.14312"),
    ("https://arxiv.org/html/2604.14312", "2604.14312"),
    ("https://arxiv.org/pdf/2604.14312", "2604.14312"),
    ("https://arxiv.org/pdf/2604.14312.pdf", "2604.14312"),
    ("https://arxiv.org/abs/2604.14312v1", "2604.14312"),
    ("https://arxiv.org/abs/2604.14312v3", "2604.14312"),
    ("https://arxiv.org/pdf/2604.14312v2.pdf", "2604.14312"),
    ("https://www.arxiv.org/abs/2604.14312", "2604.14312"),
    ("https://arxiv.org/abs/2604.14312?foo=bar", "2604.14312"),
])
def test_arxiv_id_extraction(url, expected):
    assert _arxiv_id(url) == expected


@pytest.mark.parametrize("url", [
    "https://example.com/abs/2604.14312",
    "https://arxiv.org/",
    "https://arxiv.org/find/abc",
    "https://evil.arxiv.org.attacker.com/abs/x",
])
def test_arxiv_id_rejects_non_arxiv(url):
    assert _arxiv_id(url) is None


def test_sanitize_filename_strips_bad_chars():
    assert _sanitize_filename('Foo: "Bar" / Baz?') == "Foo Bar Baz"


def test_sanitize_filename_empty_falls_back():
    assert _sanitize_filename("///") == "untitled"


def test_parse_arxiv_titles_multiple_entries():
    xml = b"""<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <entry>
    <id>http://arxiv.org/abs/2604.14312v2</id>
    <title>Attention
      Is All You Need</title>
  </entry>
  <entry>
    <id>http://arxiv.org/abs/2501.00001</id>
    <title>Another Paper</title>
  </entry>
</feed>"""
    assert _parse_arxiv_titles(xml) == {
        "2604.14312": "Attention Is All You Need",
        "2501.00001": "Another Paper",
    }


def test_sanitize_filename_truncates():
    assert len(_sanitize_filename("x" * 500, max_len=40)) <= 40


def _arxiv_titles_fn(title="A Paper"):
    def f(ids):
        return {aid: title for aid in ids} if title else {}
    return f


def _arxiv_pdf_fn(pdf=b"%PDF-1.4 fake"):
    def f(aid):
        return pdf
    return f


def _arxiv_kwargs(title="A Paper", pdf=b"%PDF-1.4 fake"):
    return dict(
        arxiv_titles=_arxiv_titles_fn(title),
        arxiv_pdf_fetcher=_arxiv_pdf_fn(pdf),
    )


def test_crawl_arxiv_writes_pdf_to_arxiv_dir(tmp_path):
    result = crawl(
        ["https://arxiv.org/abs/2604.14312"],
        tmp_path,
        fetcher=_make_fetcher(),
        img_fetcher=_null_img,
        **_arxiv_kwargs(title="Attention Is All You Need"),
    )
    url = "https://arxiv.org/abs/2604.14312"
    assert url in result
    rel = result[url]
    assert rel == "arxiv/Attention Is All You Need.pdf"
    assert (tmp_path / rel).is_file()
    assert (tmp_path / rel).read_bytes() == b"%PDF-1.4 fake"


def test_crawl_arxiv_html_url_also_downloads_pdf(tmp_path):
    url = "https://arxiv.org/html/2604.14312"
    result = crawl([url], tmp_path,
                   fetcher=_make_fetcher(), img_fetcher=_null_img,
                   **_arxiv_kwargs(title="Foo"))
    assert result[url] == "arxiv/Foo.pdf"


def test_crawl_arxiv_falls_back_to_id_when_title_missing(tmp_path):
    url = "https://arxiv.org/abs/2604.14312"
    result = crawl([url], tmp_path,
                   fetcher=_make_fetcher(), img_fetcher=_null_img,
                   **_arxiv_kwargs(title=None))
    assert result[url] == "arxiv/2604.14312.pdf"


def test_crawl_arxiv_pdf_failure(tmp_path):
    url = "https://arxiv.org/abs/2604.14312"
    result = crawl([url], tmp_path,
                   fetcher=_make_fetcher(), img_fetcher=_null_img,
                   **_arxiv_kwargs(title="X", pdf=None))
    assert url not in result


def test_crawl_arxiv_is_idempotent(tmp_path):
    pdf_calls = []
    title_calls = []

    def pdf_fetch(aid):
        pdf_calls.append(aid)
        return b"%PDF-1.4 fake"

    def titles(ids):
        title_calls.append(list(ids))
        return {aid: "Paper" for aid in ids}

    url = "https://arxiv.org/abs/2604.14312"
    crawl([url], tmp_path, fetcher=_make_fetcher(), img_fetcher=_null_img,
          arxiv_titles=titles, arxiv_pdf_fetcher=pdf_fetch)
    assert pdf_calls == ["2604.14312"]
    assert title_calls == [["2604.14312"]]
    crawl([url], tmp_path, fetcher=_make_fetcher(), img_fetcher=_null_img,
          arxiv_titles=titles, arxiv_pdf_fetcher=pdf_fetch)
    assert pdf_calls == ["2604.14312"]  # cached via index.json
    assert title_calls == [["2604.14312"]]  # second run: no ids → no call


def test_crawl_arxiv_batches_titles_into_one_call(tmp_path):
    title_calls = []

    def titles(ids):
        title_calls.append(list(ids))
        return {aid: f"Paper {aid}" for aid in ids}

    urls = [
        "https://arxiv.org/abs/2604.14312",
        "https://arxiv.org/html/2512.99999",
        "https://arxiv.org/pdf/2501.00001v3",
    ]
    crawl(urls, tmp_path, fetcher=_make_fetcher(), img_fetcher=_null_img,
          arxiv_titles=titles, arxiv_pdf_fetcher=_arxiv_pdf_fn())
    assert len(title_calls) == 1
    assert sorted(title_calls[0]) == ["2501.00001", "2512.99999", "2604.14312"]


def test_crawl_arxiv_migrates_old_crawled_html_cache(tmp_path):
    """Arxiv URLs previously crawled as HTML must be re-downloaded as PDF."""
    import json as _json
    url = "https://arxiv.org/abs/2604.14312"
    h = url_hash(url)
    (tmp_path / "crawled" / h).mkdir(parents=True)
    (tmp_path / "crawled" / h / "index.html").write_text("<html/>")
    (tmp_path / "crawled").mkdir(exist_ok=True)
    (tmp_path / "crawled" / "index.json").write_text(
        _json.dumps({url: f"crawled/{h}/index.html"})
    )
    result = crawl([url], tmp_path,
                   fetcher=_make_fetcher(), img_fetcher=_null_img,
                   **_arxiv_kwargs(title="New Title"))
    assert result[url] == "arxiv/New Title.pdf"
    assert (tmp_path / "arxiv" / "New Title.pdf").is_file()


def test_crawl_arxiv_does_not_create_crawled_dir_for_pdf(tmp_path):
    url = "https://arxiv.org/abs/2604.14312"
    result = crawl([url], tmp_path,
                   fetcher=_make_fetcher(), img_fetcher=_null_img,
                   **_arxiv_kwargs(title="Foo"))
    # No per-URL HTML stub under crawled/<hash>/
    h = url_hash(url)
    assert not (tmp_path / "crawled" / h).exists()
    # PDF sits in arxiv/ instead
    assert (tmp_path / result[url]).is_file()


# ---------- defaults ----------

def test_default_blacklist_has_expected_hosts():
    assert "reddit.com" in DEFAULT_BLACKLIST
    assert "youtube.com" in DEFAULT_BLACKLIST
    assert "youtu.be" in DEFAULT_BLACKLIST
