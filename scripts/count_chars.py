from __future__ import annotations

import argparse
import sys
from pathlib import Path

from _common import ROOT, char_count, non_ws_count, read_text


def main() -> int:
    parser = argparse.ArgumentParser(description="Count characters in UTF-8 text files.")
    parser.add_argument("paths", nargs="+", help="Files to count.")
    args = parser.parse_args()

    exit_code = 0
    for item in args.paths:
        path = Path(item)
        if not path.is_absolute():
            path = ROOT / path
        if not path.exists():
            print(f"{item}: missing", file=sys.stderr)
            exit_code = 1
            continue
        text = read_text(path)
        print(f"{path.relative_to(ROOT)}\traw={char_count(text)}\tnon_ws={non_ws_count(text)}")
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())

