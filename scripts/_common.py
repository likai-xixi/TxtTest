from __future__ import annotations

import re
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CHAPTER_RE = re.compile(r"^v(?P<volume>\d{2})_c(?P<chapter>\d{3})$")


def chapter_parts(chapter: str) -> tuple[str, str]:
    match = CHAPTER_RE.match(chapter)
    if not match:
        raise ValueError(f"Invalid chapter id: {chapter}. Expected vNN_cNNN.")
    volume = f"v{match.group('volume')}"
    chapter_file = f"c{match.group('chapter')}.md"
    return volume, chapter_file


def read_text(path: Path, default: str = "") -> str:
    if not path.exists():
        return default
    return path.read_text(encoding="utf-8")


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def char_count(text: str) -> int:
    return len(text)


def non_ws_count(text: str) -> int:
    return len(re.sub(r"\s+", "", text))


def truncate(text: str, limit: int) -> str:
    text = text.strip()
    if len(text) <= limit:
        return text
    return text[: limit - 20].rstrip() + "\n...[truncated]"


def posix(path: Path | str) -> str:
    return str(path).replace("\\", "/")


def chapter_number(chapter: str) -> int:
    match = CHAPTER_RE.match(chapter)
    if not match:
        raise ValueError(f"Invalid chapter id: {chapter}")
    return int(match.group("chapter"))

