# Claude export — JSON format

Notes from the actual export in [json/](json/). Only fields needed for
rendering are listed; trivia like UUIDs and signatures are mentioned but not
considered load-bearing for v1.

## Files in the export

| File | Size | Needed for rendering |
|------|------|----------------------|
| `conversations.json` | ~18 MB | **yes** — the chats |
| `projects.json` | ~24 KB | no (v1) |
| `memories.json` | ~16 KB | no (v1) |
| `users.json` | ~4 KB | no — single-user account metadata |

## `conversations.json`

Top level: JSON array. In this export: 103 conversations, 617 messages total.

Each conversation:

```
{
  "uuid": "...",
  "name": "...",            # may be "" (14 of 103)
  "summary": "",            # empty in all samples
  "created_at": "ISO-8601 Z",
  "updated_at": "ISO-8601 Z",
  "account": {"uuid": "..."},
  "chat_messages": [ ... ]  # ordered
}
```

Names are **not unique** (duplicates exist, 14 empty).

### Message

```
{
  "uuid": "...",
  "text": "<flattened text>",     # == concat of content[].text for text blocks
  "content": [ ... ],             # the real payload
  "sender": "human" | "assistant",
  "created_at": "ISO-8601 Z",
  "updated_at": "ISO-8601 Z",
  "attachments": [ ... ],         # rare: 3/617
  "files": [ ... ],               # rare: 11/617
  "parent_message_uuid": "..."    # threading; in practice messages are in order
}
```

Observed: senders split ~50/50 human/assistant. `msg.text` equals the single
`content[0].text` for every text-only message — we don't need both.

### Content block types (observed)

| type | count | Notes |
|------|-------|-------|
| `text`        | 683 | `.text` (markdown-ish), `.citations` (list, can be empty) |
| `tool_use`    | 259 | `.name`, `.input` (dict), `.message`, plus MCP/approval fields (null for non-MCP) |
| `tool_result` | 255 | `.tool_use_id`, `.name`, `.content` (list of `{type,text,...}`), `.is_error` |
| `thinking`    |   3 | `.thinking` (raw CoT text), `.summaries` (list of `{summary}`) |

Common to all blocks: `start_timestamp`, `stop_timestamp`, `flags`, `type`.

Tools seen (top): `web_search` (343), `web_fetch` (46), `memory_user_edits`
(30), `launch_extended_search_task` (18), `artifacts` (18),
`ask_user_input_v0` (18), `visualize:show_widget` (16), `visualize:read_me`
(12), `view` (6), `create_file` (3), `present_files` (2), `recent_chats` (2).

`tool_result.content[]` items commonly look like search hits:
`{type:"knowledge", title, url, metadata, text, is_citable, ...}` or plain
`{type:"text", text}`. Nested `text` is the user-visible payload.

`display_content` is non-null for 42 blocks; `structured_content` and
`context` are always null in this export — ignore for v1.

### Text & citations

Text blocks contain Markdown (headings, bold, tables, lists, code fences).

`citations[]` entries:
```
{
  "uuid": "...",
  "start_index": <int>,    # offset into text
  "end_index":   <int>,
  "details": {"type": "web_search_citation", "url": "..."}
}
```

### Attachments vs files

- `attachments[]`: text-like pastes with `file_name`, `file_size`,
  `file_type`, `extracted_content` (full plaintext).
- `files[]`: binary/PDF uploads with `file_uuid` + `file_name` only — the
  bytes are **not** in the export.

## v1 rendering contract

The script only needs, per message:

1. `sender` (role label)
2. `created_at` (timestamp)
3. `content[]` — render by `type`:
   - `text` → markdown → HTML (citations optional in v1)
   - `tool_use` → `name` + pretty-printed `input`
   - `tool_result` → flatten `content[].text`
   - `thinking` → collapsible block with `.thinking`
4. `attachments[].file_name` / `files[].file_name` — listed, content shown
   for attachments, name-only for files.

Per conversation: `name` (fallback "Untitled"), `created_at`, `updated_at`,
a stable slug (uuid is the safe choice — names aren't unique).
