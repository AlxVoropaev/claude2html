#!/usr/bin/env python3
"""Convert a Claude chat export (conversations.json) to offline HTML pages.

Usage: python claude2html.py <conversations.json> -o <out_dir>
"""

from __future__ import annotations

import argparse
import html
import json
import shutil
import sys
from pathlib import Path

import mistune

_md = mistune.create_markdown(escape=True, plugins=["strikethrough", "table", "url"])

ASSETS_DIR = Path(__file__).resolve().parent / "assets"

THEMES = [
    ("github-light", "GitHub Light"),
    ("github-dark", "GitHub Dark"),
    ("monokai-pro-light", "Monokai Pro Light"),
    ("monokai-pro-dark", "Monokai Pro Dark"),
]

E = html.escape


def _render_text_block(block: dict) -> str:
    return f'<div class="block"><div class="md">{_md(block.get("text", ""))}</div></div>'


def _render_thinking(block: dict) -> str:
    return (
        '<div class="block thinking"><details>'
        "<summary>thinking</summary>"
        f'<div class="md">{_md(block.get("thinking", ""))}</div>'
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


def _theme_selector() -> str:
    options = "".join(
        f'<option value="{E(value)}">{E(label)}</option>'
        for value, label in THEMES
    )
    return f'<select id="theme-select" aria-label="Theme">{options}</select>'


def _page(title: str, body: str, asset_prefix: str = "") -> str:
    return (
        "<!DOCTYPE html><html><head>"
        f'<meta charset="utf-8"><title>{E(title)}</title>'
        f'<link rel="stylesheet" href="{asset_prefix}assets/style.css">'
        f'<script src="{asset_prefix}assets/theme.js"></script>'
        "</head><body>"
        f"{_theme_selector()}"
        f"{body}"
        "</body></html>"
    )


def _conv_date(conv: dict) -> str:
    return (conv.get("updated_at", "") or "")[:10] or "undated"


def _render_conversation(conv: dict) -> str:
    title = _conv_title(conv)
    header = (
        f"<h1>{E(title)}</h1>"
        f'<div class="meta">Created {E(conv.get("created_at", ""))} · '
        f'Updated {E(conv.get("updated_at", ""))}</div>'
        '<p><a href="../../index.html">← Index</a></p>'
    )
    msgs = "".join(_render_message(m) for m in conv.get("chat_messages") or [])
    return _page(title, header + msgs, asset_prefix="../../")


def _render_index(convs: list[dict]) -> str:
    ordered = sorted(convs, key=lambda c: c.get("updated_at", ""), reverse=True)
    groups: dict[str, list[dict]] = {}
    for c in ordered:
        groups.setdefault(_conv_date(c), []).append(c)
    sections = []
    for date in sorted(groups, reverse=True):
        items = "".join(
            f'<li><a href="chats/{E(_conv_date(c))}/{E(c["uuid"])}.html">'
            f"{E(_conv_title(c))}</a></li>"
            for c in groups[date]
        )
        sections.append(
            f"<h2>{E(date)}</h2>"
            f'<ul class="index">{items}</ul>'
        )
    body = f"<h1>Claude chats ({len(convs)})</h1>" + "".join(sections)
    return _page("Claude chats", body)


def _copy_assets(out: Path) -> None:
    shutil.copytree(ASSETS_DIR, out / "assets", dirs_exist_ok=True)


def convert(src: Path, out: Path) -> int:
    with src.open(encoding="utf-8") as f:
        convs = json.load(f)
    out.mkdir(parents=True, exist_ok=True)
    _copy_assets(out)
    for conv in convs:
        chat_dir = out / "chats" / _conv_date(conv)
        chat_dir.mkdir(parents=True, exist_ok=True)
        (chat_dir / f"{conv['uuid']}.html").write_text(
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
