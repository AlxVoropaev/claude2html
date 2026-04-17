#!/usr/bin/env python3
"""Convert a Claude chat export (conversations.json) to offline HTML pages.

Usage: python claude2html.py <conversations.json> -o <out_dir>
"""

from __future__ import annotations

import argparse
import html
import json
import sys
from pathlib import Path

CSS = """
body { font-family: -apple-system, Segoe UI, sans-serif; max-width: 900px;
       margin: 2em auto; padding: 0 1em; color: #222; }
h1 { margin-bottom: 0.2em; }
.meta { color: #666; font-size: 0.9em; margin-bottom: 2em; }
.msg { border: 1px solid #ddd; border-radius: 6px; padding: 0.8em 1em;
       margin: 0.8em 0; }
.msg.human { background: #f5f7fb; }
.msg.assistant { background: #fff; }
.role { font-weight: 600; text-transform: uppercase; font-size: 0.75em;
        letter-spacing: 0.05em; color: #555; }
.ts { color: #999; font-size: 0.8em; margin-left: 0.5em; }
.block { margin: 0.6em 0; }
.block pre, .text { white-space: pre-wrap; word-wrap: break-word;
                    font-family: inherit; margin: 0; }
.tool { border-left: 3px solid #4a90e2; padding: 0.4em 0.8em;
        background: #f0f6ff; font-size: 0.92em; }
.tool.error { border-left-color: #e24a4a; background: #fff0f0; }
.tool-name { font-family: monospace; font-weight: 600; color: #2a5ca0; }
.thinking { border-left: 3px solid #aaa; padding: 0.4em 0.8em;
            background: #fafafa; color: #555; font-style: italic; }
.thinking summary { cursor: pointer; font-style: normal; color: #666; }
.attachments { border-top: 1px dashed #ccc; margin-top: 0.8em; padding-top: 0.6em;
               font-size: 0.9em; }
.attach-name { font-family: monospace; }
pre.input { background: #eef; padding: 0.5em; border-radius: 4px; overflow-x: auto; }
ul.index { list-style: none; padding: 0; }
ul.index li { padding: 0.4em 0; border-bottom: 1px solid #eee; }
ul.index a { text-decoration: none; color: #2a5ca0; font-weight: 500; }
ul.index .date { color: #888; font-size: 0.85em; margin-left: 0.5em; }
"""

E = html.escape


def _render_text_block(block: dict) -> str:
    return f'<div class="block"><div class="text">{E(block.get("text", ""))}</div></div>'


def _render_thinking(block: dict) -> str:
    body = E(block.get("thinking", ""))
    return (
        '<div class="block thinking"><details>'
        "<summary>thinking</summary>"
        f'<div class="text">{body}</div>'
        "</details></div>"
    )


def _render_tool_use(block: dict) -> str:
    name = E(block.get("name") or "tool")
    try:
        pretty = json.dumps(block.get("input", {}), indent=2, ensure_ascii=False)
    except (TypeError, ValueError):
        pretty = str(block.get("input", ""))
    return (
        '<div class="block tool">'
        f'<div><span class="tool-name">→ {name}</span></div>'
        f'<pre class="input">{E(pretty)}</pre>'
        "</div>"
    )


def _render_tool_result(block: dict) -> str:
    name = E(block.get("name") or "tool")
    err_cls = " error" if block.get("is_error") else ""
    parts = [f'<div class="block tool{err_cls}">',
             f'<div><span class="tool-name">← {name}</span></div>']
    items = block.get("content") or []
    for item in items:
        title = item.get("title")
        url = item.get("url")
        text = item.get("text", "")
        if title or url:
            parts.append('<div style="margin-top:0.4em">')
            if title:
                parts.append(f'<div><strong>{E(title)}</strong></div>')
            if url:
                parts.append(f'<div><a href="{E(url)}">{E(url)}</a></div>')
            if text:
                parts.append(f'<div class="text">{E(text)}</div>')
            parts.append("</div>")
        else:
            parts.append(f'<div class="text">{E(text)}</div>')
    parts.append("</div>")
    return "".join(parts)


RENDERERS = {
    "text": _render_text_block,
    "thinking": _render_thinking,
    "tool_use": _render_tool_use,
    "tool_result": _render_tool_result,
}


def _render_attachments(msg: dict) -> str:
    atts = msg.get("attachments") or []
    files = msg.get("files") or []
    if not atts and not files:
        return ""
    parts = ['<div class="attachments">']
    for a in atts:
        parts.append(
            f'<div>📎 <span class="attach-name">{E(a.get("file_name", ""))}</span>'
            f' ({E(str(a.get("file_size", "")))} bytes)</div>'
        )
        content = a.get("extracted_content")
        if content:
            parts.append(f'<pre class="input">{E(content)}</pre>')
    for f in files:
        parts.append(
            f'<div>📄 <span class="attach-name">{E(f.get("file_name", ""))}</span>'
            " (binary, not in export)</div>"
        )
    parts.append("</div>")
    return "".join(parts)


def _render_message(msg: dict) -> str:
    sender = msg.get("sender", "unknown")
    ts = E(msg.get("created_at", ""))
    blocks = []
    for block in msg.get("content", []) or []:
        renderer = RENDERERS.get(block.get("type"))
        if renderer:
            blocks.append(renderer(block))
    blocks.append(_render_attachments(msg))
    return (
        f'<div class="msg {E(sender)}">'
        f'<div><span class="role">{E(sender)}</span>'
        f'<span class="ts">{ts}</span></div>'
        + "".join(blocks)
        + "</div>"
    )


def _conv_title(conv: dict) -> str:
    return conv.get("name") or "Untitled"


def _page(title: str, body: str) -> str:
    return (
        "<!DOCTYPE html><html><head>"
        f'<meta charset="utf-8"><title>{E(title)}</title>'
        f"<style>{CSS}</style>"
        "</head><body>"
        f"{body}"
        "</body></html>"
    )


def _render_conversation(conv: dict) -> str:
    title = _conv_title(conv)
    header = (
        f"<h1>{E(title)}</h1>"
        f'<div class="meta">Created {E(conv.get("created_at", ""))} · '
        f'Updated {E(conv.get("updated_at", ""))}</div>'
        '<p><a href="index.html">← Index</a></p>'
    )
    msgs = "".join(_render_message(m) for m in conv.get("chat_messages") or [])
    return _page(title, header + msgs)


def _render_index(convs: list[dict]) -> str:
    ordered = sorted(convs, key=lambda c: c.get("updated_at", ""), reverse=True)
    items = []
    for c in ordered:
        items.append(
            f'<li><a href="{E(c["uuid"])}.html">{E(_conv_title(c))}</a>'
            f'<span class="date">{E(c.get("updated_at", "")[:10])}</span></li>'
        )
    body = (
        f"<h1>Claude chats ({len(convs)})</h1>"
        f'<ul class="index">{"".join(items)}</ul>'
    )
    return _page("Claude chats", body)


def convert(src: Path, out: Path) -> int:
    with src.open(encoding="utf-8") as f:
        convs = json.load(f)
    out.mkdir(parents=True, exist_ok=True)
    for conv in convs:
        (out / f"{conv['uuid']}.html").write_text(
            _render_conversation(conv), encoding="utf-8"
        )
    (out / "index.html").write_text(_render_index(convs), encoding="utf-8")
    return len(convs)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Convert Claude export to HTML.")
    p.add_argument("src", type=Path, help="Path to conversations.json")
    p.add_argument("-o", "--out", type=Path, required=True, help="Output directory")
    args = p.parse_args(argv)
    n = convert(args.src, args.out)
    print(f"Wrote {n} conversations + index.html to {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
