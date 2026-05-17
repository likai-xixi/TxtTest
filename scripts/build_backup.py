from __future__ import annotations

import argparse
import zipfile
from pathlib import Path

from _common import ROOT, now_iso


EXCLUDE_PARTS = {".git", "exports", "backups", "__pycache__"}


def should_include(path: Path) -> bool:
    rel = path.relative_to(ROOT)
    if any(part in EXCLUDE_PARTS for part in rel.parts):
        return False
    if path.name.endswith(".raw.json") or path.name.endswith(".prompt.md"):
        return False
    if path.name == ".env":
        return False
    return path.is_file()


def main() -> int:
    parser = argparse.ArgumentParser(description="Create a zip backup without secrets or raw API JSON.")
    parser.add_argument("--label", default="manual")
    args = parser.parse_args()

    stamp = now_iso().replace(":", "").replace("+", "Z")
    out = ROOT / "backups" / f"{stamp}_{args.label}.zip"
    out.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(out, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in ROOT.rglob("*"):
            if should_include(path):
                archive.write(path, path.relative_to(ROOT).as_posix())
    print(f"OK: wrote {out.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
