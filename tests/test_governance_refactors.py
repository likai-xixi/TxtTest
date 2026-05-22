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
import gate_check  # noqa: E402
import reader_feedback  # noqa: E402
from test_workflow_guards import (  # noqa: E402
    copy_repo,
    file_sha,
    run,
    write,
    write_complete_chapter_evidence,
    write_context_quality,
    write_ready_idea_lab,
    write_semantic_review_artifact,
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
            self.assertIn("schema_version: 2", brief)
            self.assertIn("## Story Card", brief)
            self.assertIn("## Machine Contract Appendix", brief)
            for field in [
                "- 第一屏扰动：",
                "- 主角本章想要：",
                "- 主角主动动作：",
                "- 本章小兑现：",
                "- before -> after：",
                "- 章末点击理由：",
                "- 上章章末锚点：",
                "- 本章开场落点：",
                "- 场景承接说明：",
                "- 主线牵引档位：",
                "- 外部压力档位：",
                "- 本章进展契约：",
                "- 本章代价与后果契约：",
                "- 本章解决边界：",
                "- reader_reward_intensity：",
                "- 可用道具 IDs：",
                "- 可用技能 IDs：",
                "- 允许新增元素：",
                "- 最低落账事件：",
            ]:
                self.assertIn(field, brief)

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
            self.assertEqual(manifest["reviews"]["product_founder"]["agent_id"], "agent_product_founder")
            self.assertIn("agent_run", manifest["reviews"]["technical_lead"])

    def test_stale_check_strict_fails_on_stale_hash_without_changing_default(self) -> None:
        with copy_repo() as repo:
            chapter = "v01_c001"
            write(repo, f"state/context_pack/{chapter}.md", "context one\n")
            write_context_quality(repo, chapter)
            write(repo, f"state/context_pack/{chapter}.md", "context two\n")

            default = run(repo, "scripts/novel.py", "stale-check", chapter)
            strict = run(repo, "scripts/novel.py", "stale-check", chapter, "--strict")

            self.assertEqual(default.returncode, 0, default.stdout + default.stderr)
            self.assertNotEqual(strict.returncode, 0)
            self.assertIn("status: STALE", strict.stdout)

    def test_workflow_contracts_check_json_and_no_write_contracts(self) -> None:
        with copy_repo() as repo:
            result = run(repo, "scripts/novel.py", "workflow-contracts")

            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn("# return-codes", result.stdout)
            self.assertIn("# json", result.stdout)
            self.assertIn("# no-write", result.stdout)

    def test_workflow_contracts_json_section_rejects_bad_registry_status_path(self) -> None:
        with copy_repo() as repo:
            registry = repo / "ops/return_code_registry.json"
            data = json.loads(registry.read_text(encoding="utf-8"))
            data["commands"][1]["json_status_path"] = "missing.status"
            registry.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

            result = run(repo, "scripts/novel.py", "workflow-contracts", "--section", "json")

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("missing JSON status path", result.stdout)

    def test_candidate_compare_includes_selection_matrix_without_writing_selection(self) -> None:
        with copy_repo() as repo:
            write(repo, "drafts/codex/v01_c001_brief.md", "Codex candidate has a visible scene and a final choice.\n")
            write(repo, "drafts/deepseek/v01_c001_brief.md", "DeepSeek candidate has a different ending and L4 risk.\n")

            result = run(repo, "scripts/novel.py", "candidate-compare", "v01_c001", "--brief", "--json")

            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            data = json.loads(result.stdout)
            self.assertFalse(data["writes_selection"])
            self.assertIn("selection_matrix", data)
            self.assertEqual(
                data["selection_matrix"]["dimensions"],
                [
                    "hook_click_reason",
                    "character_drive",
                    "pacing_efficiency",
                    "setting_safety",
                    "revision_cost",
                    "reader_reward",
                ],
            )
            self.assertEqual({row["candidate"] for row in data["selection_matrix"]["rows"]}, {"Codex", "DeepSeek"})
            self.assertFalse((repo / "reviews/v01_c001/candidate_selection.json").exists())

    def test_pilot_health_alias_can_limit_to_first_two_chapters(self) -> None:
        with copy_repo() as repo:
            result = run(repo, "scripts/novel.py", "pilot-health", "--to", "v01_c002", "--json")

            self.assertNotEqual(result.returncode, 0)
            data = json.loads(result.stdout)
            self.assertEqual(data["gate"], "A")
            self.assertEqual(data["through"], "v01_c002")
            self.assertEqual([item["chapter"] for item in data["chapters"]], ["v01_c001", "v01_c002"])

    def test_revision_closure_blocks_unresolved_revise_once_plan(self) -> None:
        with copy_repo() as repo:
            chapter = "v01_c001"
            write(repo, "chapters/v01/c001.md", "# Official\n\nA revised chapter body.\n")
            write(
                repo,
                f"reviews/{chapter}/decision.json",
                json.dumps({"chapter": chapter, "decision": "Revise once"}, ensure_ascii=False, indent=2) + "\n",
            )
            write(repo, f"reviews/{chapter}/decision.md", f"# Decision\n\ndecision: Revise once\n")
            report = {
                "schema_version": 1,
                "chapter": chapter,
                "generated_at": "2000-01-01T00:00:00+00:00",
                "status": "NOT_READY",
                "official_chapter": {
                    "path": "chapters/v01/c001.md",
                    "sha256": file_sha(repo, "chapters/v01/c001.md"),
                },
                "input_hashes": [],
                "must_fix": [{"issue": "still unresolved"}],
                "should_fix": [],
                "human_acceptance_allowed": [],
            }
            write(repo, f"reviews/{chapter}/revision_plan.json", json.dumps(report, ensure_ascii=False, indent=2) + "\n")

            result = run(repo, "scripts/novel.py", "revision-closure", chapter, "--json")

            self.assertNotEqual(result.returncode, 0)
            data = json.loads(result.stdout)
            self.assertEqual(data["status"], "BLOCKED")
            self.assertTrue(any("must_fix" in item for item in data["blockers"]))

    def test_revision_closure_blocks_unresolved_plan_after_ship_decision(self) -> None:
        with copy_repo() as repo:
            chapter = "v01_c001"
            write(repo, "chapters/v01/c001.md", "# Official\n\nA revised chapter body.\n")
            write(
                repo,
                f"reviews/{chapter}/decision.json",
                json.dumps({"chapter": chapter, "decision": "Ship"}, ensure_ascii=False, indent=2) + "\n",
            )
            report = {
                "schema_version": 1,
                "chapter": chapter,
                "generated_at": "2000-01-01T00:00:00+00:00",
                "status": "NOT_READY",
                "official_chapter": {
                    "path": "chapters/v01/c001.md",
                    "sha256": file_sha(repo, "chapters/v01/c001.md"),
                },
                "input_hashes": [],
                "must_fix": [{"issue": "still unresolved"}],
                "should_fix": [],
                "human_acceptance_allowed": [],
            }
            write(repo, f"reviews/{chapter}/revision_plan.json", json.dumps(report, ensure_ascii=False, indent=2) + "\n")

            result = run(repo, "scripts/novel.py", "revision-closure", chapter, "--json")

            self.assertNotEqual(result.returncode, 0)
            data = json.loads(result.stdout)
            self.assertEqual(data["status"], "BLOCKED")
            self.assertTrue(any("must_fix" in item for item in data["blockers"]))

    def test_chapter_evidence_rejects_stale_reader_feedback_in_reader_risk_index(self) -> None:
        with copy_repo() as repo:
            chapter = "v01_c001"
            write_complete_chapter_evidence(repo, chapter, 1)
            feedback_path = repo / f"reviews/{chapter}/reader_feedback.json"
            risk_path = repo / "state/derived/reader_risk/latest.json"
            risk = json.loads(risk_path.read_text(encoding="utf-8"))
            risk["chapters"] = [
                {
                    "chapter": chapter,
                    "reader_reward_gate": {
                        "path": f"reviews/{chapter}/reader_reward_gate.json",
                        "sha256": file_sha(repo, f"reviews/{chapter}/reader_reward_gate.json"),
                    },
                    "chapter_shape": {
                        "path": f"reviews/{chapter}/chapter_shape.json",
                        "sha256": file_sha(repo, f"reviews/{chapter}/chapter_shape.json"),
                    },
                    "reader_feedback": {
                        "path": f"reviews/{chapter}/reader_feedback.json",
                        "sha256": file_sha(repo, f"reviews/{chapter}/reader_feedback.json"),
                    },
                }
            ]
            risk_path.write_text(json.dumps(risk, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            data = json.loads(feedback_path.read_text(encoding="utf-8"))
            data["risk"] = "changed after reader risk index was built"
            feedback_path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

            result = run(repo, "scripts/chapter_evidence.py", "--chapter", chapter)

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("reader risk v01_c001 reader_feedback hash is stale", result.stdout)

    def test_decision_packet_is_no_write_json_summary(self) -> None:
        with copy_repo() as repo:
            def files() -> list[str]:
                return sorted(
                    path.relative_to(repo).as_posix()
                    for path in repo.rglob("*")
                    if path.is_file() and "__pycache__" not in path.parts and path.suffix != ".pyc"
                )

            before = files()

            result = run(repo, "scripts/novel.py", "decision-packet", "--json")

            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            data = json.loads(result.stdout)
            self.assertIn(data["status"], {"READY", "WARNING", "BLOCKED"})
            self.assertFalse(data["writes_canon"])
            self.assertFalse(data["writes_event_ledger"])
            after = files()
            self.assertEqual(before, after)

    def test_reader_experience_specialty_gates_write_current_reviews(self) -> None:
        with copy_repo() as repo:
            chapter = "v01_c001"
            body = (
                "# Official\n\n"
                "At the rain door, she chose to hide the report in her hand because family trust and pressure would cost her the job.\n"
                "She refused the process and changed the room with one sentence!\n"
            )
            write(repo, "chapters/v01/c001.md", body)
            write(repo, "outline/chapter_briefs/v01_c001.md", "emotion absence not allowed\n")
            write_semantic_review_artifact(repo, chapter, "codex_semantic_reader_review", "codex_semantic_reader_subagent", "Codex Semantic Reader Review")
            write_semantic_review_artifact(repo, chapter, "deepseek_semantic_reader_review", "deepseek_semantic_reader", "DeepSeek Semantic Reader Review")
            commands = [
                ("emotion-relationship-gate", "emotion_relationship_gate.json"),
                ("semantic-reader-review", "semantic_reader_review.json"),
                ("memorable-scene-check", "memorable_scene.json"),
            ]

            for command, artifact in commands:
                result = run(repo, "scripts/novel.py", command, chapter, "--write", "--json")
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                data = json.loads(result.stdout)
                self.assertEqual(data["status"], "CLEAR")
                self.assertTrue((repo / f"reviews/{chapter}/{artifact}").exists())
                self.assertEqual(data["official_chapter"]["path"], "chapters/v01/c001.md")

    def test_dialogue_function_blocks_consecutive_explanation_only_lines(self) -> None:
        with copy_repo() as repo:
            chapter = "v01_c001"
            write(
                repo,
                "chapters/v01/c001.md",
                "# Official\n\n- rule procedure report.\n- process file report.\n- rule process file.\n",
            )

            result = run(repo, "scripts/novel.py", "dialogue-function-check", chapter, "--json", "--no-write")

            self.assertNotEqual(result.returncode, 0)
            data = json.loads(result.stdout)
            self.assertEqual(data["status"], "BLOCKED")
            self.assertGreaterEqual(data["summary"]["max_explanation_only_run"], 2)

    def test_dialogue_function_blocks_chinese_explanation_only_lines(self) -> None:
        with copy_repo() as repo:
            chapter = "v01_c001"
            write(
                repo,
                "chapters/v01/c001.md",
                "# Official\n\n“规则流程报告。”\n“程序档案证据。”\n",
            )

            result = run(repo, "scripts/novel.py", "dialogue-function-check", chapter, "--json", "--no-write")

            self.assertNotEqual(result.returncode, 0)
            data = json.loads(result.stdout)
            self.assertEqual(data["status"], "BLOCKED")
            self.assertEqual(data["summary"]["dialogue_line_count"], 2)
            self.assertGreaterEqual(data["summary"]["max_explanation_only_run"], 2)

    def test_reader_feedback_acceptance_requires_risk_items(self) -> None:
        report = {
            "schema_version": 1,
            "chapter": "v01_c001",
            "generated_at": "2000-01-01T00:00:00+00:00",
            "status": "ACCEPTED_BY_HUMAN",
            "response_count": 0,
            "source_response_refs": [],
            "stuck_points": [],
            "continue_reasons": [],
            "reader_promise_gaps": [],
            "favorite_moments": [],
            "skip_moments": [],
            "next_click_intents": [],
            "protagonist_charm_notes": [],
            "author_explanation_flags": [],
            "suspense_fatigue_flags": [],
            "risk": "No real reader feedback yet.",
            "recommendation": "Human editor accepts the risk explicitly.",
            "human_acceptance": None,
        }
        acceptance = {
            "accepted_by": "human",
            "accepted_at": "2000-01-01T00:00:00+00:00",
            "reason": "editor accepts this risk",
            "report_sha256": reader_feedback.accepted_report_hash(report),
        }
        report["human_acceptance"] = acceptance
        self.assertFalse(gate_check.reader_feedback_accepted(report))

        acceptance["risk_acceptance_items"] = ["No real reader feedback yet."]
        self.assertTrue(gate_check.reader_feedback_accepted(report))

    def test_reader_feedback_summarize_writes_risk_acceptance_items(self) -> None:
        with copy_repo() as repo:
            result = run(
                repo,
                "scripts/reader_feedback.py",
                "summarize",
                "v01_c001",
                "--human-acceptance-reason",
                "editor accepts no-reader risk",
            )

            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            data = json.loads((repo / "reviews/v01_c001/reader_feedback.json").read_text(encoding="utf-8"))
            self.assertEqual(data["status"], "ACCEPTED_BY_HUMAN")
            self.assertTrue(data["human_acceptance"]["risk_acceptance_items"])

    def test_reader_risk_index_blocks_overdue_p1_suspense_thread(self) -> None:
        with copy_repo() as repo:
            events = [
                {
                    "event_id": "thread_1",
                    "chapter": "v01_c001",
                    "type": "thread_opened",
                    "thread_id": "missing_sister",
                    "fact": "P1 family suspense opens",
                    "evidence_quote": "door clue",
                    "consequence": "reader expects a follow-up",
                    "verified_by": "human",
                    "importance": "P1",
                }
            ]
            write(repo, "state/event_ledger.jsonl", "\n".join(json.dumps(item, ensure_ascii=False) for item in events) + "\n")

            result = run(repo, "scripts/novel.py", "reader-risk-index", "--to", "v01_c006", "--json")

            self.assertNotEqual(result.returncode, 0)
            data = json.loads(result.stdout)
            self.assertEqual(data["suspense_age_budget"]["open_threads"][0]["status"], "OVERDUE")
            self.assertTrue(any("missing_sister" in item for item in data["suspense_age_budget"]["blockers"]))


if __name__ == "__main__":
    unittest.main()
