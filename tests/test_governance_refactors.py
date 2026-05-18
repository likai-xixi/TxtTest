from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "tests"))

import deepseek_client  # noqa: E402
from test_workflow_guards import (  # noqa: E402
    copy_repo,
    run,
    write_agent_review_manifest,
    write_core_setting_freeze,
    write_ready_idea_lab,
)


class _FakeResponse:
    def __init__(self, body: bytes) -> None:
        self.body = body

    def __enter__(self) -> "_FakeResponse":
        return self

    def __exit__(self, *_args: object) -> None:
        return None

    def read(self) -> bytes:
        return self.body


class GovernanceRefactorTests(unittest.TestCase):
    def test_deepseek_client_posts_json_with_auth_header(self) -> None:
        with patch("urllib.request.urlopen", return_value=_FakeResponse(b'{"ok": true}')) as mocked:
            response = deepseek_client.call_deepseek({"model": "x"}, "secret", timeout=7)

        self.assertEqual(response, {"ok": True})
        request = mocked.call_args.args[0]
        self.assertEqual(mocked.call_args.kwargs["timeout"], 7)
        self.assertEqual(request.get_header("Authorization"), "Bearer secret")
        self.assertEqual(json.loads(request.data.decode("utf-8")), {"model": "x"})

    def test_start_chapter_gate_thresholds_follow_gate_yaml(self) -> None:
        with copy_repo() as repo:
            gate_rules = repo / "ops/gate_rules.yaml"
            gate_rules.write_text(
                gate_rules.read_text(encoding="utf-8").replace(
                    "decide_only_after_chapters: 3",
                    "decide_only_after_chapters: 1",
                    1,
                ),
                encoding="utf-8",
                newline="\n",
            )
            result = run(repo, "scripts/start_chapter.py", "--chapter", "v01_c002")

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("Gate A", result.stderr)
            self.assertIn("chapter 2+", result.stderr)

    def test_idea_select_requires_agent_review_manifest(self) -> None:
        with copy_repo() as repo:
            idea = "idea_missing_manifest"
            lab = write_ready_idea_lab(repo, idea)
            (repo / f"{lab}/agent_review_manifest.json").unlink()

            result = run(repo, "scripts/record_idea_selection.py", "--id", idea, "--choice", "A")

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("agent_review_manifest.json", result.stderr)

    def test_idea_select_records_agent_manifest_in_freeze_evidence(self) -> None:
        with copy_repo() as repo:
            idea = "idea_with_manifest"
            write_ready_idea_lab(repo, idea)

            result = run(repo, "scripts/record_idea_selection.py", "--id", idea, "--choice", "A")

            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            freeze = json.loads((repo / f"state/idea_lab/{idea}/core_setting_freeze.json").read_text(encoding="utf-8"))
            self.assertIn("agent_review_manifest", freeze["evidence"])

    def test_agent_manifest_rejects_stale_review_hash(self) -> None:
        with copy_repo() as repo:
            idea = "idea_stale_manifest"
            lab = write_ready_idea_lab(repo, idea)
            (repo / f"{lab}/product_founder_review.md").write_text(
                f"# Product Founder Review: {idea}\n\nChanged after manifest.\n",
                encoding="utf-8",
                newline="\n",
            )

            result = run(repo, "scripts/record_idea_selection.py", "--id", idea, "--choice", "A")

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("product_founder review hash mismatch", result.stderr)

    def test_selected_c001_brief_includes_element_governance_sections(self) -> None:
        with copy_repo() as repo:
            idea = "idea_c001_fields"
            write_ready_idea_lab(repo, idea)

            result = run(repo, "scripts/record_idea_selection.py", "--id", idea, "--choice", "A")

            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            brief = (repo / "outline/chapter_briefs/v01_c001.md").read_text(encoding="utf-8")
            for heading in [
                "## 本章可用道具 IDs",
                "## 本章可用技能 IDs",
                "## 本章允许新增元素",
                "## 本章禁止临场解决",
            ]:
                self.assertIn(heading, brief)

    def test_agent_manifest_command_writes_current_hashes(self) -> None:
        with copy_repo() as repo:
            idea = "idea_manifest_command"
            lab = write_ready_idea_lab(repo, idea)
            (repo / f"{lab}/agent_review_manifest.json").unlink()

            result = run(repo, "scripts/record_agent_review_manifest.py", "--id", idea)

            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            manifest = json.loads((repo / f"{lab}/agent_review_manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(manifest["idea_id"], idea)
            self.assertEqual(set(manifest["reviews"]), {"product_founder", "technical_lead", "qa_release"})


if __name__ == "__main__":
    unittest.main()
