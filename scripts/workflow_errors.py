from __future__ import annotations

import sys
from typing import Any


CATEGORIES = {"BLOCKER", "MISSING", "STALE", "POLICY", "IO", "API", "SCHEMA"}


def normalize_category(category: str) -> str:
    category = category.upper()
    if category not in CATEGORIES:
        return "BLOCKER"
    return category


def issue(category: str, message: str, path: str | None = None) -> dict[str, Any]:
    item: dict[str, Any] = {"category": normalize_category(category), "message": message}
    if path:
        item["path"] = path
    return item


def format_issue(category: str, message: str, path: str | None = None) -> str:
    prefix = normalize_category(category)
    if path:
        return f"{prefix}: {path}: {message}"
    return f"{prefix}: {message}"


def print_issue(category: str, message: str, path: str | None = None, *, stream: Any = None) -> None:
    print(format_issue(category, message, path), file=stream or sys.stderr)


def print_issues(items: list[dict[str, Any]], *, stream: Any = None) -> None:
    for item in items:
        print_issue(
            str(item.get("category", "BLOCKER")),
            str(item.get("message", "")),
            str(item.get("path")) if item.get("path") else None,
            stream=stream,
        )

