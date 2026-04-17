"""CLI entry point: ``python -m claude2html <src> -o <out> [--crawl]``."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import convert


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Convert Claude export to HTML.")
    p.add_argument("src", type=Path, help="Path to conversations.json")
    p.add_argument("-o", "--out", type=Path, required=True, help="Output directory")
    p.add_argument(
        "--crawl",
        action="store_true",
        help="Download external links to local readable HTML under out/crawled/",
    )
    args = p.parse_args(argv)
    n = convert(args.src, args.out, crawl_urls=args.crawl)
    print(f"Wrote {n} conversations + index.html to {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
