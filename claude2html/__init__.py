"""Convert a Claude chat export (conversations.json) to offline HTML pages.

The output directory is updated in place: existing chat/artifact HTML files are
overwritten, but the ``crawled/`` cache is append-only across runs.
"""

from __future__ import annotations

import json
import zipfile
from pathlib import Path

from . import crawler, render


def _load_conversations(src: Path) -> list:
    if zipfile.is_zipfile(src):
        with zipfile.ZipFile(src) as z, z.open("conversations.json") as f:
            return json.load(f)
    with src.open(encoding="utf-8") as f:
        return json.load(f)


def convert(
    src: Path,
    out: Path,
    crawl_urls: bool = False,
    fetcher=None,
    img_fetcher=None,
) -> int:
    convs = _load_conversations(src)

    out.mkdir(parents=True, exist_ok=True)
    render.copy_assets(out)

    if crawl_urls:
        urls = crawler.collect_urls(convs)
        link_map = crawler.crawl(
            urls, out, fetcher=fetcher, img_fetcher=img_fetcher
        )
    else:
        link_map = crawler.load_link_map(out)

    artifacts_dir = out / "artifacts"
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    artifacts: list[dict] = []
    for conv in convs:
        chat_dir = out / "chats" / render.conv_date(conv)
        chat_dir.mkdir(parents=True, exist_ok=True)
        (chat_dir / f"{conv['uuid']}.html").write_text(
            render.render_conversation(conv, artifacts_dir, artifacts, link_map),
            encoding="utf-8",
        )

    (out / "index.html").write_text(
        render.render_index(convs, len(artifacts)), encoding="utf-8"
    )
    (artifacts_dir / "index.html").write_text(
        render.render_artifact_index(artifacts), encoding="utf-8"
    )
    return len(convs)


__all__ = ["convert", "crawler", "render"]
