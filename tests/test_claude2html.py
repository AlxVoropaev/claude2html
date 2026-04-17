"""Tests for the claude2html converter (v1)."""

import json
import subprocess
import sys
import zipfile
from pathlib import Path

import claude2html

ROOT = Path(__file__).resolve().parent.parent


def _fixture():
    """A minimal export covering every observed content block type."""
    return [
        {
            "uuid": "conv-aaa",
            "name": "Meeting Claude",
            "summary": "",
            "created_at": "2026-04-10T15:17:22Z",
            "updated_at": "2026-04-10T15:19:40Z",
            "account": {"uuid": "u1"},
            "chat_messages": [
                {
                    "uuid": "m1",
                    "text": "Hello <there> & friends",
                    "content": [
                        {
                            "type": "text",
                            "text": "Hello <there> & friends",
                            "citations": [],
                            "start_timestamp": "2026-04-10T15:17:27Z",
                            "stop_timestamp": "2026-04-10T15:17:27Z",
                            "flags": None,
                        }
                    ],
                    "sender": "human",
                    "created_at": "2026-04-10T15:17:27Z",
                    "updated_at": "2026-04-10T15:17:27Z",
                    "attachments": [],
                    "files": [],
                    "parent_message_uuid": None,
                },
                {
                    "uuid": "m2",
                    "text": "Let me search.",
                    "content": [
                        {
                            "type": "thinking",
                            "thinking": "I should call web_search.",
                            "summaries": [{"summary": "Planning a search."}],
                            "cut_off": False,
                            "truncated": False,
                            "alternative_display_type": None,
                            "signature": None,
                            "start_timestamp": "2026-04-10T15:17:30Z",
                            "stop_timestamp": "2026-04-10T15:17:31Z",
                            "flags": None,
                        },
                        {
                            "type": "text",
                            "text": "Let me search.",
                            "citations": [],
                            "start_timestamp": "2026-04-10T15:17:31Z",
                            "stop_timestamp": "2026-04-10T15:17:31Z",
                            "flags": None,
                        },
                        {
                            "type": "tool_use",
                            "id": "toolu_1",
                            "name": "web_search",
                            "input": {"query": "claude export format"},
                            "message": "web_search",
                            "start_timestamp": "2026-04-10T15:17:32Z",
                            "stop_timestamp": "2026-04-10T15:17:32Z",
                            "flags": None,
                        },
                        {
                            "type": "tool_result",
                            "tool_use_id": "toolu_1",
                            "name": "web_search",
                            "content": [
                                {
                                    "type": "knowledge",
                                    "title": "Docs <title>",
                                    "url": "https://example.com/a",
                                    "text": "Snippet one.",
                                },
                                {"type": "text", "text": "Snippet two."},
                            ],
                            "is_error": False,
                            "message": None,
                            "start_timestamp": None,
                            "stop_timestamp": None,
                            "flags": None,
                        },
                    ],
                    "sender": "assistant",
                    "created_at": "2026-04-10T15:17:30Z",
                    "updated_at": "2026-04-10T15:17:32Z",
                    "attachments": [
                        {
                            "file_name": "prompts.md",
                            "file_size": 42,
                            "file_type": "text/markdown",
                            "extracted_content": "# Pasted\n<escape me>",
                        }
                    ],
                    "files": [
                        {"file_uuid": "f1", "file_name": "scan.pdf"}
                    ],
                    "parent_message_uuid": "m1",
                },
            ],
        },
        {
            "uuid": "conv-research",
            "name": "Deep research question",
            "summary": "",
            "created_at": "2026-04-12T10:00:00Z",
            "updated_at": "2026-04-12T10:05:00Z",
            "account": {"uuid": "u1"},
            "chat_messages": [
                {
                    "uuid": "m-r1",
                    "text": "research please",
                    "content": [
                        {
                            "type": "text",
                            "text": "research please",
                            "citations": [],
                            "start_timestamp": "2026-04-12T10:00:00Z",
                            "stop_timestamp": "2026-04-12T10:00:00Z",
                            "flags": None,
                        }
                    ],
                    "sender": "human",
                    "created_at": "2026-04-12T10:00:00Z",
                    "updated_at": "2026-04-12T10:00:00Z",
                    "attachments": [],
                    "files": [],
                    "parent_message_uuid": None,
                },
                {
                    "uuid": "m-r2",
                    "text": "done",
                    "content": [
                        {
                            "type": "tool_use",
                            "id": "toolu_ext",
                            "name": "launch_extended_search_task",
                            "input": {"command": "SECRET_QUERY_XYZ"},
                            "message": "launch_extended_search_task",
                            "start_timestamp": None,
                            "stop_timestamp": None,
                            "flags": None,
                        },
                        {
                            "type": "tool_result",
                            "tool_use_id": None,
                            "name": "launch_extended_search_task",
                            "content": [{"type": "text", "text": "SECRET_RESULT_XYZ"}],
                            "is_error": False,
                            "message": None,
                            "start_timestamp": None,
                            "stop_timestamp": None,
                            "flags": None,
                        },
                        {
                            "type": "text",
                            "text": "Here you go.",
                            "citations": [],
                            "start_timestamp": None,
                            "stop_timestamp": None,
                            "flags": None,
                        },
                        {
                            "type": "tool_use",
                            "id": "toolu_art",
                            "name": "artifacts",
                            "input": {
                                "command": "create",
                                "id": "art-id-1",
                                "title": "Research Report",
                                "type": "text/markdown",
                                "language": None,
                                "content": "# Hello\n\nBody **markdown** here.",
                                "md_citations": [
                                    {
                                        "uuid": "c1",
                                        "title": "forbes",
                                        "url": "https://example.com/forbes",
                                        "metadata": {
                                            "preview_title": "Real page headline from Forbes",
                                            "icon_url": "https://icons.example/forbes.png",
                                            "source": "forbes",
                                        },
                                    },
                                    {
                                        "uuid": "c2",
                                        "title": "forbes",
                                        "url": "https://example.com/forbes",
                                        "metadata": {
                                            "preview_title": "Real page headline from Forbes",
                                            "icon_url": "https://icons.example/forbes.png",
                                            "source": "forbes",
                                        },
                                    },
                                    {
                                        "uuid": "c3",
                                        "title": "Other page title",
                                        "url": "https://example.com/other",
                                        "metadata": {
                                            "icon_url": "https://icons.example/other.png",
                                            "source": "Other Site",
                                        },
                                    },
                                ],
                            },
                            "message": "artifacts",
                            "start_timestamp": None,
                            "stop_timestamp": None,
                            "flags": None,
                        },
                        {
                            "type": "tool_result",
                            "tool_use_id": None,
                            "name": "artifacts",
                            "content": [{"type": "text", "text": "OK"}],
                            "is_error": False,
                            "message": None,
                            "start_timestamp": None,
                            "stop_timestamp": None,
                            "flags": None,
                        },
                    ],
                    "sender": "assistant",
                    "created_at": "2026-04-12T10:05:00Z",
                    "updated_at": "2026-04-12T10:05:00Z",
                    "attachments": [],
                    "files": [],
                    "parent_message_uuid": "m-r1",
                },
            ],
        },
        {
            "uuid": "conv-bbb",
            "name": "",  # empty name → should fall back to "Untitled"
            "summary": "",
            "created_at": "2026-04-11T09:00:00Z",
            "updated_at": "2026-04-11T09:05:00Z",
            "account": {"uuid": "u1"},
            "chat_messages": [
                {
                    "uuid": "m3",
                    "text": "hi",
                    "content": [
                        {
                            "type": "text",
                            "text": "hi",
                            "citations": [],
                            "start_timestamp": "2026-04-11T09:00:00Z",
                            "stop_timestamp": "2026-04-11T09:00:00Z",
                            "flags": None,
                        }
                    ],
                    "sender": "human",
                    "created_at": "2026-04-11T09:00:00Z",
                    "updated_at": "2026-04-11T09:00:00Z",
                    "attachments": [],
                    "files": [],
                    "parent_message_uuid": None,
                }
            ],
        },
    ]


def _run(tmp_path):
    src = tmp_path / "conversations.json"
    src.write_text(json.dumps(_fixture()), encoding="utf-8")
    out = tmp_path / "out"
    result = subprocess.run(
        [sys.executable, "-m", "claude2html", str(src), "-o", str(out)],
        capture_output=True,
        text=True,
        cwd=str(ROOT),
    )
    assert result.returncode == 0, result.stderr
    return out


AAA = Path("chats/2026-04-10/conv-aaa.html")
BBB = Path("chats/2026-04-11/conv-bbb.html")
RESEARCH = Path("chats/2026-04-12/conv-research.html")
RESEARCH_ART = Path("artifacts/conv-research-1.html")
ARTIFACTS_INDEX = Path("artifacts/index.html")


def test_accepts_zip_export(tmp_path):
    src = tmp_path / "export.zip"
    with zipfile.ZipFile(src, "w") as z:
        z.writestr("conversations.json", json.dumps(_fixture()))
    out = tmp_path / "out"
    result = subprocess.run(
        [sys.executable, "-m", "claude2html", str(src), "-o", str(out)],
        capture_output=True,
        text=True,
        cwd=str(ROOT),
    )
    assert result.returncode == 0, result.stderr
    assert (out / "index.html").is_file()
    assert (out / "chats/2026-04-10/conv-aaa.html").is_file()


def test_output_layout(tmp_path):
    out = _run(tmp_path)
    assert (out / "index.html").is_file()
    assert (out / AAA).is_file()
    assert (out / BBB).is_file()
    html_files = sorted(str(p.relative_to(out)) for p in out.rglob("*.html"))
    assert html_files == [
        str(RESEARCH_ART),
        str(ARTIFACTS_INDEX),
        str(AAA),
        str(BBB),
        str(RESEARCH),
        "index.html",
    ]


def test_index_lists_both_and_uses_fallback_title(tmp_path):
    out = _run(tmp_path)
    idx = (out / "index.html").read_text(encoding="utf-8")
    assert f'href="{AAA.as_posix()}"' in idx
    assert f'href="{BBB.as_posix()}"' in idx
    assert "Meeting Claude" in idx
    assert "Untitled" in idx  # fallback for empty name


def test_index_groups_by_date_desc(tmp_path):
    out = _run(tmp_path)
    idx = (out / "index.html").read_text(encoding="utf-8")
    # Newer date heading should come before older one
    assert idx.index("<h2>2026-04-11</h2>") < idx.index("<h2>2026-04-10</h2>")
    # Each conversation is listed under its date's heading
    assert idx.index("<h2>2026-04-11</h2>") < idx.index("conv-bbb.html")
    assert idx.index("conv-bbb.html") < idx.index("<h2>2026-04-10</h2>")
    assert idx.index("<h2>2026-04-10</h2>") < idx.index("conv-aaa.html")


def test_renders_text_and_escapes_html(tmp_path):
    out = _run(tmp_path)
    page = (out / AAA).read_text(encoding="utf-8")
    assert "Hello &lt;there&gt; &amp; friends" in page
    assert "<there>" not in page  # raw angle brackets must not leak


def test_renders_tool_use_with_input(tmp_path):
    out = _run(tmp_path)
    page = (out / AAA).read_text(encoding="utf-8")
    assert "web_search" in page
    assert "claude export format" in page  # the query from input


def test_renders_tool_result_flattened(tmp_path):
    out = _run(tmp_path)
    page = (out / AAA).read_text(encoding="utf-8")
    assert "Snippet one." in page
    assert "Snippet two." in page
    assert "Docs &lt;title&gt;" in page  # title rendered & escaped


def test_renders_thinking(tmp_path):
    out = _run(tmp_path)
    page = (out / AAA).read_text(encoding="utf-8")
    assert "I should call web_search." in page


def test_renders_attachment_and_file_names(tmp_path):
    out = _run(tmp_path)
    page = (out / AAA).read_text(encoding="utf-8")
    assert "prompts.md" in page
    assert "scan.pdf" in page
    # Attachment extracted content is shown and escaped
    assert "# Pasted" in page
    assert "&lt;escape me&gt;" in page


def test_role_labels_present(tmp_path):
    out = _run(tmp_path)
    page = (out / AAA).read_text(encoding="utf-8")
    # Some indication of who sent each message
    assert "human" in page.lower()
    assert "assistant" in page.lower()


def test_page_is_self_contained(tmp_path):
    out = _run(tmp_path)
    page = (out / AAA).read_text(encoding="utf-8")
    # CSS and JS are inlined so pages work when opened via content:// URIs
    assert "<style>" in page and "--bg:" in page
    assert "<script>" in page and 'localStorage.getItem("theme")' in page
    head = page.split("</head>")[0]
    assert "http://" not in head
    assert "https://" not in head


def test_index_is_self_contained(tmp_path):
    out = _run(tmp_path)
    idx = (out / "index.html").read_text(encoding="utf-8")
    assert "<style>" in idx and "--bg:" in idx
    assert "<script>" in idx and 'localStorage.getItem("theme")' in idx


def test_theme_selector_lists_all_four(tmp_path):
    out = _run(tmp_path)
    page = (out / AAA).read_text(encoding="utf-8")
    for value in ("github-light", "github-dark", "monokai-pro-light", "monokai-pro-dark"):
        assert f'value="{value}"' in page


def test_conversation_page_has_title_and_timestamps(tmp_path):
    out = _run(tmp_path)
    page = (out / AAA).read_text(encoding="utf-8")
    assert "Meeting Claude" in page
    assert "2026-04-10" in page


def test_extended_search_task_is_stripped(tmp_path):
    out = _run(tmp_path)
    page = (out / RESEARCH).read_text(encoding="utf-8")
    assert "launch_extended_search_task" not in page
    assert "SECRET_QUERY_XYZ" not in page
    assert "SECRET_RESULT_XYZ" not in page


def test_artifact_is_extracted_and_linked(tmp_path):
    out = _run(tmp_path)
    page = (out / RESEARCH).read_text(encoding="utf-8")
    assert (out / RESEARCH_ART).is_file()
    assert 'href="../../artifacts/conv-research-1.html"' in page
    assert "Research Report" in page
    # The artifact body is NOT inlined into the chat page
    assert "Body <strong>markdown</strong>" not in page


def test_artifact_page_renders_markdown_and_back_link(tmp_path):
    out = _run(tmp_path)
    art = (out / RESEARCH_ART).read_text(encoding="utf-8")
    assert "<h1>Hello</h1>" in art
    assert "<strong>markdown</strong>" in art
    # Back link to chat, plus nav links to both indices
    assert 'href="../chats/2026-04-12/conv-research.html"' in art
    assert 'href="index.html"' in art  # artifact index
    assert 'href="../index.html"' in art  # chats index


def test_artifact_page_collapses_deduped_citations(tmp_path):
    out = _run(tmp_path)
    art = (out / RESEARCH_ART).read_text(encoding="utf-8")
    assert "<details" in art
    assert "Sources (2)" in art
    assert 'href="https://example.com/forbes"' in art
    assert 'href="https://example.com/other"' in art
    # duplicate URL listed only once
    assert art.count('href="https://example.com/forbes"') == 1


def test_citation_entry_has_icon_title_and_site(tmp_path):
    out = _run(tmp_path)
    art = (out / RESEARCH_ART).read_text(encoding="utf-8")
    # Icons referenced remotely (not downloaded)
    assert 'src="https://icons.example/forbes.png"' in art
    assert 'src="https://icons.example/other.png"' in art
    # Linked text prefers metadata.preview_title over the short title
    assert (
        '<a href="https://example.com/forbes">Real page headline from Forbes</a>'
        in art
    )
    # Falls back to cit.title when preview_title is absent
    assert (
        '<a href="https://example.com/other">Other page title</a>' in art
    )
    # Site is shown in parens
    assert "(forbes)" in art
    assert "(Other Site)" in art


def test_artifact_index_lists_and_links_to_chat(tmp_path):
    out = _run(tmp_path)
    idx = (out / ARTIFACTS_INDEX).read_text(encoding="utf-8")
    assert "Artifacts (1)" in idx
    assert 'href="conv-research-1.html"' in idx
    assert ">Research Report</a>" in idx
    # Links back to its chat
    assert 'href="../chats/2026-04-12/conv-research.html"' in idx
    # Links back to main index
    assert 'href="../index.html"' in idx


def test_main_index_links_to_artifact_index(tmp_path):
    out = _run(tmp_path)
    idx = (out / "index.html").read_text(encoding="utf-8")
    assert 'href="artifacts/index.html"' in idx
    assert "Artifacts (1)" in idx


def test_chat_page_links_to_artifact_index(tmp_path):
    out = _run(tmp_path)
    page = (out / RESEARCH).read_text(encoding="utf-8")
    assert 'href="../../artifacts/index.html"' in page


# ---------- crawl integration ----------

def _crawl_fixture():
    """Export with URLs in message text and artifact content."""
    return [
        {
            "uuid": "conv-cr",
            "name": "Crawl me",
            "created_at": "2026-04-13T10:00:00Z",
            "updated_at": "2026-04-13T10:00:00Z",
            "chat_messages": [
                {
                    "uuid": "m1",
                    "sender": "human",
                    "created_at": "2026-04-13T10:00:00Z",
                    "content": [{
                        "type": "text",
                        "text": "See https://good.example/post and "
                                "https://reddit.com/r/python (skipped).",
                    }],
                },
                {
                    "uuid": "m2",
                    "sender": "assistant",
                    "created_at": "2026-04-13T10:00:00Z",
                    "content": [
                        {
                            "type": "tool_use",
                            "id": "t1",
                            "name": "artifacts",
                            "input": {
                                "command": "create",
                                "id": "a1",
                                "title": "Report",
                                "type": "text/markdown",
                                "content": "# R\n\nRef: https://art.example/page",
                            },
                        },
                        {
                            "type": "tool_result",
                            "tool_use_id": "t1",
                            "name": "artifacts",
                            "content": [{"type": "text", "text": "OK"}],
                        },
                    ],
                },
            ],
        },
    ]


CR_CHAT = Path("chats/2026-04-13/conv-cr.html")
CR_ART = Path("artifacts/conv-cr-1.html")


def _write_fixture(tmp_path, data):
    src = tmp_path / "conversations.json"
    src.write_text(json.dumps(data), encoding="utf-8")
    return src


def _fake_fetcher(pages):
    def fetch(url):
        return pages.get(url)
    return fetch


def test_crawl_rewrites_links_in_chat_page(tmp_path):
    src = _write_fixture(tmp_path, _crawl_fixture())
    out = tmp_path / "out"
    pages = {
        "https://good.example/post":
            "<html><body><article><h1>G</h1><p>Good body text.</p>"
            "</article></body></html>",
    }
    claude2html.convert(
        src, out, crawl_urls=True,
        fetcher=_fake_fetcher(pages), img_fetcher=lambda u: None,
    )
    page = (out / CR_CHAT).read_text(encoding="utf-8")
    assert "../../crawled/" in page
    assert "index.html" in page
    # Blacklisted link stays original
    assert "https://reddit.com/r/python" in page


def test_crawl_rewrites_links_in_artifact_page(tmp_path):
    src = _write_fixture(tmp_path, _crawl_fixture())
    out = tmp_path / "out"
    pages = {
        "https://art.example/page":
            "<html><body><article><h1>A</h1><p>Artifact body text.</p>"
            "</article></body></html>",
    }
    claude2html.convert(
        src, out, crawl_urls=True,
        fetcher=_fake_fetcher(pages), img_fetcher=lambda u: None,
    )
    art = (out / CR_ART).read_text(encoding="utf-8")
    assert "../crawled/" in art
    # Link no longer points to original URL
    assert 'href="https://art.example/page"' not in art


def test_without_crawl_flag_no_downloads(tmp_path):
    src = _write_fixture(tmp_path, _crawl_fixture())
    out = tmp_path / "out"
    calls = []

    def fetch(url):
        calls.append(url)
        return "<html></html>"

    claude2html.convert(src, out, crawl_urls=False,
                        fetcher=fetch, img_fetcher=lambda u: None)
    assert calls == []
    # Original URLs still in the page
    page = (out / CR_CHAT).read_text(encoding="utf-8")
    assert "https://good.example/post" in page


def test_without_crawl_uses_existing_cache(tmp_path):
    """Rerun without --crawl still rewrites links for URLs already cached."""
    src = _write_fixture(tmp_path, _crawl_fixture())
    out = tmp_path / "out"
    pages = {
        "https://good.example/post":
            "<html><body><article><h1>G</h1><p>Good body text.</p>"
            "</article></body></html>",
        "https://art.example/page":
            "<html><body><article><h1>A</h1><p>Artifact body text.</p>"
            "</article></body></html>",
    }
    # First run: crawl
    claude2html.convert(src, out, crawl_urls=True,
                        fetcher=_fake_fetcher(pages), img_fetcher=lambda u: None)
    # Second run: no crawl, but cache still exists
    calls = []

    def fetch(url):
        calls.append(url)
        return None

    claude2html.convert(src, out, crawl_urls=False,
                        fetcher=fetch, img_fetcher=lambda u: None)
    assert calls == []
    page = (out / CR_CHAT).read_text(encoding="utf-8")
    assert "../../crawled/" in page


def test_update_mode_preserves_crawled_dir(tmp_path):
    """Rerunning the converter must not delete the crawled cache."""
    src = _write_fixture(tmp_path, _crawl_fixture())
    out = tmp_path / "out"
    pages = {
        "https://good.example/post":
            "<html><body><article><h1>G</h1><p>Good body.</p>"
            "</article></body></html>",
    }
    claude2html.convert(src, out, crawl_urls=True,
                        fetcher=_fake_fetcher(pages), img_fetcher=lambda u: None)
    crawled_files_before = sorted((out / "crawled").rglob("*.html"))
    assert crawled_files_before

    # Second run without crawling should not remove crawled files
    claude2html.convert(src, out, crawl_urls=False,
                        fetcher=lambda u: None, img_fetcher=lambda u: None)
    crawled_files_after = sorted((out / "crawled").rglob("*.html"))
    assert crawled_files_before == crawled_files_after


def test_crawled_page_has_theme_and_original_link(tmp_path):
    src = _write_fixture(tmp_path, _crawl_fixture())
    out = tmp_path / "out"
    pages = {
        "https://good.example/post":
            "<html><body><article><h1>Gee</h1><p>Real body text here.</p>"
            "</article></body></html>",
    }
    claude2html.convert(src, out, crawl_urls=True,
                        fetcher=_fake_fetcher(pages), img_fetcher=lambda u: None)
    # Find the generated crawled page
    crawled_pages = list((out / "crawled").rglob("index.html"))
    assert len(crawled_pages) == 1
    page = crawled_pages[0].read_text(encoding="utf-8")
    assert 'href="https://good.example/post"' in page  # original link banner
    assert "Real body text" in page
    assert "<style>" in page and "--bg:" in page  # theme CSS inlined
