from __future__ import annotations

import argparse
import sys

from workflow_state import next_prompt


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="Print the next recommended Codex app prompt.")
    parser.add_argument("--chapter", default=None)
    args = parser.parse_args()

    print("# Next Prompt")
    print()
    print("```text")
    print(next_prompt(args.chapter))
    print("```")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
