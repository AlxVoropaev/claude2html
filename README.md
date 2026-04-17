# claude2html

Convert a Claude chat export (`conversations.json`) to a set of offline-
viewable HTML pages. Optionally crawl external links in chats/artifacts to
local readable copies.

## Setup

```bash
uv sync
```

Installs the `claude2html` package plus dev dependencies (`pytest`).

## Usage

```bash
uv run claude2html json/conversations.json -o out/
```

or equivalently:

```bash
uv run python -m claude2html json/conversations.json -o out/
```

Writes one `out/chats/<date>/<uuid>.html` per conversation, an
`out/artifacts/<name>.html` per artifact, and an `out/index.html` listing
them (newest first). Open `out/index.html` in a browser — everything is
self-contained, no network access needed.

Reruns are non-destructive: existing chat/artifact HTML is overwritten, and
the `out/crawled/` cache is append-only.

### Crawling external links

```bash
uv run claude2html json/conversations.json -o out/ --crawl
```

With `--crawl`, URLs mentioned in message text and artifact content are
downloaded, extracted to clean Markdown via [trafilatura][tr], saved as local
HTML under `out/crawled/<hash>/`, and links in chat/artifact pages are
rewritten to point to the local copies. Images in extracted content are
downloaded alongside. The hostname blacklist
(`reddit.com`, `youtube.com`, `youtu.be`) is skipped. Without `--crawl`,
no network is used, but any existing cache under `out/crawled/` is still
used to rewrite links.

Concurrency: 16 parallel downloads, capped at 2 per host.

[tr]: https://trafilatura.readthedocs.io/

## Testing

```bash
uv run pytest
```

## Layout

- [claude2html/__init__.py](claude2html/__init__.py) — `convert()` entry
  point.
- [claude2html/__main__.py](claude2html/__main__.py) — CLI
  (`python -m claude2html`).
- [claude2html/render.py](claude2html/render.py) — HTML rendering
  (uses `mistune` for Markdown).
- [claude2html/crawler.py](claude2html/crawler.py) — URL collection,
  parallel crawler with per-host limits, trafilatura-based extraction,
  local-page rendering.
- [claude2html/assets/](claude2html/assets/) — `style.css`, `theme.js`
  (copied into the output dir).
- [FORMAT.md](FORMAT.md) — notes on the export JSON structure used for
  rendering.
- [tests/test_claude2html.py](tests/test_claude2html.py) — end-to-end
  conversion tests + crawl-flag integration tests.
- [tests/test_crawler.py](tests/test_crawler.py) — unit tests for URL
  collection, blacklist, hashing, and the parallel crawler.

## Scope

- Renders: text, thinking, tool_use (with pretty-printed `input`),
  tool_result (flattened), attachments (name + extracted content), files
  (name only — bytes aren't in the export).
- Text, thinking, and artifact content are rendered as Markdown (headings,
  lists, fenced code, tables, blockquotes, strikethrough, autolinks); raw
  HTML in the source is escaped.
- Four selectable themes (GitHub light/dark, Monokai Pro light/dark) with
  per-page toggle.
- Crawling extracts only URLs from message `text` blocks and artifact
  `content` — `md_citations`, `web_search` results, and `tool_result` bodies
  are not crawled.
- Binary/PDF `files[]` referenced by messages aren't included in the
  export, so only their filenames are shown.

## License

This project is open source and available under the MIT License.
