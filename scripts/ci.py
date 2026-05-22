from __future__ import annotations

import os
import subprocess
import sys
from dataclasses import dataclass

from _common import ROOT


@dataclass
class Step:
    name: str
    command: list[str]
    returncode: int


def run_step(name: str, command: list[str], *, ci_depth: int) -> Step:
    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8:replace"
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["NOVEL_CI_DEPTH"] = str(ci_depth + 1)
    if name == "self-test" and ci_depth > 0:
        print("# self-test")
        print("SKIP: nested self-test avoided during CI recursion")
        return Step(name, command, 0)
    print(f"# {name}")
    result = subprocess.run(command, cwd=ROOT, env=env)
    return Step(name, command, result.returncode)


def main() -> int:
    ci_depth = int(os.environ.get("NOVEL_CI_DEPTH", "0") or "0")
    steps = [
        ("compileall", [sys.executable, "-B", "-m", "compileall", "-q", "scripts", "tests"]),
        ("check", [sys.executable, str(ROOT / "scripts" / "novel.py"), "check"]),
        ("workflow-contracts", [sys.executable, str(ROOT / "scripts" / "novel.py"), "workflow-contracts"]),
        ("self-test", [sys.executable, str(ROOT / "scripts" / "novel.py"), "self-test"]),
        ("workflow-smoke", [sys.executable, str(ROOT / "scripts" / "novel.py"), "workflow-smoke"]),
    ]
    results = [run_step(name, command, ci_depth=ci_depth) for name, command in steps]
    print()
    print("# Local CI Summary")
    for result in results:
        status = "PASS" if result.returncode == 0 else "FAIL"
        print(f"- {result.name}: {status} ({result.returncode})")
    return 0 if all(result.returncode == 0 for result in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
