from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from _common import ROOT


IGNORE = shutil.ignore_patterns(
    ".git",
    "__pycache__",
    "*.pyc",
    ".pytest_cache",
    "backups",
    "exports",
    "*.zip",
)


def run(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8:replace"
    command = [sys.executable, *args]
    return subprocess.run(
        command,
        cwd=repo,
        text=True,
        capture_output=True,
        encoding="utf-8",
        errors="replace",
        env=env,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Run a no-live-API workflow smoke in a temporary copy.")
    parser.add_argument("--keep-temp", action="store_true")
    args = parser.parse_args()

    temp_root = Path(tempfile.mkdtemp(prefix="novel_workflow_smoke_"))
    repo = temp_root / "repo"
    shutil.copytree(ROOT, repo, ignore=IGNORE)
    print(f"SMOKE: temp repo {repo}")

    steps = [
        ("check", ["scripts/novel.py", "check"]),
        (
            "minimal chapter path",
            [
                "-m",
                "unittest",
                "tests.test_workflow_guards.WorkflowGuardTests.test_minimal_chapter_happy_path_closes_ship",
            ],
        ),
        ("desk json", ["scripts/novel.py", "desk", "--json"]),
        ("stale check", ["scripts/novel.py", "stale-check"]),
        ("gate rehearsal", ["scripts/novel.py", "gate-rehearsal", "A"]),
    ]
    for name, step_args in steps:
        result = run(repo, *step_args)
        if result.stdout:
            print(result.stdout, end="")
        if result.stderr:
            print(result.stderr, end="", file=sys.stderr)
        if result.returncode != 0:
            print(f"SMOKE FAILED: {name} exited {result.returncode}", file=sys.stderr)
            if not args.keep_temp:
                shutil.rmtree(temp_root, ignore_errors=True)
            return result.returncode
        print(f"SMOKE OK: {name}")

    if args.keep_temp:
        print(f"SMOKE: kept temp repo at {repo}")
    else:
        shutil.rmtree(temp_root, ignore_errors=True)
    print("SMOKE OK: workflow sandbox completed without live DeepSeek or real repo mutation")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
