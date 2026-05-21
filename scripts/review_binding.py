from __future__ import annotations

import hashlib
import re
from pathlib import Path

from _common import ROOT, read_text


REVIEW_STATUS_RE = re.compile(r"^\s*status\s*[:：]\s*(.+?)\s*$", re.IGNORECASE | re.MULTILINE)
METADATA_RE_TEMPLATE = r"^\s*{key}\s*[:：]\s*(.*?)\s*$"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def normalized_text(text: str) -> str:
    return "".join(str(text or "").split())


def review_status(text: str) -> str | None:
    match = REVIEW_STATUS_RE.search(text)
    return match.group(1).strip() if match else None


def metadata_value(text: str, key: str) -> str:
    pattern = re.compile(METADATA_RE_TEMPLATE.format(key=re.escape(key)), re.IGNORECASE | re.MULTILINE)
    match = pattern.search(text)
    return match.group(1).strip() if match else ""


def review_body_sha256_text(text: str) -> str:
    filtered = [
        line
        for line in text.splitlines()
        if not line.strip().lower().startswith("review_sha256:")
    ]
    return hashlib.sha256(("\n".join(filtered).rstrip() + "\n").encode("utf-8")).hexdigest()


def review_body_sha256(path: Path) -> str:
    return review_body_sha256_text(read_text(path))


def official_chapter_path(chapter: str) -> Path:
    return ROOT / "chapters" / chapter[:3] / f"c{chapter[-3:]}.md"


def review_bound_to_current_chapter(text: str, official_path: Path) -> bool:
    if not official_path.exists():
        return False
    return metadata_value(text, "official_chapter_sha256") == sha256(official_path)


def review_hash_is_current(text: str, review_path: Path) -> bool:
    expected = metadata_value(text, "review_sha256")
    return bool(expected) and expected == review_body_sha256(review_path)


def accepted_by_human_is_current(text: str, review_path: Path, official_path: Path) -> bool:
    if review_status(text) != "ACCEPTED_BY_HUMAN":
        return False
    if metadata_value(text, "accepted_by") != "human":
        return False
    if not metadata_value(text, "accepted_at"):
        return False
    if not metadata_value(text, "reason"):
        return False
    return review_bound_to_current_chapter(text, official_path) and review_hash_is_current(text, review_path)


def section_body(text: str, heading: str) -> str:
    marker = f"## {heading}"
    if marker not in text:
        return ""
    tail = text.split(marker, 1)[1]
    if "\n## " in tail:
        tail = tail.split("\n## ", 1)[0]
    return tail.strip()


def evidence_quotes(text: str) -> list[str]:
    body = section_body(text, "Evidence Quotes")
    quotes: list[str] = []
    for raw in body.splitlines():
        line = raw.strip()
        if not line or line.startswith("|") or set(line) <= {"-", ":", " "}:
            continue
        line = re.sub(r"^[-*+]\s*", "", line)
        line = re.sub(r"^\d+[.)]\s*", "", line).strip()
        line = line.strip("`").strip()
        if line and line.lower() not in {"none", "n/a"}:
            quotes.append(line)
    return quotes


def quote_matches_text(quote: str, source_text: str) -> bool:
    value = normalized_text(quote)
    if not value:
        return False
    return value in normalized_text(source_text)


def any_quote_matches_official(quotes: list[str], official_path: Path) -> bool:
    if not official_path.exists():
        return False
    source = read_text(official_path)
    return any(quote_matches_text(quote, source) for quote in quotes)


def validate_markdown_review_binding(
    *,
    chapter: str,
    review_path: Path,
    require_quote: bool = True,
    allowed_statuses: set[str] | None = None,
) -> list[str]:
    allowed = allowed_statuses or {"CLEAR", "ACCEPTED_BY_HUMAN"}
    text = read_text(review_path)
    status = review_status(text)
    failures: list[str] = []
    if status not in allowed:
        failures.append(
            f"{chapter}: review {review_path.relative_to(ROOT)} status is {status or 'MISSING'}; "
            f"expected one of {sorted(allowed)}"
        )
        return failures
    official = official_chapter_path(chapter)
    if status == "CLEAR":
        if not review_bound_to_current_chapter(text, official):
            failures.append(f"{chapter}: review {review_path.relative_to(ROOT)} official chapter hash is missing or stale")
        if not review_hash_is_current(text, review_path):
            failures.append(f"{chapter}: review {review_path.relative_to(ROOT)} review_sha256 is missing or stale")
        if require_quote:
            quotes = evidence_quotes(text)
            if not quotes:
                failures.append(f"{chapter}: review {review_path.relative_to(ROOT)} has no Evidence Quotes")
            elif not any_quote_matches_official(quotes, official):
                failures.append(f"{chapter}: review {review_path.relative_to(ROOT)} Evidence Quotes do not match the official chapter")
    if status == "ACCEPTED_BY_HUMAN" and not accepted_by_human_is_current(text, review_path, official):
        failures.append(f"{chapter}: review {review_path.relative_to(ROOT)} human acceptance is missing or stale")
    return failures


def markdown_review_with_hash(content: str) -> str:
    if "review_sha256:" not in content:
        content = content.replace("official_chapter_sha256:", "official_chapter_sha256:\nreview_sha256:", 1)
    digest = review_body_sha256_text(content)
    return re.sub(r"^review_sha256\s*[:：].*$", f"review_sha256: {digest}", content, flags=re.MULTILINE)
