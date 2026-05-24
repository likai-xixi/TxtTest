from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class ShadowMemoryTests(unittest.TestCase):
    def copy_repo(self):
        temp = tempfile.TemporaryDirectory()
        target = Path(temp.name) / "repo"
        shutil.copytree(
            ROOT,
            target,
            ignore=shutil.ignore_patterns(".git", "__pycache__", "backups", "exports", "*.pyc", ".pytest_cache"),
        )
        self.addCleanup(temp.cleanup)
        return target

    def run_cmd(self, repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, *args],
            cwd=repo,
            text=True,
            capture_output=True,
            encoding="utf-8",
            errors="replace",
        )

    def test_shadow_build_writes_artifacts_and_check_passes(self) -> None:
        repo = self.copy_repo()
        result = self.run_cmd(repo, "scripts/novel.py", "shadow-build", "v01_c001", "--write", "--json")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        manifest = json.loads(result.stdout)
        self.assertEqual(manifest["status"], "READY")
        self.assertEqual(manifest["source_boundary"], "shadow_advisory_not_fact_source")
        self.assertFalse(manifest["can_satisfy_ship_without_chapter_evidence"])

        for relative in (
            "state/shadow/local_window/v01_c001.json",
            "state/shadow/rag_index/v01_c001.json",
            "state/shadow/kg_edges/v01_c001.json",
            "state/shadow/route_signals/v01_c001.json",
            "state/shadow/manifests/v01_c001.json",
        ):
            self.assertTrue((repo / relative).exists(), relative)

        check = self.run_cmd(repo, "scripts/novel.py", "shadow-check", "v01_c001", "--json")
        self.assertEqual(check.returncode, 0, check.stdout + check.stderr)
        data = json.loads(check.stdout)
        self.assertEqual(data["status"], "READY")

    def test_shadow_check_detects_stale_brief_hash(self) -> None:
        repo = self.copy_repo()
        build = self.run_cmd(repo, "scripts/novel.py", "shadow-build", "v01_c001", "--write", "--json")
        self.assertEqual(build.returncode, 0, build.stdout + build.stderr)

        brief = repo / "outline/chapter_briefs/v01_c001.md"
        brief.write_text(brief.read_text(encoding="utf-8") + "\n\nshadow stale test\n", encoding="utf-8", newline="\n")
        check = self.run_cmd(repo, "scripts/novel.py", "shadow-check", "v01_c001", "--json")
        self.assertNotEqual(check.returncode, 0, check.stdout + check.stderr)
        data = json.loads(check.stdout)
        self.assertEqual(data["status"], "BLOCKED")
        self.assertTrue(any("hash is stale" in item for item in data["blockers"]))

    def test_shadow_route_cannot_skip_ship_evidence(self) -> None:
        repo = self.copy_repo()
        route = self.run_cmd(repo, "scripts/novel.py", "shadow-route", "v01_c001", "--json")
        self.assertEqual(route.returncode, 0, route.stdout + route.stderr)
        data = json.loads(route.stdout)
        self.assertFalse(data["can_downgrade_route"])
        self.assertTrue(data["must_not_skip_ship_evidence"])
        self.assertIn(data["route"], {"fast", "normal", "heavy", "gate"})


if __name__ == "__main__":
    unittest.main()
