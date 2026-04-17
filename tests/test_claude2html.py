"""Tests for the claude2html converter (v1)."""

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "claude2html.py"


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
        [sys.executable, str(SCRIPT), str(src), "-o", str(out)],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    return out


AAA = Path("chats/2026-04-10/conv-aaa.html")
BBB = Path("chats/2026-04-11/conv-bbb.html")


def test_output_layout(tmp_path):
    out = _run(tmp_path)
    assert (out / "index.html").is_file()
    assert (out / AAA).is_file()
    assert (out / BBB).is_file()
    html_files = sorted(str(p.relative_to(out)) for p in out.rglob("*.html"))
    assert html_files == [str(AAA), str(BBB), "index.html"]


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
    # Assets are referenced via relative paths and shipped under out/assets/
    assert 'href="../../assets/style.css"' in page
    assert 'src="../../assets/theme.js"' in page
    head = page.split("</head>")[0]
    assert "http://" not in head
    assert "https://" not in head
    assert (out / "assets" / "style.css").is_file()
    assert (out / "assets" / "theme.js").is_file()


def test_index_references_assets(tmp_path):
    out = _run(tmp_path)
    idx = (out / "index.html").read_text(encoding="utf-8")
    assert 'href="assets/style.css"' in idx
    assert 'src="assets/theme.js"' in idx


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
