from __future__ import annotations

import subprocess
import sys
import os
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    result = subprocess.run([sys.executable, "-B", "-m", "unittest", "discover", "-s", "tests", "-q"], cwd=ROOT, env=env)
    return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())
