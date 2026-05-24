from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

from _common import ROOT
from context_governance import sha256


REGISTRY = ROOT / "ops" / "return_code_registry.json"
IGNORED_DIRS = {".git", "__pycache__", ".pytest_cache", "backups", "exports"}
IGNORED_SUFFIXES = {".pyc", ".zip"}
ENCODING_TARGETS = [
    ROOT / "README.md",
    ROOT / "AGENTS.md",
    ROOT / "docs",
    ROOT / "ops",
    ROOT / "templates",
    ROOT / "state" / "gates",
]
MOJIBAKE_MARKERS = (
    "\ufffd",
    "锟",
    "脙",
    "脗",
    "瀵板懎",
    "瀵板懓",
    "瀵板懐",
    "瀵板懍",
    "娑撯",
    "娑撴",
    "閺嶇",
    "鐠囨",
    "閺傞",
)
CLONE_FORBIDDEN_PATTERNS = (
    "state/idea_lab/*/*.json",
    "state/idea_lab/*/*.md",
    "external_runs/deepseek/*/*.raw.json",
    "external_runs/deepseek/*/*.manifest.json",
    "external_runs/deepseek/*/*.md",
    "external_runs/codex/*/*.manifest.json",
    "external_runs/codex/*/*.md",
    "reviews/*/decision.md",
    "reviews/*/chapter_landing.json",
    "reviews/*/candidate_selection.md",
    "reader_tests/chapter_feedback/*/*.json",
    "reader_tests/responses/*/*.json",
    "state/shadow/*/*.json",
    "state/shadow/*/*.md",
)


def load_registry() -> dict[str, Any]:
    return json.loads(REGISTRY.read_text(encoding="utf-8"))


def run(repo: Path, args: list[str]) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8:replace"
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    return subprocess.run(
        [sys.executable, "scripts/novel.py", *args],
        cwd=repo,
        text=True,
        capture_output=True,
        encoding="utf-8",
        errors="replace",
        env=env,
    )


def expectation_matches(returncode: int, expectation: str) -> bool:
    if expectation == "zero":
        return returncode == 0
    if expectation == "nonzero":
        return returncode != 0
    if expectation == "any":
        return True
    return False


def value_at_path(data: Any, path: str) -> Any:
    current = data
    for part in path.split("."):
        if not isinstance(current, dict) or part not in current:
            return None
        current = current[part]
    return current


def file_snapshot(repo: Path) -> dict[str, str]:
    snapshot: dict[str, str] = {}
    for path in sorted(repo.rglob("*")):
        if not path.is_file():
            continue
        rel = path.relative_to(repo).as_posix()
        parts = set(Path(rel).parts)
        if parts & IGNORED_DIRS:
            continue
        if path.suffix in IGNORED_SUFFIXES:
            continue
        snapshot[rel] = sha256(path)
    return snapshot


def copy_to_temp() -> tuple[Path, Path]:
    temp_root = Path(tempfile.mkdtemp(prefix="novel_contracts_"))
    repo = temp_root / "repo"
    shutil.copytree(
        ROOT,
        repo,
        ignore=shutil.ignore_patterns(".git", "__pycache__", "*.pyc", ".pytest_cache", "backups", "exports", "*.zip"),
    )
    return temp_root, repo


def check_return_codes() -> list[str]:
    errors: list[str] = []
    registry = load_registry()
    for command in registry.get("commands", []):
        name = str(command.get("name") or "")
        args = command.get("args")
        expectation = str(command.get("unopened_template_expectation") or "any")
        if not name or not isinstance(args, list) or not all(isinstance(item, str) for item in args):
            errors.append(f"return-code registry command is malformed: {command!r}")
            continue
        result = run(ROOT, args)
        if not expectation_matches(result.returncode, expectation):
            errors.append(f"{name}: expected {expectation}, got {result.returncode}")
        output = result.stdout + result.stderr
        if "Traceback (most recent call last)" in output:
            errors.append(f"{name}: command printed a traceback")
    return errors


def check_json_contracts() -> list[str]:
    errors: list[str] = []
    for command in load_registry().get("commands", []):
        status_path = command.get("json_status_path")
        if not status_path:
            continue
        name = str(command.get("name") or "")
        args = command.get("args")
        if not isinstance(args, list) or not all(isinstance(item, str) for item in args):
            errors.append(f"{name}: JSON contract has malformed args")
            continue
        result = run(ROOT, args)
        try:
            data = json.loads(result.stdout)
        except json.JSONDecodeError as exc:
            errors.append(f"{name}: stdout is not valid JSON: {exc}")
            continue
        if value_at_path(data, str(status_path)) in (None, ""):
            errors.append(f"{name}: missing JSON status path {status_path}")
    return errors


def check_no_write() -> list[str]:
    errors: list[str] = []
    temp_root, repo = copy_to_temp()
    try:
        before = file_snapshot(repo)
        for args in load_registry().get("no_write_commands", []):
            if not isinstance(args, list) or not all(isinstance(item, str) for item in args):
                errors.append(f"no-write command is malformed: {args!r}")
                continue
            result = run(repo, args)
            if "Traceback (most recent call last)" in result.stdout + result.stderr:
                errors.append(f"{' '.join(args)}: command printed a traceback")
        after = file_snapshot(repo)
        if before != after:
            before_keys = set(before)
            after_keys = set(after)
            added = sorted(after_keys - before_keys)
            removed = sorted(before_keys - after_keys)
            changed = sorted(path for path in before_keys & after_keys if before[path] != after[path])
            for path in added[:10]:
                errors.append(f"no-write added file: {path}")
            for path in removed[:10]:
                errors.append(f"no-write removed file: {path}")
            for path in changed[:10]:
                errors.append(f"no-write changed file: {path}")
    finally:
        shutil.rmtree(temp_root, ignore_errors=True)
    return errors


def check_clone_hygiene() -> list[str]:
    errors: list[str] = []
    for pattern in CLONE_FORBIDDEN_PATTERNS:
        for path in sorted(ROOT.glob(pattern)):
            if path.name == ".gitkeep":
                continue
            if path.is_file() and path.stat().st_size > 0:
                errors.append(f"clone hygiene forbidden starter artifact: {path.relative_to(ROOT).as_posix()}")
    return errors


def iter_human_facing_files() -> list[Path]:
    paths: list[Path] = []
    for target in ENCODING_TARGETS:
        if target.is_file():
            paths.append(target)
        elif target.exists():
            paths.extend(
                sorted(
                    path
                    for path in target.rglob("*")
                    if path.is_file() and path.suffix.lower() in {".md", ".yaml", ".yml", ".json", ".txt"}
                )
            )
    return paths


def check_encoding() -> list[str]:
    errors: list[str] = []
    for path in iter_human_facing_files():
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError as exc:
            errors.append(f"encoding decode failure: {path.relative_to(ROOT).as_posix()}: {exc}")
            continue
        found = [marker for marker in MOJIBAKE_MARKERS if marker in text]
        if found:
            errors.append(f"mojibake marker in {path.relative_to(ROOT).as_posix()}: {', '.join(found)}")
    return errors


def run_sections(section: str | None) -> list[tuple[str, list[str]]]:
    checks = [
        ("return-codes", check_return_codes),
        ("json", check_json_contracts),
        ("no-write", check_no_write),
        ("clone", check_clone_hygiene),
        ("encoding", check_encoding),
    ]
    results: list[tuple[str, list[str]]] = []
    for name, func in checks:
        if section and section != name:
            continue
        results.append((name, func()))
    return results


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate workflow command contracts and template safety.")
    parser.add_argument("--section", choices=["return-codes", "json", "no-write", "clone", "encoding"], default=None)
    args = parser.parse_args()

    any_errors = False
    for name, errors in run_sections(args.section):
        print(f"# {name}")
        if errors:
            any_errors = True
            for error in errors:
                print(f"ERROR: {error}")
        else:
            print("OK")
    return 1 if any_errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
