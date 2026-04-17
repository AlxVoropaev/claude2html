"""HTML rendering for Claude chat exports."""

from __future__ import annotations

import html
import json
import shutil
from pathlib import Path

import mistune

ASSETS_DIR = Path(__file__).resolve().parent / "assets"

THEMES = [
    ("github-light", "GitHub Light"),
    ("github-dark", "GitHub Dark"),
    ("monokai-pro-light", "Monokai Pro Light"),
    ("monokai-pro-dark", "Monokai Pro Dark"),
]

E = html.escape


def make_md(link_map: dict[str, str] | None = None, link_prefix: str = ""):
    """Create a mistune markdown renderer that rewrites known links to local paths."""
    lm = link_map or {}

    class _R(mistune.HTMLRenderer):
        def link(self, text: str, url: str, title=None) -> str:
            local = lm.get(url)
            if local:
                url = link_prefix + local
            return super().link(text, url, title)

    return mistune.create_markdown(
        renderer=_R(escape=True),
        plugins=["strikethrough", "table", "url"],
    )


_DEFAULT_MD = make_md()


def _render_text_block(block: dict, md) -> str:
    return f'<div class="block"><div class="md">{md(block.get("text", ""))}</div></div>'


def _render_thinking(block: dict, md) -> str:
    return (
        '<div class="block thinking"><details>'
        "<summary>thinking</summary>"
        f'<div class="md">{md(block.get("thinking", ""))}</div>'
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


def _render_tool_result_items(items: list) -> str:
    parts = []
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
    return "".join(parts)


def _render_tool_result(block: dict) -> str:
    name = E(block.get("name") or "tool")
    err_cls = " error" if block.get("is_error") else ""
    body = _render_tool_result_items(block.get("content") or [])
    return (
        f'<div class="block tool{err_cls}">'
        f'<div><span class="tool-name">← {name}</span></div>'
        f"{body}"
        "</div>"
    )


def _collapsed_summary(use: dict) -> str | None:
    name = use.get("name")
    inp = use.get("input") or {}
    if name == "web_search":
        return f"🔍 {E(inp.get('query', '') or 'web_search')}"
    if name == "web_fetch":
        return f"🌐 {E(inp.get('url', '') or 'web_fetch')}"
    return None


def _render_collapsed_pair(use: dict, result: dict, summary: str) -> str:
    err_cls = " error" if result.get("is_error") else ""
    body = _render_tool_result_items(result.get("content") or [])
    return (
        f'<div class="block tool{err_cls}"><details>'
        f"<summary>{summary}</summary>"
        f"{body}"
        "</details></div>"
    )


def _render_artifact_link(use: dict, href: str) -> str:
    title = E((use.get("input") or {}).get("title") or "Artifact")
    return (
        '<div class="block tool">'
        f'<div>📄 <a href="{E(href)}">{title}</a></div>'
        "</div>"
    )


def _cit_fields(cit: dict) -> tuple[str, str, str]:
    meta = cit.get("metadata") or {}
    src0 = (cit.get("sources") or [{}])[0] or {}
    icon = meta.get("icon_url") or src0.get("icon_url") or ""
    site = meta.get("source") or src0.get("source") or ""
    title = meta.get("preview_title") or src0.get("title") or cit.get("title") or ""
    return icon, title, site


def _render_md_citations(citations: list) -> str:
    seen: set[str] = set()
    items: list[str] = []
    for cit in citations:
        url = cit.get("url") or ""
        if not url or url in seen:
            continue
        seen.add(url)
        icon, title, site = _cit_fields(cit)
        title = title or url
        parts = []
        if icon:
            parts.append(f'<img class="cit-icon" src="{E(icon)}" alt="" />')
        parts.append(f'<a href="{E(url)}">{E(title)}</a>')
        if site:
            parts.append(f'<span class="cit-site">({E(site)})</span>')
        items.append(f'<li>{" ".join(parts)}</li>')
    if not items:
        return ""
    return (
        '<details class="block tool"><summary>'
        f"Sources ({len(items)})"
        f'</summary><ul class="citations">{"".join(items)}</ul></details>'
    )


def _render_artifact_page(use: dict, back_href: str, md) -> str:
    inp = use.get("input") or {}
    title = inp.get("title") or "Artifact"
    content = inp.get("content") or ""
    citations = inp.get("md_citations") or []
    body = (
        f'<p><a href="{E(back_href)}">← Back to chat</a> · '
        '<a href="index.html">Artifacts</a> · '
        '<a href="../index.html">Chats</a></p>'
        f"<h1>{E(title)}</h1>"
        f'<div class="md">{md(content)}</div>'
        f"{_render_md_citations(citations)}"
    )
    return _page(title, body, asset_prefix="../")


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


def _is_pair(block: dict, nxt: dict | None, name: str) -> bool:
    return (
        block.get("type") == "tool_use"
        and block.get("name") == name
        and nxt is not None
        and nxt.get("type") == "tool_result"
        and nxt.get("name") == name
    )


def _render_message(msg: dict, emit_artifact, md) -> str:
    sender = msg.get("sender", "unknown")
    ts = E(msg.get("created_at", ""))
    content = msg.get("content", []) or []
    blocks = []
    i = 0
    while i < len(content):
        block = content[i]
        nxt = content[i + 1] if i + 1 < len(content) else None
        name = block.get("name")
        btype = block.get("type")
        if btype in ("tool_use", "tool_result") and name in (
            "launch_extended_search_task",
            "ask_user_input_v0",
        ):
            i += 1
            continue
        if (
            btype == "tool_use"
            and name in ("web_search", "web_fetch")
            and nxt is not None
            and nxt.get("type") == "tool_result"
            and nxt.get("tool_use_id") == block.get("id")
        ):
            blocks.append(
                _render_collapsed_pair(block, nxt, _collapsed_summary(block) or E(name))
            )
            i += 2
            continue
        if btype == "tool_use" and name == "artifacts":
            href = emit_artifact(block)
            blocks.append(_render_artifact_link(block, href))
            i += 2 if _is_pair(block, nxt, "artifacts") else 1
            continue
        if btype == "tool_result" and name == "artifacts":
            i += 1
            continue
        if btype == "text":
            blocks.append(_render_text_block(block, md))
        elif btype == "thinking":
            blocks.append(_render_thinking(block, md))
        elif btype == "tool_use":
            blocks.append(_render_tool_use(block))
        elif btype == "tool_result":
            blocks.append(_render_tool_result(block))
        i += 1
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


def render_conversation(
    conv: dict,
    artifacts_dir: Path,
    artifacts: list,
    link_map: dict[str, str] | None = None,
) -> str:
    title = _conv_title(conv)
    date = _conv_date(conv)
    header = (
        f"<h1>{E(title)}</h1>"
        f'<div class="meta">Created {E(conv.get("created_at", ""))} · '
        f'Updated {E(conv.get("updated_at", ""))}</div>'
        '<p><a href="../../index.html">← Chats</a> · '
        '<a href="../../artifacts/index.html">Artifacts</a></p>'
    )
    conv_uuid = conv["uuid"]
    back_href = f"../chats/{date}/{conv_uuid}.html"
    counter = [0]
    md_chat = make_md(link_map, link_prefix="../../")
    md_art = make_md(link_map, link_prefix="../")

    def emit_artifact(use: dict) -> str:
        counter[0] += 1
        fname = f"{conv_uuid}-{counter[0]}.html"
        (artifacts_dir / fname).write_text(
            _render_artifact_page(use, back_href, md_art), encoding="utf-8"
        )
        art_title = (use.get("input") or {}).get("title") or "Artifact"
        artifacts.append(
            {
                "file": fname,
                "title": art_title,
                "chat_title": title,
                "chat_date": date,
                "chat_uuid": conv_uuid,
            }
        )
        return f"../../artifacts/{fname}"

    msgs = "".join(
        _render_message(m, emit_artifact, md_chat)
        for m in conv.get("chat_messages") or []
    )
    return _page(title, header + msgs, asset_prefix="../../")


def render_index(convs: list[dict], n_artifacts: int) -> str:
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
    body = (
        f'<p><a href="artifacts/index.html">Artifacts ({n_artifacts}) →</a></p>'
        f"<h1>Claude chats ({len(convs)})</h1>"
        + "".join(sections)
    )
    return _page("Claude chats", body)


def render_artifact_index(artifacts: list) -> str:
    groups: dict[str, list[dict]] = {}
    for a in artifacts:
        groups.setdefault(a["chat_date"], []).append(a)
    sections = []
    for date in sorted(groups, reverse=True):
        items = "".join(
            f'<li><a href="{E(a["file"])}">{E(a["title"])}</a> '
            '<span class="meta">— '
            f'<a href="../chats/{E(a["chat_date"])}/{E(a["chat_uuid"])}.html">'
            f'{E(a["chat_title"])}</a></span></li>'
            for a in groups[date]
        )
        sections.append(
            f"<h2>{E(date)}</h2>"
            f'<ul class="index">{items}</ul>'
        )
    body = (
        '<p><a href="../index.html">← Chats</a></p>'
        f"<h1>Artifacts ({len(artifacts)})</h1>"
        + "".join(sections)
    )
    return _page("Artifacts", body, asset_prefix="../")


def copy_assets(out: Path) -> None:
    shutil.copytree(ASSETS_DIR, out / "assets", dirs_exist_ok=True)


def conv_date(conv: dict) -> str:
    return _conv_date(conv)
