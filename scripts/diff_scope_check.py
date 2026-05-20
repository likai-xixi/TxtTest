from __future__ import annotations

import argparse
import fnmatch
import subprocess
import sys

from _common import ROOT, chapter_parts, posix


try:
    import yaml
except ImportError:  # pragma: no cover - exercised only on stripped Python envs
    yaml = None


def load_role_patterns() -> dict[str, list[str]]:
    if yaml is None:
        raise RuntimeError("PyYAML is required to read ops/roles.yaml")
    path = ROOT / "ops" / "roles.yaml"
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise RuntimeError("ops/roles.yaml must contain a mapping of roles")
    patterns: dict[str, list[str]] = {}
    for role, config in data.items():
        if not isinstance(config, dict) or not isinstance(config.get("allow"), list):
            raise RuntimeError(f"ops/roles.yaml role {role!r} must define allow: [...]")
        values: list[str] = []
        for item in config["allow"]:
            if not isinstance(item, str) or not item.strip():
                raise RuntimeError(f"ops/roles.yaml role {role!r} has an invalid allow entry")
            values.append(posix(item.strip()))
        patterns[str(role)] = values
    return patterns


ROLE_PATTERNS = load_role_patterns()


def run_git(args: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *args], cwd=ROOT, text=True, capture_output=True)


def changed_files() -> list[str]:
    head = run_git(["rev-parse", "--verify", "HEAD"])
    files: set[str] = set()
    if head.returncode == 0:
        for args in (["diff", "--name-only", "HEAD"], ["diff", "--name-only", "--cached"]):
            result = run_git(args)
            if result.returncode == 0:
                files.update(line.strip() for line in result.stdout.splitlines() if line.strip())
        status = run_git(["status", "--porcelain", "-uall"])
        if status.returncode == 0:
            for line in status.stdout.splitlines():
                if not line.strip():
                    continue
                path = line[3:].strip()
                if " -> " in path:
                    path = path.split(" -> ", 1)[1]
                if path:
                    files.add(path)
    else:
        result = run_git(["status", "--short"])
        for line in result.stdout.splitlines():
            if not line.strip():
                continue
            path = line[3:].strip()
            if " -> " in path:
                path = path.split(" -> ", 1)[1]
            files.add(path)
    return sorted(files)


def main() -> int:
    parser = argparse.ArgumentParser(description="Check that changed files fit a workflow role.")
    parser.add_argument("--role", required=True, choices=sorted(ROLE_PATTERNS))
    parser.add_argument("--chapter", required=True)
    args = parser.parse_args()

    volume, chapter_file = chapter_parts(args.chapter)
    patterns = [
        pattern.format(chapter=args.chapter, volume=volume, chapter_file=chapter_file)
        for pattern in ROLE_PATTERNS[args.role]
    ]
    files = changed_files()
    violations = [
        file for file in files
        if not any(fnmatch.fnmatch(posix(file), pattern) for pattern in patterns)
    ]

    if violations:
        print(f"ERROR: role {args.role} allows only:")
        for pattern in patterns:
            print(f"  - {pattern}")
        print("Changed files outside scope:")
        for file in violations:
            print(f"  - {file}")
        return 1

    print(f"OK: {len(files)} changed files fit role {args.role}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
