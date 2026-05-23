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
import audit  # noqa: E402
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


def write_review_route(
    repo: Path,
    chapter: str,
    route: str = "fast",
    reviews: list[str] | None = None,
    *,
    fail_closed: bool = False,
    status: str = "READY",
    routing_inputs: list[dict] | None = None,
) -> None:
    volume = chapter[:3]
    chapter_rel = f"chapters/{volume}/c{int(chapter[-3:]):03d}.md"
    brief_rel = f"outline/chapter_briefs/{chapter}.md"
    manifest_rel = f"state/context_pack/{chapter}.manifest.json"
    ledger_rel = "state/event_ledger.jsonl"
    report = {
        "schema_version": 1,
        "chapter": chapter,
        "route": route,
        "route_version": 1,
        "generated_at": "2000-01-01T00:00:00+00:00",
        "status": status,
        "official_chapter": {"path": chapter_rel, "exists": True, "sha256": file_sha(repo, chapter_rel)},
        "official_brief": {"path": brief_rel, "exists": True, "sha256": file_sha(repo, brief_rel)},
        "context_manifest": {"path": manifest_rel, "exists": True, "sha256": file_sha(repo, manifest_rel)},
        "source_event_ledger": {"path": ledger_rel, "exists": True, "sha256": file_sha(repo, ledger_rel)},
        "routing_inputs": routing_inputs or [],
        "fail_closed": fail_closed,
        "always_required_ship_gates": ["hash_stale", "provenance", "event_ledger", "fact_cards"],
        "additional_literary_reviews": reviews if reviews is not None else ["human_flavor", "highlights", "ai_taste"],
        "reasons": ["fixture route"],
        "warnings": [],
        "blockers": [],
    }
    write(repo, f"reviews/{chapter}/review_route.json", json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    write(repo, f"reviews/{chapter}/review_route.md", f"# Review Route: {chapter}\n\nroute: {route.upper()}\n")


def remove_markdown_section(text: str, title: str) -> str:
    marker = f"## {title}"
    if marker not in text:
        return text
    before, rest = text.split(marker, 1)
    next_index = rest.find("\n## ")
    if next_index == -1:
        return before.rstrip() + "\n"
    return before + rest[next_index + 1 :]


def write_minimal_route_inputs(repo: Path, chapter: str) -> None:
    volume = chapter[:3]
    write(repo, f"chapters/{volume}/c{int(chapter[-3:]):03d}.md", "# Route Fixture\n\nA plain chapter with a concrete ending choice.\n")
    write(
        repo,
        f"outline/chapter_briefs/{chapter}.md",
        "# Route Brief\n\nEnding Click Reason: the saved evidence creates an immediate next action.\n",
    )
    write(repo, f"state/context_pack/{chapter}.manifest.json", json.dumps({"chapter": chapter}, ensure_ascii=False) + "\n")
    write(repo, "state/event_ledger.jsonl", "")


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

    def test_personal_mode_is_required_by_template_check(self) -> None:
        with copy_repo() as repo:
            (repo / "ops/personal_mode.yaml").unlink()

            missing = run(repo, "scripts/novel.py", "check")

            self.assertNotEqual(missing.returncode, 0)
            self.assertIn("personal_mode", missing.stdout + missing.stderr)

        with copy_repo() as repo:
            path = repo / "ops/personal_mode.yaml"
            path.write_text(
                path.read_text(encoding="utf-8").replace(
                    "allow_route_to_skip_ship_gates: false",
                    "allow_route_to_skip_ship_gates: true",
                ),
                encoding="utf-8",
                newline="\n",
            )

            invalid = run(repo, "scripts/novel.py", "check")

            self.assertNotEqual(invalid.returncode, 0)
            self.assertIn("skip Ship gates", invalid.stdout + invalid.stderr)

    def test_human_flavor_is_advisory_warning_not_ship_block(self) -> None:
        with copy_repo() as repo:
            chapter = "v01_c001"
            write_complete_chapter_evidence(repo, chapter, 1)

            result = run(repo, "scripts/novel.py", "human-flavor-check", chapter, "--json", "--no-write")

            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            data = json.loads(result.stdout)
            self.assertIn(data["status"], {"CLEAR", "WARNING"})
            self.assertEqual(data["blocking"], False)

    def test_brief_check_hard_blocks_missing_human_flavor_sections(self) -> None:
        with copy_repo() as repo:
            chapter = "v01_c001"
            write_complete_chapter_evidence(repo, chapter, 1)

            ready = run(repo, "scripts/novel.py", "brief-check", chapter)

            self.assertEqual(ready.returncode, 0, ready.stdout + ready.stderr)
            brief_path = repo / f"outline/chapter_briefs/{chapter}.md"
            brief_path.write_text(
                remove_markdown_section(brief_path.read_text(encoding="utf-8"), "Human Flavor Focus"),
                encoding="utf-8",
                newline="\n",
            )

            missing = run(repo, "scripts/novel.py", "brief-check", chapter)

            self.assertNotEqual(missing.returncode, 0)
            self.assertIn("missing required human-flavor section", missing.stdout + missing.stderr)

    def test_brief_check_hard_blocks_empty_or_placeholder_human_flavor_values(self) -> None:
        with copy_repo() as repo:
            chapter = "v01_c001"
            write_complete_chapter_evidence(repo, chapter, 1)
            brief_path = repo / f"outline/chapter_briefs/{chapter}.md"
            text = brief_path.read_text(encoding="utf-8")
            text = text.replace(
                "Protagonist cost or misjudgment: ",
                "Protagonist cost or misjudgment: TODO ",
                1,
            )
            brief_path.write_text(text, encoding="utf-8", newline="\n")

            result = run(repo, "scripts/novel.py", "brief-check", chapter)

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("human-flavor section still has placeholder text", result.stdout + result.stderr)

    def test_route_reviews_human_flavor_single_warning_stays_fast_until_window(self) -> None:
        with copy_repo() as repo:
            chapter = "v01_c011"
            write_minimal_route_inputs(repo, chapter)
            warning = {
                "schema_version": 1,
                "chapter": chapter,
                "status": "WARNING",
                "signals": {
                    "has_cost_or_misjudgment": False,
                    "has_private_motive_or_flaw": True,
                    "has_life_texture": False,
                    "does_not_flatten": True,
                    "protagonist_is_too_correct": False,
                },
                "window": {
                    "last_3_missing_cost_or_misjudgment": 1,
                    "last_5_human_flavor_warnings": 1,
                },
                "warnings": ["single chapter warning"],
            }
            write(repo, f"reviews/{chapter}/human_flavor.json", json.dumps(warning, ensure_ascii=False, indent=2) + "\n")

            single = run(repo, "scripts/novel.py", "route-reviews", chapter, "--preview", "--json")

            self.assertEqual(single.returncode, 0, single.stdout + single.stderr)
            self.assertEqual(json.loads(single.stdout)["route"], "fast")

            warning["window"]["last_3_missing_cost_or_misjudgment"] = 3
            write(repo, f"reviews/{chapter}/human_flavor.json", json.dumps(warning, ensure_ascii=False, indent=2) + "\n")

            windowed = run(repo, "scripts/novel.py", "route-reviews", chapter, "--preview", "--json")

            self.assertEqual(windowed.returncode, 0, windowed.stdout + windowed.stderr)
            self.assertEqual(json.loads(windowed.stdout)["route"], "normal")

    def test_route_reviews_fail_closed_for_missing_parse_and_gate_inputs(self) -> None:
        with copy_repo() as repo:
            chapter = "v01_c001"
            write_complete_chapter_evidence(repo, chapter, 1)
            (repo / f"state/context_pack/{chapter}.manifest.json").unlink()

            missing = run(repo, "scripts/novel.py", "route-reviews", chapter, "--preview", "--json")

            self.assertNotEqual(missing.returncode, 0)
            missing_data = json.loads(missing.stdout)
            self.assertTrue(missing_data["fail_closed"])
            self.assertEqual(missing_data["route"], "heavy")
            self.assertEqual(missing_data["status"], "BLOCKED")

        with copy_repo() as repo:
            chapter = "v01_c001"
            write_complete_chapter_evidence(repo, chapter, 1)
            write(repo, f"reviews/{chapter}/ai_taste.json", "{not-json\n")

            parsed = run(repo, "scripts/novel.py", "route-reviews", chapter, "--preview", "--json")

            self.assertNotEqual(parsed.returncode, 0)
            parsed_data = json.loads(parsed.stdout)
            self.assertTrue(parsed_data["fail_closed"])
            self.assertEqual(parsed_data["route"], "heavy")
            self.assertEqual(parsed_data["status"], "BLOCKED")
            self.assertTrue(any("cannot be parsed" in item for item in parsed_data["warnings"]))

        with copy_repo() as repo:
            chapter = "v01_c003"
            write_complete_chapter_evidence(repo, chapter, 3)

            gate = run(repo, "scripts/novel.py", "route-reviews", chapter, "--preview", "--json")

            self.assertEqual(gate.returncode, 0, gate.stdout + gate.stderr)
            self.assertEqual(json.loads(gate.stdout)["route"], "gate")

    def test_route_artifact_stales_when_bound_inputs_change(self) -> None:
        with copy_repo() as repo:
            chapter = "v01_c001"
            write_complete_chapter_evidence(repo, chapter, 1)
            self.assertEqual(run(repo, "scripts/novel.py", "human-flavor-check", chapter, "--write").returncode, 0)
            self.assertEqual(run(repo, "scripts/novel.py", "highlights-review", chapter, "--write").returncode, 0)
            write_review_route(repo, chapter, "fast")
            chapter_path = repo / "chapters/v01/c001.md"
            chapter_path.write_text(chapter_path.read_text(encoding="utf-8") + "\nchanged after route\n", encoding="utf-8", newline="\n")

            result = run(repo, "scripts/chapter_evidence.py", "--chapter", chapter)

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("review_route official_chapter hash is stale", result.stdout)

    def test_route_artifact_stales_when_routing_input_changes(self) -> None:
        with copy_repo() as repo:
            chapter = "v01_c001"
            write_complete_chapter_evidence(repo, chapter, 1)
            self.assertEqual(run(repo, "scripts/novel.py", "human-flavor-check", chapter, "--write").returncode, 0)
            self.assertEqual(run(repo, "scripts/novel.py", "highlights-review", chapter, "--write").returncode, 0)
            human_rel = f"reviews/{chapter}/human_flavor.json"
            write_review_route(
                repo,
                chapter,
                "fast",
                routing_inputs=[{"path": human_rel, "exists": True, "sha256": file_sha(repo, human_rel)}],
            )
            data = json.loads((repo / human_rel).read_text(encoding="utf-8"))
            data["warnings"].append("changed after route")
            write(repo, human_rel, json.dumps(data, ensure_ascii=False, indent=2) + "\n")

            result = run(repo, "scripts/chapter_evidence.py", "--chapter", chapter)

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("review_route routing_inputs[1] hash is stale", result.stdout)

    def test_missing_route_artifact_blocks_ship_summary_and_evidence(self) -> None:
        with copy_repo() as repo:
            chapter = "v01_c001"
            write_complete_chapter_evidence(repo, chapter, 1)
            route_path = repo / f"reviews/{chapter}/review_route.json"
            if route_path.exists():
                route_path.unlink()

            evidence = run(repo, "scripts/chapter_evidence.py", "--chapter", chapter)
            summary = run(repo, "scripts/novel.py", "review-summary", chapter, "--json")

            self.assertNotEqual(evidence.returncode, 0)
            self.assertIn("missing review_route.json", evidence.stdout)
            self.assertNotEqual(summary.returncode, 0)
            self.assertEqual(json.loads(summary.stdout)["ship_gates"], "BLOCKED")
            self.assertIn("missing review_route.json", summary.stdout)

    def test_light_review_summary_can_use_preview_route_without_artifact(self) -> None:
        with copy_repo() as repo:
            chapter = "v01_c001"
            write_complete_chapter_evidence(repo, chapter, 1)
            route_path = repo / f"reviews/{chapter}/review_route.json"
            if route_path.exists():
                route_path.unlink()

            route = run(repo, "scripts/novel.py", "route-reviews", chapter, "--preview", "--json")
            summary = run(repo, "scripts/novel.py", "review-summary", chapter, "--preview-route", "--json")

            self.assertEqual(route.returncode, 0, route.stdout + route.stderr)
            self.assertEqual(summary.returncode, 0, summary.stdout + summary.stderr)
            route_data = json.loads(route.stdout)
            data = json.loads(summary.stdout)
            self.assertEqual(data["route"], route_data["route"].upper())
            self.assertEqual(data["ship_gates"], "CLEAR")
            self.assertNotIn("missing review_route.json", summary.stdout)

    def test_heavy_fail_closed_route_artifact_blocks_ship(self) -> None:
        with copy_repo() as repo:
            chapter = "v01_c001"
            write_complete_chapter_evidence(repo, chapter, 1)
            write_review_route(
                repo,
                chapter,
                "heavy",
                [
                    "human_flavor",
                    "highlights",
                    "style_voice",
                    "ai_taste",
                    "dialogue_function",
                    "emotion_relationship",
                    "memorable_scene",
                    "prose_risk",
                    "reader_reward",
                    "reader_risk",
                    "codex_integrated",
                    "deepseek_integrated",
                    "codex_anti_ai",
                    "deepseek_anti_ai",
                    "codex_semantic",
                    "deepseek_semantic",
                    "semantic_reader",
                    "review_arbitration",
                    "revision_plan",
                    "series_style",
                    "long_health",
                ],
                fail_closed=True,
            )

            result = run(repo, "scripts/chapter_evidence.py", "--chapter", chapter)

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("review_route fail_closed requires rerun before Ship", result.stdout)

    def test_route_artifact_cannot_drop_configured_literary_reviews(self) -> None:
        with copy_repo() as repo:
            chapter = "v01_c001"
            write_complete_chapter_evidence(repo, chapter, 1)
            self.assertEqual(run(repo, "scripts/novel.py", "human-flavor-check", chapter, "--write").returncode, 0)
            write_review_route(repo, chapter, "fast", ["human_flavor"])

            result = run(repo, "scripts/chapter_evidence.py", "--chapter", chapter)

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("missing configured literary reviews", result.stdout)

    def test_fast_route_cannot_bypass_always_required_ship_gates(self) -> None:
        with copy_repo() as repo:
            chapter = "v01_c001"
            write_complete_chapter_evidence(repo, chapter, 1)
            self.assertEqual(run(repo, "scripts/novel.py", "human-flavor-check", chapter, "--write").returncode, 0)
            self.assertEqual(run(repo, "scripts/novel.py", "highlights-review", chapter, "--write").returncode, 0)
            write_review_route(repo, chapter, "fast")
            (repo / f"reviews/{chapter}/fact_cards.json").unlink()

            result = run(repo, "scripts/chapter_evidence.py", "--chapter", chapter)

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("missing fact card evidence", result.stdout)
            self.assertNotIn("missing review artifact reviews/v01_c001/deepseek_integrated_review.md", result.stdout)

    def test_always_required_ship_gates_are_bound_to_route_config(self) -> None:
        with copy_repo() as repo:
            chapter = "v01_c001"
            write_complete_chapter_evidence(repo, chapter, 1)
            self.assertEqual(run(repo, "scripts/novel.py", "human-flavor-check", chapter, "--write").returncode, 0)
            self.assertEqual(run(repo, "scripts/novel.py", "highlights-review", chapter, "--write").returncode, 0)
            write_review_route(repo, chapter, "fast")
            config_path = repo / "ops/review_routing.yaml"
            config_text = config_path.read_text(encoding="utf-8")
            config_path.write_text(config_text.replace("  - fact_cards\n", ""), encoding="utf-8", newline="\n")

            result = run(repo, "scripts/chapter_evidence.py", "--chapter", chapter)

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("review_routing.yaml missing always-required Ship gate: fact_cards", result.stdout)

    def test_highlights_are_imported_and_unreasoned_flattening_blocks(self) -> None:
        with copy_repo() as repo:
            chapter = "v01_c001"
            write_complete_chapter_evidence(repo, chapter, 1)
            self.assertEqual(run(repo, "scripts/novel.py", "highlights-review", chapter, "--write").returncode, 0)

            plan = run(repo, "scripts/novel.py", "revision-plan", chapter, "--json")

            self.assertEqual(plan.returncode, 0, plan.stdout + plan.stderr)
            plan_data = json.loads(plan.stdout)
            self.assertTrue(plan_data["must_preserve"])
            self.assertEqual(plan_data["must_preserve"][0]["highlight_id"], "h001")

            self.assertEqual(run(repo, "scripts/novel.py", "human-flavor-check", chapter, "--write").returncode, 0)
            write_review_route(repo, chapter, "heavy", ["human_flavor", "highlights", "revision_plan"])
            report = json.loads((repo / f"reviews/{chapter}/revision_plan.json").read_text(encoding="utf-8"))
            report["highlight_revisions"] = [{"highlight_id": "h001", "action": "flatten"}]
            write(repo, f"reviews/{chapter}/revision_plan.json", json.dumps(report, ensure_ascii=False, indent=2) + "\n")

            result = run(repo, "scripts/chapter_evidence.py", "--chapter", chapter)

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("requires human_override_reason", result.stdout)

    def test_highlight_override_reason_allows_flattening_exception(self) -> None:
        with copy_repo() as repo:
            chapter = "v01_c001"
            write_complete_chapter_evidence(repo, chapter, 1)
            self.assertEqual(run(repo, "scripts/novel.py", "human-flavor-check", chapter, "--write").returncode, 0)
            self.assertEqual(run(repo, "scripts/novel.py", "highlights-review", chapter, "--write").returncode, 0)
            plan = run(repo, "scripts/novel.py", "revision-plan", chapter, "--json")
            self.assertEqual(plan.returncode, 0, plan.stdout + plan.stderr)
            write_review_route(repo, chapter, "fast", ["human_flavor", "highlights", "ai_taste", "revision_plan"])
            report = json.loads((repo / f"reviews/{chapter}/revision_plan.json").read_text(encoding="utf-8"))
            report["highlight_revisions"] = [
                {
                    "highlight_id": "h001",
                    "action": "flatten",
                    "human_override_reason": "总编确认此处需要改平以避免误导读者。",
                }
            ]
            write(repo, f"reviews/{chapter}/revision_plan.json", json.dumps(report, ensure_ascii=False, indent=2) + "\n")

            result = run(repo, "scripts/chapter_evidence.py", "--chapter", chapter)

            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_human_flavor_window_blocks_ship_until_editor_action(self) -> None:
        with copy_repo() as repo:
            chapter = "v01_c001"
            write_complete_chapter_evidence(repo, chapter, 1)
            self.assertEqual(run(repo, "scripts/novel.py", "human-flavor-check", chapter, "--write").returncode, 0)
            self.assertEqual(run(repo, "scripts/novel.py", "highlights-review", chapter, "--write").returncode, 0)
            data = json.loads((repo / f"reviews/{chapter}/human_flavor.json").read_text(encoding="utf-8"))
            data["window"]["last_3_missing_cost_or_misjudgment"] = 3
            write(repo, f"reviews/{chapter}/human_flavor.json", json.dumps(data, ensure_ascii=False, indent=2) + "\n")
            write_review_route(repo, chapter, "fast")

            result = run(repo, "scripts/chapter_evidence.py", "--chapter", chapter)

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("human_flavor 3-chapter window requires forced revision", result.stdout)

    def test_route_configured_highlights_requires_artifact(self) -> None:
        with copy_repo() as repo:
            chapter = "v01_c001"
            write_complete_chapter_evidence(repo, chapter, 1)
            self.assertEqual(run(repo, "scripts/novel.py", "human-flavor-check", chapter, "--write").returncode, 0)
            highlights_path = repo / f"reviews/{chapter}/highlights_review.json"
            if highlights_path.exists():
                highlights_path.unlink()
            write_review_route(repo, chapter, "fast")

            result = run(repo, "scripts/chapter_evidence.py", "--chapter", chapter)

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("missing highlights review", result.stdout)

    def test_highlights_are_advisory_when_no_protectable_quote(self) -> None:
        with copy_repo() as repo:
            chapter = "v01_c001"
            write_complete_chapter_evidence(repo, chapter, 1)
            self.assertEqual(run(repo, "scripts/novel.py", "human-flavor-check", chapter, "--write").returncode, 0)
            report = {
                "schema_version": 1,
                "chapter": chapter,
                "generated_at": "2000-01-01T00:00:00+00:00",
                "status": "WARNING",
                "official_chapter": {
                    "path": "chapters/v01/c001.md",
                    "exists": True,
                    "sha256": file_sha(repo, "chapters/v01/c001.md"),
                },
                "input_hashes": [
                    {
                        "path": "chapters/v01/c001.md",
                        "exists": True,
                        "sha256": file_sha(repo, "chapters/v01/c001.md"),
                    }
                ],
                "protected_highlights": [],
                "warnings": ["no protectable highlight quote found"],
                "blockers": [],
            }
            write(repo, f"reviews/{chapter}/highlights_review.json", json.dumps(report, ensure_ascii=False, indent=2) + "\n")
            write_review_route(repo, chapter, "fast")

            result = run(repo, "scripts/chapter_evidence.py", "--chapter", chapter)

            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_review_summary_emits_one_line_editor_decision(self) -> None:
        with copy_repo() as repo:
            chapter = "v01_c001"
            write_complete_chapter_evidence(repo, chapter, 1)
            self.assertEqual(run(repo, "scripts/novel.py", "human-flavor-check", chapter, "--write").returncode, 0)
            self.assertEqual(run(repo, "scripts/novel.py", "highlights-review", chapter, "--write").returncode, 0)
            write_review_route(repo, chapter, "fast")

            result = run(repo, "scripts/novel.py", "review-summary", chapter, "--json")

            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            data = json.loads(result.stdout)
            self.assertEqual(data["route"], "FAST")
            self.assertEqual(data["ship_gates"], "CLEAR")
            self.assertEqual(data["status"], "可收")
            self.assertTrue(data["one_line_decision"])
            self.assertTrue(data["must_preserve"])
            self.assertIn("ai_risk", data)

    def test_review_summary_literary_must_fix_returns_nonzero(self) -> None:
        with copy_repo() as repo:
            chapter = "v01_c001"
            write_complete_chapter_evidence(repo, chapter, 1)
            self.assertEqual(run(repo, "scripts/novel.py", "human-flavor-check", chapter, "--write").returncode, 0)
            write_review_route(repo, chapter, "fast")
            (repo / f"reviews/{chapter}/highlights_review.json").unlink()

            result = run(repo, "scripts/novel.py", "review-summary", chapter, "--json")

            self.assertNotEqual(result.returncode, 0)
            data = json.loads(result.stdout)
            self.assertEqual(data["ship_gates"], "CLEAR")
            self.assertTrue(data["must_fix"])

    def test_chapter_evidence_can_require_receive_control_report(self) -> None:
        with copy_repo() as repo:
            chapter = "v01_c001"
            write_complete_chapter_evidence(repo, chapter, 1)

            missing = run(repo, "scripts/chapter_evidence.py", "--chapter", chapter, "--require-receive")

            self.assertNotEqual(missing.returncode, 0)
            self.assertIn("missing receive control-plane report", missing.stdout)

    def test_receive_preview_is_compact_by_default(self) -> None:
        with copy_repo() as repo:
            result = run(repo, "scripts/novel.py", "receive-chapter", "v01_c001", "--preview")

            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            data = json.loads(result.stdout)
            self.assertEqual(data["mode"], "compact")
            self.assertGreater(data["hidden_step_count"], 0)
            self.assertNotIn("steps", data)
            self.assertEqual(len(data["editor_lines"]), 5)

    def test_receive_preview_uses_route_aware_step_plan(self) -> None:
        with copy_repo() as repo:
            chapter = "v01_c001"
            write_complete_chapter_evidence(repo, chapter, 1)
            self.assertEqual(run(repo, "scripts/novel.py", "human-flavor-check", chapter, "--write").returncode, 0)
            self.assertEqual(run(repo, "scripts/novel.py", "highlights-review", chapter, "--write").returncode, 0)
            write_review_route(repo, chapter, "fast")

            verbose = run(repo, "scripts/novel.py", "receive-chapter", chapter, "--preview", "--verbose")
            compact = run(repo, "scripts/novel.py", "receive-chapter", chapter, "--preview")

            self.assertEqual(verbose.returncode, 0, verbose.stdout + verbose.stderr)
            verbose_data = json.loads(verbose.stdout)
            self.assertIn("route-aware preview using FAST route", verbose_data["route_note"])
            steps = [step["name"] for step in verbose_data["steps"]]
            self.assertIn("route-reviews", steps)
            self.assertIn("human-flavor-check", steps)
            self.assertNotIn("semantic-reader-review", steps)
            self.assertNotIn("deepseek-anti-ai-review", steps)

            self.assertEqual(compact.returncode, 0, compact.stdout + compact.stderr)
            compact_data = json.loads(compact.stdout)
            self.assertLess(compact_data["hidden_step_count"], 38)

    def test_chapter_evidence_handles_malformed_review_json_without_traceback(self) -> None:
        with copy_repo() as repo:
            chapter = "v01_c001"
            write_complete_chapter_evidence(repo, chapter, 1)
            self.assertEqual(run(repo, "scripts/novel.py", "human-flavor-check", chapter, "--write").returncode, 0)
            self.assertEqual(run(repo, "scripts/novel.py", "highlights-review", chapter, "--write").returncode, 0)
            write_review_route(repo, chapter, "fast")
            write(repo, f"reviews/{chapter}/ai_taste.json", "{not-json\n")

            result = run(repo, "scripts/chapter_evidence.py", "--chapter", chapter)

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("ai_taste.json invalid JSON", result.stdout)
            self.assertNotIn("Traceback", result.stderr + result.stdout)

    def test_chapter_evidence_handles_malformed_route_without_traceback(self) -> None:
        with copy_repo() as repo:
            chapter = "v01_c001"
            write_complete_chapter_evidence(repo, chapter, 1)
            write(repo, f"reviews/{chapter}/review_route.json", "{not-json\n")

            result = run(repo, "scripts/chapter_evidence.py", "--chapter", chapter)

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("review_route.json invalid JSON", result.stdout)
            self.assertNotIn("Traceback", result.stderr + result.stdout)

    def test_heavy_route_config_does_not_emit_unknown_integrated_review(self) -> None:
        with copy_repo() as repo:
            chapter = "v01_c001"
            write_complete_chapter_evidence(repo, chapter, 1)
            self.assertEqual(run(repo, "scripts/novel.py", "human-flavor-check", chapter, "--write").returncode, 0)
            self.assertEqual(run(repo, "scripts/novel.py", "highlights-review", chapter, "--write").returncode, 0)
            write_review_route(repo, chapter, "heavy")

            result = run(repo, "scripts/chapter_evidence.py", "--chapter", chapter)

            self.assertNotIn("unknown routed literary review codex_integrated", result.stdout)
            self.assertNotIn("unknown routed literary review deepseek_integrated", result.stdout)

    def test_route_rejects_thread_debt_ledger_with_stale_event_source(self) -> None:
        with copy_repo() as repo:
            chapter = "v01_c001"
            write_complete_chapter_evidence(repo, chapter, 1)
            ledger = {
                "schema_version": 1,
                "generated_at": "2000-01-01T00:00:00+00:00",
                "through": chapter,
                "status": "READY",
                "source_priority": ["event_ledger"],
                "source_event_ledger": {
                    "path": "state/event_ledger.jsonl",
                    "exists": True,
                    "sha256": file_sha(repo, "state/event_ledger.jsonl"),
                },
                "threads": [],
                "blockers": [],
                "warnings": [],
            }
            write(repo, "state/derived/thread_debt_ledger.json", json.dumps(ledger, ensure_ascii=False, indent=2) + "\n")
            write_review_route(
                repo,
                chapter,
                "fast",
                routing_inputs=[
                    {
                        "path": "state/derived/thread_debt_ledger.json",
                        "exists": True,
                        "sha256": file_sha(repo, "state/derived/thread_debt_ledger.json"),
                    }
                ],
            )
            write(repo, "state/event_ledger.jsonl", (repo / "state/event_ledger.jsonl").read_text(encoding="utf-8") + '{"event_id":"late"}\n')

            result = run(repo, "scripts/chapter_evidence.py", "--chapter", chapter)

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("source_event_ledger hash is stale", result.stdout)

    def test_stale_check_reports_new_derived_ledgers(self) -> None:
        with copy_repo() as repo:
            chapter = "v01_c001"
            write_complete_chapter_evidence(repo, chapter, 1)
            ledger = {
                "schema_version": 1,
                "generated_at": "2000-01-01T00:00:00+00:00",
                "through": chapter,
                "status": "READY",
                "source_priority": ["event_ledger"],
                "source_event_ledger": {
                    "path": "state/event_ledger.jsonl",
                    "exists": True,
                    "sha256": "stale",
                },
                "threads": [],
                "blockers": [],
                "warnings": [],
            }
            write(repo, "state/derived/thread_debt_ledger.json", json.dumps(ledger, ensure_ascii=False, indent=2) + "\n")

            result = run(repo, "scripts/novel.py", "stale-check", chapter, "--strict")

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("thread_debt_ledger source_event_ledger hash is stale", result.stdout)

    def test_stale_check_reports_style_voice_nested_source_refs(self) -> None:
        with copy_repo() as repo:
            chapter = "v01_c001"
            write_complete_chapter_evidence(repo, chapter, 1)
            ledger = {
                "schema_version": 1,
                "generated_at": "2000-01-01T00:00:00+00:00",
                "through": chapter,
                "status": "READY",
                "source_priority": ["event_ledger"],
                "source_event_ledger": {
                    "path": "state/event_ledger.jsonl",
                    "exists": True,
                    "sha256": file_sha(repo, "state/event_ledger.jsonl"),
                },
                "chapters": [
                    {
                        "chapter": chapter,
                        "voice_notes": [],
                        "source_refs": [
                            {
                                "path": "chapters/v01/c001.md",
                                "exists": True,
                                "sha256": file_sha(repo, "chapters/v01/c001.md"),
                            }
                        ],
                    }
                ],
                "blockers": [],
                "warnings": [],
            }
            write(repo, "state/derived/style_voice_ledger.json", json.dumps(ledger, ensure_ascii=False, indent=2) + "\n")
            write(repo, "chapters/v01/c001.md", (repo / "chapters/v01/c001.md").read_text(encoding="utf-8") + "\nlate voice edit\n")

            result = run(repo, "scripts/novel.py", "stale-check", chapter, "--strict")

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("style_voice_ledger v01_c001 source_refs[1] hash is stale", result.stdout)

    def test_long_health_context_quality_ref_must_be_current(self) -> None:
        with copy_repo() as repo:
            chapter = "v01_c010"
            write_complete_chapter_evidence(repo, chapter, 10)
            self.assertEqual(run(repo, "scripts/novel.py", "human-flavor-check", chapter, "--write").returncode, 0)
            self.assertEqual(run(repo, "scripts/novel.py", "highlights-review", chapter, "--write").returncode, 0)
            context_quality_rel = f"state/derived/context_quality/{chapter}.json"
            long_health = {
                "schema_version": 1,
                "generated_at": "2000-01-01T00:00:00+00:00",
                "status": "READY",
                "through": chapter,
                "chapters": 10,
                "source_event_ledger": {
                    "path": "state/event_ledger.jsonl",
                    "exists": True,
                    "sha256": file_sha(repo, "state/event_ledger.jsonl"),
                },
                "source_reader_promise": {
                    "path": "state/project_reader_promise.json",
                    "exists": True,
                    "sha256": file_sha(repo, "state/project_reader_promise.json"),
                },
                "rolling_input_refs": [],
                "context_health_window": [
                    {
                        "chapter": chapter,
                        "context_quality": {
                            "path": context_quality_rel,
                            "exists": True,
                            "sha256": file_sha(repo, context_quality_rel),
                        },
                        "status": "READY",
                    }
                ],
                "context_health_blockers": [],
                "context_health_warnings": [],
                "rolling_blockers": [],
                "rolling_warnings": [],
                "risk_flags": [],
            }
            write(repo, "state/derived/long_health/latest.json", json.dumps(long_health, ensure_ascii=False, indent=2) + "\n")
            quality = json.loads((repo / context_quality_rel).read_text(encoding="utf-8"))
            quality["context_health"]["warnings"].append("changed after long_health")
            write(repo, context_quality_rel, json.dumps(quality, ensure_ascii=False, indent=2) + "\n")
            write_review_route(repo, chapter, "fast", ["human_flavor", "highlights", "ai_taste", "long_health"])

            result = run(repo, "scripts/chapter_evidence.py", "--chapter", chapter)

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("long_health v01_c010 context_quality hash is stale", result.stdout)

    def test_context_quality_blocks_missing_due_p1_thread_debt(self) -> None:
        with copy_repo() as repo:
            chapter = "v01_c006"
            write_complete_chapter_evidence(repo, chapter, 6)
            ledger = {
                "schema_version": 1,
                "generated_at": "2000-01-01T00:00:00+00:00",
                "through": chapter,
                "status": "WARNING",
                "source_priority": ["event_ledger"],
                "source_event_ledger": {
                    "path": "state/event_ledger.jsonl",
                    "exists": True,
                    "sha256": file_sha(repo, "state/event_ledger.jsonl"),
                },
                "threads": [
                    {
                        "thread_id": "missing_sister",
                        "level": "P1",
                        "status": "active",
                        "opened_at": "v01_c001",
                        "last_advanced_at": "v01_c001",
                        "next_required_advance_by": "v01_c006",
                        "payoff_due_by": "v01_c041",
                        "allowed_deferrals": 2,
                        "current_deferrals": 0,
                        "due": True,
                        "advance_due": True,
                        "payoff_due": False,
                        "event_ids": ["not_in_pack"],
                        "source_priority_applied": "event_ledger",
                    }
                ],
                "blockers": [],
                "warnings": [],
            }
            write(repo, "state/derived/thread_debt_ledger.json", json.dumps(ledger, ensure_ascii=False, indent=2) + "\n")

            result = run(repo, "scripts/novel.py", "context-quality", chapter)

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("due P0/P1 thread debt missing", result.stdout)

    def test_derived_ledgers_are_build_only_and_do_not_write_canon(self) -> None:
        with copy_repo() as repo:
            chapter = "v01_c001"
            write_complete_chapter_evidence(repo, chapter, 1)
            canon_before = (repo / "bible/canon.md").read_text(encoding="utf-8")
            chapter_before = (repo / "chapters/v01/c001.md").read_text(encoding="utf-8")
            ledger_before = (repo / "state/event_ledger.jsonl").read_text(encoding="utf-8")

            for command in ("thread-debt-ledger-build", "character-arc-ledger-build", "style-voice-ledger-build"):
                result = run(repo, "scripts/novel.py", command, "--to", chapter, "--write", "--json")
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

            self.assertEqual(canon_before, (repo / "bible/canon.md").read_text(encoding="utf-8"))
            self.assertEqual(chapter_before, (repo / "chapters/v01/c001.md").read_text(encoding="utf-8"))
            self.assertEqual(ledger_before, (repo / "state/event_ledger.jsonl").read_text(encoding="utf-8"))
            for name in ("thread_debt_ledger", "character_arc_ledger", "style_voice_ledger"):
                self.assertTrue((repo / f"state/derived/{name}.json").exists())

    def test_thread_debt_ledger_uses_priority_windows(self) -> None:
        with copy_repo() as repo:
            events = [
                {
                    "event_id": "e001",
                    "chapter": "v01_c001",
                    "type": "thread_opened",
                    "thread_id": "p0_main",
                    "fact": "P0 opens",
                    "evidence_quote": "quote",
                    "consequence": "must advance soon",
                    "verified_by": "human",
                    "importance": "P0",
                }
            ]
            write(repo, "state/event_ledger.jsonl", "\n".join(json.dumps(item, ensure_ascii=False) for item in events) + "\n")

            result = run(repo, "scripts/novel.py", "thread-debt-ledger-build", "--to", "v01_c004", "--json")

            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            data = json.loads(result.stdout)
            thread = data["threads"][0]
            self.assertEqual(thread["level"], "P0")
            self.assertTrue(thread["advance_due"])
            self.assertEqual(thread["next_required_advance_by"], "v01_c004")

    def test_human_flavor_three_chapter_window_is_current_inclusive(self) -> None:
        with copy_repo() as repo:
            for number in range(1, 4):
                chapter = f"v01_c{number:03d}"
                write_complete_chapter_evidence(repo, chapter, number)
                self.assertEqual(run(repo, "scripts/novel.py", "human-flavor-check", chapter, "--write").returncode, 0)

            data = json.loads((repo / "reviews/v01_c003/human_flavor.json").read_text(encoding="utf-8"))

            self.assertLessEqual(data["window"]["last_3_missing_cost_or_misjudgment"], 3)

    def test_review_summary_default_is_five_lines(self) -> None:
        with copy_repo() as repo:
            chapter = "v01_c001"
            write_complete_chapter_evidence(repo, chapter, 1)
            self.assertEqual(run(repo, "scripts/novel.py", "human-flavor-check", chapter, "--write").returncode, 0)
            self.assertEqual(run(repo, "scripts/novel.py", "highlights-review", chapter, "--write").returncode, 0)
            write_review_route(repo, chapter, "fast")

            result = run(repo, "scripts/novel.py", "review-summary", chapter)

            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertEqual(len([line for line in result.stdout.splitlines() if line.strip()]), 5)

    def test_status_is_one_line_and_personal_mode_hides_commercial_advisory(self) -> None:
        with copy_repo() as repo:
            status = run(repo, "scripts/novel.py", "status")
            desk = run(repo, "scripts/novel.py", "desk", "--verbose")
            audit_step_names = {name for name, _command in audit.step_defs_for("project", "v01_c001", "A")}

            self.assertEqual(status.returncode, 0, status.stdout + status.stderr)
            self.assertEqual(len([line for line in status.stdout.splitlines() if line.strip()]), 1)
            self.assertNotIn("commercial_positioning", desk.stdout)
            self.assertNotIn("market-scan-check", audit_step_names)
            self.assertNotIn("commercial-idea-check", audit_step_names)

    def test_ai_and_prose_risk_warn_before_extreme_blocking(self) -> None:
        with copy_repo() as repo:
            chapter = "v01_c001"
            write_complete_chapter_evidence(repo, chapter, 1)
            write(
                repo,
                "chapters/v01/c001.md",
                "# Official\n\n"
                "process file wait report. process file wait report.\n\n"
                "process file wait report. process file wait report.\n\n"
                "process file wait report. process file wait report.\n",
            )

            ai = run(repo, "scripts/novel.py", "ai-taste-check", chapter, "--json", "--no-write")
            prose = run(repo, "scripts/novel.py", "prose-risk-check", chapter, "--json", "--no-write")

            self.assertEqual(ai.returncode, 0, ai.stdout + ai.stderr)
            self.assertIn(json.loads(ai.stdout)["status"], {"CLEAR", "WARNING"})
            self.assertNotEqual(prose.returncode, 1, prose.stdout + prose.stderr)
            self.assertNotEqual(json.loads(prose.stdout)["status"], "BLOCKED")


if __name__ == "__main__":
    unittest.main()
