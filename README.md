# claude2html

Convert a Claude chat export (`conversations.json`) to a set of offline-
viewable HTML pages.

## Setup

```bash
uv sync
```

Creates a `.venv` with the project's dev dependencies (`pytest`).

## Usage

```bash
uv run python claude2html.py json/conversations.json -o out/
```

Writes one `out/<conversation-uuid>.html` per conversation plus an
`out/index.html` listing them (newest first). Open `out/index.html` in a
browser — everything is self-contained, no network access needed.

## Testing

```bash
uv run pytest
```

## Layout

- [claude2html.py](claude2html.py) — single-file converter (uses `mistune` for
  Markdown rendering).
- [FORMAT.md](FORMAT.md) — notes on the export JSON structure used for
  rendering.
- [tests/test_claude2html.py](tests/test_claude2html.py) — tests covering
  every content-block type (`text`, `thinking`, `tool_use`, `tool_result`),
  HTML escaping, attachments, and the index page.

## Scope of v1

- Renders: text, thinking, tool_use (with pretty-printed `input`),
  tool_result (flattened), attachments (name + extracted content), files
  (name only — bytes aren't in the export).
- Text and thinking blocks are rendered as Markdown (headings, lists,
  fenced code, tables, blockquotes, strikethrough, autolinks); raw HTML
  in the source is escaped.
- Citations are not linked in the rendered text yet.
- Binary/PDF `files[]` referenced by messages aren't included in the
  export, so only their filenames are shown.

## License

This project is open source and available under the MIT License.
