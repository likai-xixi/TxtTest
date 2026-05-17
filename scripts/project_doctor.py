from __future__ import annotations

import os
import subprocess
import sys

from _common import ROOT, unresolved_locks


def run_git(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *args], cwd=ROOT, text=True, capture_output=True)


def main() -> int:
    errors: list[str] = []
    warnings: list[str] = []
    ok: list[str] = []

    status = run_git("status", "--short")
    if status.returncode != 0:
        errors.append("not a Git repository; run `python scripts/novel.py go` or `git init` first")
    else:
        ok.append("Git repository detected")
        head = run_git("rev-parse", "--verify", "HEAD")
        if head.returncode != 0:
            errors.append("Git repository has no initial commit")
        else:
            ok.append("initial Git commit exists")
        porcelain = run_git("status", "--porcelain")
        if porcelain.returncode == 0 and porcelain.stdout.strip():
            warnings.append("working tree has uncommitted changes")

    if os.environ.get("DEEPSEEK_API_KEY"):
        ok.append("DEEPSEEK_API_KEY is set")
    else:
        warnings.append("DEEPSEEK_API_KEY is missing; idea lab and live DeepSeek calls will stop")

    locks = unresolved_locks()
    if locks:
        errors.append(f"{len(locks)} unresolved stop lock(s) block write actions")
    else:
        ok.append("no open stop locks")

    check = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "check_template.py")],
        cwd=ROOT,
        text=True,
        capture_output=True,
    )
    if check.returncode == 0:
        ok.append("template check passed")
    else:
        details = (check.stderr or check.stdout).strip().splitlines()
        errors.append("template check failed")
        for line in details[:8]:
            errors.append(f"template: {line}")

    print("# Project Doctor")
    print()
    if errors:
        print("status: ERROR")
    elif warnings:
        print("status: WARNING")
    else:
        print("status: READY")
    print()
    for item in ok:
        print(f"OK: {item}")
    for item in warnings:
        print(f"WARNING: {item}")
    for item in errors:
        print(f"ERROR: {item}")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
