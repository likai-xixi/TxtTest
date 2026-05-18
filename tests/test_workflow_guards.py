from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
import unittest
import zipfile
import hashlib
import json
import os
from contextlib import contextmanager
from collections.abc import Iterator
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


@contextmanager
def copy_repo() -> Iterator[Path]:
    with tempfile.TemporaryDirectory() as temp:
        target = Path(temp) / "repo"
        shutil.copytree(
            ROOT,
            target,
            ignore=shutil.ignore_patterns(".git", "__pycache__", "backups", "exports", "*.pyc"),
        )
        yield target


def run(repo: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, *args],
        cwd=repo,
        text=True,
        capture_output=True,
        encoding="utf-8",
        errors="replace",
    )


def run_with_env(repo: Path, args: tuple[str, ...], env: dict[str, str]) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, *args],
        cwd=repo,
        text=True,
        capture_output=True,
        encoding="utf-8",
        errors="replace",
        env=env,
    )


def write(repo: Path, relative: str, text: str) -> None:
    path = repo / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")


def file_sha(repo: Path, relative: str) -> str:
    return hashlib.sha256((repo / relative).read_bytes()).hexdigest()


def write_context_quality(repo: Path, chapter: str) -> None:
    context_rel = f"state/context_pack/{chapter}.md"
    manifest_rel = f"state/context_pack/{chapter}.manifest.json"
    quality_rel = f"state/derived/context_quality/{chapter}.json"
    manifest = {
        "schema_version": 2,
        "chapter": chapter,
        "budget_chars": 6000,
        "hard_max_chars": 24000,
        "allow_truncated": False,
        "pack_truncated": False,
        "pack_chars": len((repo / context_rel).read_text(encoding="utf-8")),
        "object_ids": [],
        "ability_ids": [],
        "sections": [
            {"id": "core_freeze", "body_chars": 10, "sources": [{"path": "state/idea_lab/selected.json"}]},
            {"id": "chapter_brief", "body_chars": 10, "sources": [{"path": f"outline/chapter_briefs/{chapter}.md"}]},
            {"id": "authorized_elements_full", "body_chars": 10, "sources": [{"path": f"outline/chapter_briefs/{chapter}.md"}]},
            {"id": "rules_and_boundaries", "body_chars": 10, "sources": [{"path": "bible/rules.md"}]},
        ],
        "input_hashes": [{"path": context_rel, "sha256": file_sha(repo, context_rel)}],
        "context_pack": {"path": context_rel, "sha256": file_sha(repo, context_rel)},
    }
    write(repo, manifest_rel, json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")
    quality = {
        "schema_version": 1,
        "chapter": chapter,
        "status": "READY",
        "pack_path": context_rel,
        "manifest_path": manifest_rel,
        "context_pack_sha256": file_sha(repo, context_rel),
        "manifest_sha256": file_sha(repo, manifest_rel),
        "budget_chars": 6000,
        "pack_chars": manifest["pack_chars"],
        "required_fact_coverage": 1.0,
        "unsupported_key_fact_count": 0,
        "active_thread_coverage": 1.0,
        "irrelevant_section_ratio": 0.0,
        "truncation_count": 0,
        "source_traceability": {"ok": True, "failure_count": 0},
        "input_hashes": {context_rel: file_sha(repo, context_rel)},
        "object_ids": [],
        "ability_ids": [],
        "blockers": [],
        "warnings": [],
    }
    write(repo, quality_rel, json.dumps(quality, ensure_ascii=False, indent=2) + "\n")


def write_minimal_derived_governance(repo: Path, chapter: str) -> None:
    number = int(chapter[-3:])
    start = ((number - 1) // 50) * 50 + 1
    end = start + 49
    write(repo, "state/derived/current_state.yaml", "schema_version: 2\n")
    write(repo, "state/derived/threads/open.yaml", "threads: []\n")
    write(repo, "state/derived/threads/active.yaml", "threads: []\n")
    write(repo, "state/derived/threads/paid_off_index.yaml", "threads: []\n")
    write(repo, f"state/derived/indexes/events_by_chapter/{chapter}.json", "[]\n")
    write(repo, "state/derived/indexes/events_by_type/character_decision.json", "[]\n")
    write(repo, "state/derived/entities/characters/protagonist.yaml", "id: protagonist\n")
    write(repo, "state/derived/arcs/volume_01.md", "# Volume 01 Derived Arc\n")
    write(repo, f"state/derived/arcs/chunk_{start:03d}_{end:03d}.md", f"# Arc Chunk {start:03d}-{end:03d}\n")


MODEL_DISAGREEMENT_READY = """# Model Disagreement

status: CLEAR
codex_action: Ship
deepseek_action: Ship

## 双方一致的问题

- 无阻塞问题。

## Codex 独有问题

- 无。

## DeepSeek 独有问题

- 无。

## 冲突判断

- 未识别到核心冲突。

## 需要人类裁决事项

- 本章是否 Ship。

## 建议动作

- Ship
"""


IDEA_SYNTHESIS_READY = """# Codex Synthesis: {idea}

## Direction A：最强商业钩子

- 一句话卖点：A hook.
- 主角欲望：A desire.
- 核心冲突：A conflict.
- 世界异常：A anomaly.
- 世界观核心规则：A worldview core.
- 世界观硬边界：A hard limits.
- 主角异常原因：A anomaly cause.
- 主角家属/亲密关系：A family anchor.
- 家属剧情功能与风险：A family stakes.
- 前三章约束：A first three constraints.
- 不可违背红线：A forbidden changes.
- 仍可开放的问题：A open questions.
- 前三章验证点：A checks.
- 最大风险：A risk.
- 适合继续的信号：A continue.
- 不适合继续的信号：A stop.

## Direction B：最强人物驱动

- 一句话卖点：B hook.
- 主角欲望：B desire.
- 核心冲突：B conflict.
- 世界异常：B anomaly.
- 世界观核心规则：B worldview core.
- 世界观硬边界：B hard limits.
- 主角异常原因：B anomaly cause.
- 主角家属/亲密关系：B family anchor.
- 家属剧情功能与风险：B family stakes.
- 前三章约束：B first three constraints.
- 不可违背红线：B forbidden changes.
- 仍可开放的问题：B open questions.
- 前三章验证点：B checks.
- 最大风险：B risk.
- 适合继续的信号：B continue.
- 不适合继续的信号：B stop.

## Direction C：最大差异化/反套路

- 一句话卖点：C hook.
- 主角欲望：C desire.
- 核心冲突：C conflict.
- 世界异常：C anomaly.
- 世界观核心规则：C worldview core.
- 世界观硬边界：C hard limits.
- 主角异常原因：C anomaly cause.
- 主角家属/亲密关系：C family anchor.
- 家属剧情功能与风险：C family stakes.
- 前三章约束：C first three constraints.
- 不可违背红线：C forbidden changes.
- 仍可开放的问题：C open questions.
- 前三章验证点：C checks.
- 最大风险：C risk.
- 适合继续的信号：C continue.
- 不适合继续的信号：C stop.
"""


COMPLETE_BRIEF = """# {chapter} Brief

## 本章功能

建立本章案件和主角行动目标。

## 开篇吸引点

用具体异常场面开局。

## 主角目标

主角要在本章完成一次可失败的调查。

## 主要阻力

现场证据被平台和利益方同时遮蔽。

## 主角主动选择

主角选择冒险保留关键异常证据。

## 本章推进

完成阶段性案件推进。

## 信息增量

读者知道异常并非普通故障。

## 章末问题

幕后是谁在制造异常信号？

## 本章使用设定

只使用 context pack 中已经允许的设定。

## 本章可用人物状态

主角保持不信鬼但愿意调查异常。

## 本章可用道具 / 装备

只使用已记录的检测设备。

## 本章可用道具 IDs

none

## 本章可用技能 / 能力

只使用已记录的数据分析能力。

## 本章可用技能 IDs

none

## 能力限制 / 代价

能力不能直接证明鬼存在，且会误判。

## 未解决伏笔

保留旧案信号伏笔。

## 新增设定

无。

## 本章允许新增元素

L0 场景细节和 L1 一次性线索可以新增；没有 L3/L4 新机制。

## 本章禁止临场解决

不得靠未授权新道具、新能力或新规则解决本章核心问题。

## 伏笔：新开 / 推进 / 回收

推进旧案信号。

## 本章禁止新增

禁止新增万能能力。

## 本章禁止解决

禁止解决幕后主谜题。

## 禁止新增 / 禁止解决 / 禁止模仿

禁止换皮参考作品桥段。
"""


def write_ready_idea_lab(repo: Path, idea: str) -> str:
    lab = f"state/idea_lab/{idea}"
    write(repo, f"{lab}/original_idea.md", f"# Original Idea: {idea}\n\n赛博民俗悬疑。\n")
    write(repo, f"{lab}/deepseek_idea.md", f"# DeepSeek Idea Directions: {idea}\n\nDirection A/B/C ready.\n")
    write(repo, f"external_runs/deepseek/{idea}/idea.raw.json", '{"choices":[{"message":{"content":"ok"}}]}\n')
    write(repo, f"{lab}/product_founder_review.md", f"# Product Founder Review: {idea}\n\nA has the clearest hook.\n")
    write(repo, f"{lab}/technical_lead_review.md", f"# Technical Lead Review: {idea}\n\nKeep rules small for three chapters.\n")
    write(repo, f"{lab}/qa_release_review.md", f"# QA Release Review: {idea}\n\nGate A needs protagonist agency evidence.\n")
    write(repo, f"{lab}/codex_synthesis.md", IDEA_SYNTHESIS_READY.format(idea=idea))
    return lab


def write_core_setting_freeze(repo: Path, idea: str = "idea_core") -> None:
    lab = write_ready_idea_lab(repo, idea)
    write(repo, f"{lab}/selection.json", json.dumps({"idea_id": idea, "choice": "A", "verified_by": "human"}, ensure_ascii=False) + "\n")
    fields = {
        "worldview_core": "A worldview core.",
        "worldview_hard_limits": "A hard limits.",
        "protagonist_anomaly_cause": "A anomaly cause.",
        "protagonist_family": "A family anchor.",
        "family_stakes": "A family stakes.",
        "first_three_chapter_constraints": "A first three constraints.",
        "forbidden_changes": "A forbidden changes.",
        "open_questions_allowed": "A open questions.",
    }
    evidence_paths = {
        "original_idea": f"{lab}/original_idea.md",
        "deepseek_idea": f"{lab}/deepseek_idea.md",
        "deepseek_raw": f"external_runs/deepseek/{idea}/idea.raw.json",
        "product_founder_review": f"{lab}/product_founder_review.md",
        "technical_lead_review": f"{lab}/technical_lead_review.md",
        "qa_release_review": f"{lab}/qa_release_review.md",
        "codex_synthesis": f"{lab}/codex_synthesis.md",
        "selection": f"{lab}/selection.json",
    }
    evidence = {
        key: {"path": path, "sha256": file_sha(repo, path), "mtime": (repo / path).stat().st_mtime}
        for key, path in evidence_paths.items()
    }
    freeze = {
        "idea_id": idea,
        "status": "LOCKED",
        "locked_at": "2026-01-01T00:00:00+00:00",
        "selected_direction": "A",
        "human_approved": True,
        "verified_by": "human",
        "fields": fields,
        "evidence": evidence,
        "writes_canon": False,
        "writes_chapters": False,
        "writes_event_ledger": False,
    }
    write(repo, f"{lab}/core_setting_freeze.json", json.dumps(freeze, ensure_ascii=False, indent=2) + "\n")
    write(
        repo,
        f"{lab}/core_setting_freeze.md",
        "# Core Setting Freeze: idea_core\n\n## 世界观核心规则\n\nA worldview core.\n\n## 主角异常原因\n\nA anomaly cause.\n\n## 主角家属/亲密关系\n\nA family anchor.\n",
    )
    write(
        repo,
        "state/idea_lab/selected.json",
        json.dumps(
            {
                "idea_id": idea,
                "selection_path": f"{lab}/selection.json",
                "core_setting_freeze_path": f"{lab}/core_setting_freeze.json",
            },
            ensure_ascii=False,
        )
        + "\n",
    )


def write_brief_landing(repo: Path, chapter: str = "v01_c001", source: str = "Manual") -> None:
    brief_rel = f"outline/chapter_briefs/{chapter}.md"
    if not (repo / brief_rel).exists():
        write(repo, brief_rel, COMPLETE_BRIEF.format(chapter=chapter))
    selection = {
        "chapter": chapter,
        "choice": source,
        "reason": "human selected official brief",
        "selected_candidates": [],
    }
    write(repo, f"state/selections/{chapter}_brief.json", json.dumps(selection) + "\n")
    landing = {
        "chapter": chapter,
        "recorded_at": "2000-01-01T00:00:00+00:00",
        "source": source,
        "landed_by": "Codex",
        "attestation": "Human selected and Codex landed the official brief.",
        "inputs": [{"path": f"state/selections/{chapter}_brief.json", "sha256": file_sha(repo, f"state/selections/{chapter}_brief.json")}],
        "official_brief": {"path": brief_rel, "sha256": file_sha(repo, brief_rel)},
    }
    write(repo, f"reviews/{chapter}/brief_landing.json", json.dumps(landing) + "\n")
    write(repo, f"reviews/{chapter}/brief_landing.md", "# Brief Landing\n\nsource: Manual\n")


def run_deepseek_module_with_response(
    repo: Path,
    module: str,
    response_literal: str,
    *args: str,
) -> subprocess.CompletedProcess:
    env = os.environ.copy()
    env["DEEPSEEK_API_KEY"] = "test-key"
    code = (
        "import sys\n"
        "sys.path.insert(0, 'scripts')\n"
        f"import {module} as target\n"
        f"target.call_deepseek = lambda payload, api_key: {response_literal}\n"
        "raise SystemExit(target.main())\n"
    )
    return subprocess.run(
        [sys.executable, "-c", code, *args],
        cwd=repo,
        text=True,
        capture_output=True,
        encoding="utf-8",
        errors="replace",
        env=env,
    )


def write_auxiliary_reviews(repo: Path, chapter: str, status: str = "CLEAR") -> None:
    for name in ("ai_taste", "web_satisfaction", "retention_risk", "originality"):
        findings = "- Checked."
        if name == "originality":
            findings = "- 撞梗、换皮、设定名词、人物关系、句式、对白节奏、标志性表达风险已检查。"
        write(
            repo,
            f"reviews/{chapter}/{name}.md",
            f"# {name}: {chapter}\n\nstatus: {status}\n\n## Findings\n\n{findings}\n",
        )


def write_complete_chapter_evidence(repo: Path, chapter: str, number: int) -> None:
    volume = chapter[:3]
    chapter_file = f"c{number:03d}.md"
    chapter_rel = f"chapters/{volume}/{chapter_file}"
    context_rel = f"state/context_pack/{chapter}.md"
    brief_rel = f"outline/chapter_briefs/{chapter}.md"
    draft_rel = f"drafts/codex/{chapter}.md"

    write(repo, context_rel, f"context for {chapter}\n")
    write(repo, brief_rel, "brief " + ("A" * 320) + "\n")
    write(repo, chapter_rel, f"Official chapter {chapter} with independent Codex prose.\n")
    write(repo, draft_rel, f"Codex candidate {chapter}.\n")
    write_context_quality(repo, chapter)
    write_minimal_derived_governance(repo, chapter)
    write(repo, f"reviews/{chapter}/candidate_selection.md", f"# Candidate Selection\n\nchoice: Codex\n")
    selection = {
        "chapter": chapter,
        "choice": "Codex",
        "reason": "synthetic ready evidence",
        "selected_candidates": [{"path": draft_rel, "sha256": file_sha(repo, draft_rel)}],
    }
    write(repo, f"state/selections/{chapter}.json", json.dumps(selection) + "\n")
    landing = {
        "chapter": chapter,
        "recorded_at": "2000-01-01T00:00:00+00:00",
        "selected_direction": "Codex",
        "source": "Codex",
        "official_source": "Codex",
        "landed_by": "Codex",
        "integrated_by": "Codex",
        "integration_mode": "codex_integrated",
        "attestation": "Codex integrated from context pack, brief, and selected direction.",
        "codex_integrated": True,
        "deepseek_direct_adoption": False,
        "direct_deepseek_candidate": None,
        "inputs": [
            {"path": context_rel, "sha256": file_sha(repo, context_rel)},
            {"path": f"state/derived/context_quality/{chapter}.json", "sha256": file_sha(repo, f"state/derived/context_quality/{chapter}.json")},
            {"path": brief_rel, "sha256": file_sha(repo, brief_rel)},
            {"path": f"state/selections/{chapter}.json", "sha256": file_sha(repo, f"state/selections/{chapter}.json")},
            {"path": draft_rel, "sha256": file_sha(repo, draft_rel)},
        ],
        "official_chapter": {"path": chapter_rel, "sha256": file_sha(repo, chapter_rel)},
    }
    write(repo, f"reviews/{chapter}/chapter_landing.json", json.dumps(landing) + "\n")
    write(repo, f"reviews/{chapter}/chapter_landing.md", "# Chapter Landing\n\nselected_direction: Codex\n")
    write(repo, f"reviews/{chapter}/codex_integrated_review.md", "# Codex Review\n\naction: Ship\n")
    write(repo, f"reviews/{chapter}/deepseek_integrated_review.md", "# DeepSeek Review\n\naction: Ship\n")
    manifest = {
        "codex": {
            "recorded_at": "2000-01-01T00:00:00+00:00",
            "inputs": [
                {"path": context_rel, "sha256": file_sha(repo, context_rel)},
                {"path": chapter_rel, "sha256": file_sha(repo, chapter_rel)},
            ],
        },
        "deepseek": {
            "recorded_at": "2000-01-01T00:00:00+00:00",
            "inputs": [
                {"path": context_rel, "sha256": file_sha(repo, context_rel)},
                {"path": chapter_rel, "sha256": file_sha(repo, chapter_rel)},
            ],
        },
    }
    write(repo, f"reviews/{chapter}/review_manifest.json", json.dumps(manifest) + "\n")
    write(repo, f"reviews/{chapter}/model_disagreement.md", MODEL_DISAGREEMENT_READY)
    write(repo, f"reviews/{chapter}/continuity.md", "# Continuity\n\nstatus: CLEAR\np0_count: 0\np1_count: 0\n")
    write(repo, f"reviews/{chapter}/decision.md", "# Decision\n\ndecision: Ship\n")
    write_auxiliary_reviews(repo, chapter)


def write_human_events(repo: Path, count: int) -> None:
    lines = []
    for number in range(1, count + 1):
        chapter = f"v01_c{number:03d}"
        lines.append(
            json.dumps(
                {
                    "event_id": f"{chapter}_e001",
                    "chapter": chapter,
                    "type": "character_decision",
                    "fact": f"fact {number}",
                    "evidence_quote": f"Official chapter {chapter}",
                    "consequence": f"consequence {number}",
                    "verified_by": "human",
                }
            )
        )
    write(repo, "state/event_ledger.jsonl", "\n".join(lines) + "\n")


class WorkflowGuardTests(unittest.TestCase):
    def test_minimal_chapter_happy_path_closes_ship(self) -> None:
        with copy_repo() as temp:
            repo = temp
            write(repo, "outline/premise.md", "# Premise\n\nA focused pilot premise.\n")
            write(repo, "outline/volume_01.md", "# Volume 01\n\nPilot arc.\n")
            write(repo, "bible/characters.yaml", "characters:\n  - id: protagonist\n    current_state: ready\n")
            write(repo, "bible/relationships.yaml", "relationships: []\n")
            write(repo, "bible/locations.yaml", "locations: []\n")
            write(repo, "bible/rules.md", "# Rules\n\nNo special rule yet.\n")
            write(repo, "bible/style_guide.md", "# Style Guide\n\nClear, direct prose.\n")
            write_core_setting_freeze(repo)
            write(repo, "outline/chapter_briefs/v01_c001.md", COMPLETE_BRIEF.format(chapter="v01_c001"))

            self.assertEqual(run(repo, "scripts/build_derived_state.py").returncode, 0)
            context = run(repo, "scripts/build_context_pack.py", "--chapter", "v01_c001", "--limit", "5000")
            self.assertEqual(context.returncode, 0, context.stdout + context.stderr)

            subprocess.run(["git", "init"], cwd=repo, check=True, capture_output=True)
            subprocess.run(["git", "config", "user.name", "Test"], cwd=repo, check=True)
            subprocess.run(["git", "config", "user.email", "test@example.local"], cwd=repo, check=True)
            subprocess.run(["git", "add", "."], cwd=repo, check=True)
            subprocess.run(["git", "commit", "-m", "baseline"], cwd=repo, check=True, capture_output=True)

            write(repo, "chapters/v01/c001.md", "Official chapter text with a concrete protagonist choice.\n")
            write(repo, "drafts/codex/v01_c001.md", "Codex candidate text.\n")
            selection = run(
                repo,
                "scripts/novel.py",
                "select-candidate",
                "v01_c001",
                "--choice",
                "Codex",
                "--reason",
                "human selected Codex candidate",
                "--notes",
                "human selected Codex direction",
            )
            self.assertEqual(selection.returncode, 0, selection.stderr)
            landing = run(
                repo,
                "scripts/novel.py",
                "land",
                "v01_c001",
                "--selected-direction",
                "Codex",
                "--attestation",
                "Codex integrated the official chapter from the context pack, brief, and selected direction.",
            )
            self.assertEqual(landing.returncode, 0, landing.stderr)
            manifest = run(repo, "scripts/novel.py", "codex-review-start", "v01_c001")
            self.assertEqual(manifest.returncode, 0, manifest.stderr)
            deepseek_manifest = run(
                repo,
                "scripts/review_manifest.py",
                "--chapter",
                "v01_c001",
                "--reviewer",
                "deepseek",
                "--input",
                "state/context_pack/v01_c001.md",
                "--input",
                "chapters/v01/c001.md",
            )
            self.assertEqual(deepseek_manifest.returncode, 0, deepseek_manifest.stdout + deepseek_manifest.stderr)
            write(repo, "reviews/v01_c001/codex_integrated_review.md", "# Codex Review\n\naction: Ship\n")
            write(repo, "reviews/v01_c001/deepseek_integrated_review.md", "# DeepSeek Review\n\naction: Ship\n")
            review = run(repo, "scripts/novel.py", "review", "v01_c001")
            self.assertEqual(review.returncode, 0, review.stdout + review.stderr)
            write_auxiliary_reviews(repo, "v01_c001")
            event = run(
                repo,
                "scripts/novel.py",
                "event",
                "v01_c001",
                "--type",
                "character_decision",
                "--fact",
                "The protagonist chooses action.",
                "--evidence-quote",
                "concrete protagonist choice",
                "--consequence",
                "The pilot can continue.",
            )
            self.assertEqual(event.returncode, 0, event.stderr)
            close = run(
                repo,
                "scripts/novel.py",
                "close",
                "v01_c001",
                "--decision",
                "Ship",
                "--keep",
                "protagonist agency",
                "--change",
                "none",
                "--next-verify",
                "chapter two hook",
                "--setting-boundary",
                "no new canon",
                "--failure-condition",
                "goal unclear",
            )
            self.assertEqual(close.returncode, 0, close.stdout + close.stderr)

    def test_novel_chapter_evidence_wrapper_reports_not_ready(self) -> None:
        with copy_repo() as temp:
            repo = temp
            result = run(repo, "scripts/novel.py", "chapter-evidence", "v01_c001")

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("status: NOT_READY", result.stdout)

    def test_novel_new_wrapper_commands_are_available(self) -> None:
        with copy_repo() as temp:
            repo = temp
            help_result = run(repo, "scripts/novel.py", "--help")
            self.assertEqual(help_result.returncode, 0)
            for command in (
                "go",
                "draft",
                "write",
                "brief-candidates",
                "deepseek-brief",
                "select-brief",
                "land-brief",
                "setting",
                "desk",
                "core-freeze-check",
                "idea",
                "idea-form",
                "idea-select",
                "self-test",
                "diff-scope",
                "continuity",
                "compare",
                "evidence",
            ):
                self.assertIn(command, help_result.stdout)

            diff_scope = run(repo, "scripts/novel.py", "diff-scope", "--role", "chapter", "--chapter", "v01_c001")
            self.assertEqual(diff_scope.returncode, 0, diff_scope.stdout + diff_scope.stderr)

            evidence = run(repo, "scripts/novel.py", "evidence", "v01_c001")
            self.assertNotEqual(evidence.returncode, 0)
            self.assertIn("status: NOT_READY", evidence.stdout)

    def test_go_blocks_before_core_setting_freeze(self) -> None:
        with copy_repo() as temp:
            repo = temp
            result = run(repo, "scripts/novel.py", "go", "--name", "Test Book")

            self.assertNotEqual(result.returncode, 0)
            self.assertTrue((repo / ".git").exists())
            self.assertFalse((repo / "setup_answers.md").exists())
            self.assertIn("DEEPSEEK_API_KEY:", result.stdout)
            self.assertIn("core setting freeze: NOT_READY", result.stdout)

    def test_draft_blocks_before_core_setting_freeze(self) -> None:
        with copy_repo() as temp:
            repo = temp
            result = run(repo, "scripts/novel.py", "draft", "v01_c001")

            self.assertNotEqual(result.returncode, 0)
            self.assertFalse((repo / "setup_answers.md").exists())
            self.assertIn("core setting freeze: NOT_READY", result.stdout)

    def test_write_blocks_before_core_setting_freeze(self) -> None:
        with copy_repo() as temp:
            repo = temp
            result = run(repo, "scripts/novel.py", "write")

            self.assertNotEqual(result.returncode, 0)
            self.assertFalse((repo / "setup_answers.md").exists())
            self.assertIn("chapter: v01_c001", result.stdout)
            self.assertIn("core setting freeze: NOT_READY", result.stdout)

    def test_desk_handles_gbk_parent_output(self) -> None:
        with copy_repo() as temp:
            repo = temp
            env = os.environ.copy()
            env["PYTHONIOENCODING"] = "gbk:strict"

            result = run_with_env(repo, ("scripts/novel.py", "desk"), env)

            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn("Project Status", result.stdout)
            self.assertIn("Next Prompt", result.stdout)

    def test_setting_parks_note_without_changing_canon_or_ledger(self) -> None:
        with copy_repo() as temp:
            repo = temp
            canon_before = (repo / "bible/canon.md").read_text(encoding="utf-8")
            ledger_before = (repo / "state/event_ledger.jsonl").read_text(encoding="utf-8")

            result = run(
                repo,
                "scripts/novel.py",
                "setting",
                "--chapter",
                "v01_c001",
                "--text",
                "灵犀镜只能照见说谎者的影子。",
            )

            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn("parked setting", result.stdout)
            self.assertIn(
                "灵犀镜只能照见说谎者的影子。",
                (repo / "bible/open_questions.md").read_text(encoding="utf-8"),
            )
            self.assertIn(
                "灵犀镜只能照见说谎者的影子。",
                (repo / "outline/chapter_briefs/v01_c001.md").read_text(encoding="utf-8"),
            )
            self.assertEqual(canon_before, (repo / "bible/canon.md").read_text(encoding="utf-8"))
            self.assertEqual(ledger_before, (repo / "state/event_ledger.jsonl").read_text(encoding="utf-8"))

    def test_start_blocks_without_core_setting_freeze(self) -> None:
        with copy_repo() as temp:
            repo = temp
            write(repo, "outline/chapter_briefs/v01_c001.md", COMPLETE_BRIEF.format(chapter="v01_c001"))

            result = run(repo, "scripts/novel.py", "start", "v01_c001")

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("core setting freeze", result.stderr)
            self.assertFalse((repo / "state/context_pack/v01_c001.md").exists())

    def test_start_default_context_limit_allows_ready_initial_pilot(self) -> None:
        with copy_repo() as temp:
            repo = temp
            write_core_setting_freeze(repo)
            write(repo, "outline/chapter_briefs/v01_c001.md", COMPLETE_BRIEF.format(chapter="v01_c001"))
            write_brief_landing(repo, "v01_c001")

            result = run(repo, "scripts/novel.py", "start", "v01_c001")

            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertTrue((repo / "state/context_pack/v01_c001.md").exists())
            self.assertTrue((repo / "state/context_pack/v01_c001.manifest.json").exists())
            quality = json.loads((repo / "state/derived/context_quality/v01_c001.json").read_text(encoding="utf-8"))
            self.assertEqual(quality["status"], "READY")
            self.assertEqual(quality["budget_chars"], 6000)

    def test_write_routes_placeholder_brief_to_brief_candidates(self) -> None:
        with copy_repo() as temp:
            repo = temp
            write_core_setting_freeze(repo)

            result = run(repo, "scripts/novel.py", "write", "v01_c001")

            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertTrue((repo / "state/context_pack/v01_c001_brief.md").exists())
            self.assertFalse((repo / "state/context_pack/v01_c001.md").exists())
            self.assertIn("drafts/codex/v01_c001_brief.md", result.stdout)
            self.assertIn("select-brief", result.stdout)

    def test_start_requires_brief_landing_after_ready_brief(self) -> None:
        with copy_repo() as temp:
            repo = temp
            write_core_setting_freeze(repo)
            write(repo, "outline/chapter_briefs/v01_c001.md", COMPLETE_BRIEF.format(chapter="v01_c001"))

            result = run(repo, "scripts/novel.py", "start", "v01_c001")

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("missing brief landing record", result.stderr)
            self.assertFalse((repo / "state/context_pack/v01_c001.md").exists())

    def test_deepseek_generate_blocks_without_core_setting_freeze(self) -> None:
        with copy_repo() as temp:
            repo = temp
            write(repo, "state/context_pack/v01_c001.md", "context\n")

            result = run(repo, "scripts/run_deepseek_generate.py", "--chapter", "v01_c001", "--dry-run")

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("core setting freeze", result.stderr)
            self.assertFalse((repo / "external_runs/deepseek/v01_c001/generate.prompt.md").exists())

    def test_deepseek_brief_dry_run_blocks_without_core_setting_freeze(self) -> None:
        with copy_repo() as temp:
            repo = temp
            write(repo, "state/context_pack/v01_c001_brief.md", "brief pack\n")

            result = run(repo, "scripts/run_deepseek_brief.py", "--chapter", "v01_c001", "--dry-run")

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("core setting freeze", result.stderr)
            self.assertFalse((repo / "external_runs/deepseek/v01_c001/brief.prompt.md").exists())

    def test_deepseek_brief_dry_run_prompt_requires_complete_brief_fields(self) -> None:
        with copy_repo() as temp:
            repo = temp
            write_core_setting_freeze(repo)
            write(repo, "state/context_pack/v01_c001_brief.md", "brief pack\n")

            result = run(repo, "scripts/run_deepseek_brief.py", "--chapter", "v01_c001", "--dry-run")

            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            prompt = (repo / "external_runs/deepseek/v01_c001/brief.prompt.md").read_text(encoding="utf-8")
            required = [
                "本章功能",
                "开篇吸引点",
                "主角目标",
                "主要阻力",
                "主角主动选择",
                "本章推进",
                "信息增量",
                "章末问题",
                "本章使用设定",
                "本章可用人物状态",
                "本章可用道具 / 装备",
                "本章可用道具 IDs",
                "本章可用技能 / 能力",
                "本章可用技能 IDs",
                "能力限制 / 代价",
                "未解决伏笔",
                "新增设定",
                "本章允许新增元素",
                "本章禁止临场解决",
                "伏笔：新开 / 推进 / 回收",
                "本章禁止新增",
                "本章禁止解决",
                "禁止新增 / 禁止解决 / 禁止模仿",
            ]
            for field in required:
                self.assertIn(field, prompt)
            self.assertIn("字段名必须逐字一致", prompt)
            self.assertIn("不能删减、合并、改名或换成 JSON", prompt)
            self.assertIn("L0/L1/L2/L3/L4", prompt)
            self.assertIn("不得写“待定”“待填”“TODO”“待人类确认”", prompt)

    def test_status_prefers_ready_idea_lab_over_questionnaire(self) -> None:
        with copy_repo() as temp:
            repo = temp
            write_ready_idea_lab(repo, "idea_status")
            result = run(repo, "scripts/novel.py", "status")

            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn("idea-select --id idea_status", result.stdout)
            self.assertNotIn("python scripts/novel.py questionnaire", result.stdout)

    def test_status_without_idea_lab_still_prompts_questionnaire(self) -> None:
        with copy_repo() as temp:
            repo = temp
            for item in (repo / "state/idea_lab").iterdir():
                if item.is_dir():
                    shutil.rmtree(item)

            result = run(repo, "scripts/novel.py", "status")

            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn("python scripts/novel.py idea --text", result.stdout)

    def test_idea_requires_deepseek_key_before_writing_lab(self) -> None:
        with copy_repo() as temp:
            repo = temp
            env = os.environ.copy()
            env.pop("DEEPSEEK_API_KEY", None)

            result = run_with_env(repo, ("scripts/novel.py", "idea", "--id", "idea_test", "--text", "赛博民俗悬疑"), env)

            self.assertEqual(result.returncode, 2)
            self.assertIn("DEEPSEEK_API_KEY", result.stderr)
            self.assertFalse((repo / "state/idea_lab/idea_test").exists())

    def test_idea_form_creates_short_seed(self) -> None:
        with copy_repo() as temp:
            repo = temp
            result = run(repo, "scripts/novel.py", "idea-form")

            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertTrue((repo / "idea_seed.md").exists())
            self.assertIn("核心想法", (repo / "idea_seed.md").read_text(encoding="utf-8"))

    def test_idea_select_writes_only_pilot_assets(self) -> None:
        with copy_repo() as temp:
            repo = temp
            idea = "idea_test"
            lab = write_ready_idea_lab(repo, idea)
            canon_before = (repo / "bible/canon.md").read_text(encoding="utf-8")
            ledger_before = (repo / "state/event_ledger.jsonl").read_text(encoding="utf-8")

            result = run(
                repo,
                "scripts/novel.py",
                "idea-select",
                "--id",
                idea,
                "--choice",
                "A",
                "--reason",
                "商业钩子最强",
            )

            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertTrue((repo / f"{lab}/selection.json").exists())
            self.assertTrue((repo / f"{lab}/core_setting_freeze.json").exists())
            self.assertTrue((repo / "state/idea_lab/selected.json").exists())
            self.assertIn("idea_lab_id: idea_test", (repo / "outline/premise.md").read_text(encoding="utf-8"))
            self.assertIn("开书前核心设定冻结", (repo / "outline/premise.md").read_text(encoding="utf-8"))
            self.assertIn("不得直接视为 canon", (repo / "bible/open_questions.md").read_text(encoding="utf-8"))
            self.assertIn("Gate A", (repo / "outline/gate_a_3_chapters.md").read_text(encoding="utf-8"))
            self.assertIn("待定", (repo / "outline/chapter_briefs/v01_c001.md").read_text(encoding="utf-8"))
            self.assertEqual(canon_before, (repo / "bible/canon.md").read_text(encoding="utf-8"))
            self.assertEqual(ledger_before, (repo / "state/event_ledger.jsonl").read_text(encoding="utf-8"))
            self.assertFalse((repo / "chapters/v01/c001.md").exists())

    def test_idea_select_rejects_placeholder_core_setting_field(self) -> None:
        with copy_repo() as temp:
            repo = temp
            idea = "idea_placeholder_core"
            lab = write_ready_idea_lab(repo, idea)
            text = (repo / f"{lab}/codex_synthesis.md").read_text(encoding="utf-8")
            write(repo, f"{lab}/codex_synthesis.md", text.replace("A anomaly cause.", ""))

            result = run(repo, "scripts/novel.py", "idea-select", "--id", idea, "--choice", "A")

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("core setting freeze missing field protagonist_anomaly_cause", result.stderr)
            self.assertFalse((repo / f"{lab}/selection.json").exists())
            self.assertFalse((repo / f"{lab}/selection.md").exists())
            self.assertFalse((repo / f"{lab}/core_setting_freeze.json").exists())
            self.assertFalse((repo / "state/idea_lab/selected.json").exists())

    def test_core_freeze_check_detects_changed_evidence(self) -> None:
        with copy_repo() as temp:
            repo = temp
            write_core_setting_freeze(repo, "idea_changed")
            write(repo, "state/idea_lab/idea_changed/codex_synthesis.md", IDEA_SYNTHESIS_READY.format(idea="idea_changed") + "\nchanged\n")

            result = run(repo, "scripts/novel.py", "core-freeze-check")

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("status: NOT_READY", result.stdout)
            self.assertIn("changed after freeze", result.stdout)

    def test_idea_select_requires_multi_agent_outputs(self) -> None:
        with copy_repo() as temp:
            repo = temp
            idea = "idea_missing_agent"
            lab = f"state/idea_lab/{idea}"
            write(repo, f"{lab}/original_idea.md", "# Original\n\n想法。\n")
            write(repo, f"{lab}/deepseek_idea.md", "# DeepSeek\n\nDirections.\n")

            result = run(repo, "scripts/novel.py", "idea-select", "--id", idea, "--choice", "A")

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("missing idea-lab input", result.stderr)

    def test_idea_select_requires_structured_codex_synthesis(self) -> None:
        with copy_repo() as temp:
            repo = temp
            idea = "idea_bad_synthesis"
            lab = write_ready_idea_lab(repo, idea)
            write(
                repo,
                f"{lab}/codex_synthesis.md",
                f"# Codex Synthesis: {idea}\n\n## Direction A\n\n- 一句话卖点：Only one field.\n",
            )

            result = run(repo, "scripts/novel.py", "idea-select", "--id", idea, "--choice", "A")

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("codex_synthesis.md missing Direction B", result.stderr)

    def test_idea_select_rejects_stale_agent_outputs(self) -> None:
        with copy_repo() as temp:
            repo = temp
            idea = "idea_stale_agent"
            lab = write_ready_idea_lab(repo, idea)
            old_time = 1000
            new_time = 2000
            os.utime(repo / f"{lab}/product_founder_review.md", (old_time, old_time))
            os.utime(repo / f"{lab}/original_idea.md", (new_time, new_time))
            os.utime(repo / f"{lab}/deepseek_idea.md", (new_time, new_time))

            result = run(repo, "scripts/novel.py", "idea-select", "--id", idea, "--choice", "A")

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("older than idea inputs", result.stderr)

    def test_idea_force_cleans_stale_agent_outputs(self) -> None:
        with copy_repo() as temp:
            repo = temp
            idea = "idea_force"
            lab = write_ready_idea_lab(repo, idea)
            write(repo, f"{lab}/selection.json", "{}\n")
            write(repo, f"{lab}/selection.md", "old selection\n")
            write(
                repo,
                "scripts/run_deepseek_idea.py",
                """from __future__ import annotations
import argparse
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument("--idea-id", required=True)
parser.add_argument("--text", required=True)
parser.add_argument("--model")
parser.add_argument("--temperature")
parser.add_argument("--max-tokens")
args = parser.parse_args()
root = Path(__file__).resolve().parents[1]
lab = root / "state" / "idea_lab" / args.idea_id
lab.mkdir(parents=True, exist_ok=True)
(lab / "deepseek_idea.md").write_text(f"# DeepSeek Idea Directions: {args.idea_id}\\n\\nnew deepseek\\n", encoding="utf-8")
print("OK: stub deepseek idea")
""",
            )
            env = os.environ.copy()
            env["DEEPSEEK_API_KEY"] = "test-key"

            result = run_with_env(
                repo,
                ("scripts/novel.py", "idea", "--id", idea, "--text", "新想法", "--force"),
                env,
            )

            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertFalse((repo / f"{lab}/product_founder_review.md").exists())
            self.assertFalse((repo / f"{lab}/technical_lead_review.md").exists())
            self.assertFalse((repo / f"{lab}/qa_release_review.md").exists())
            self.assertFalse((repo / f"{lab}/codex_synthesis.md").exists())
            self.assertFalse((repo / f"{lab}/selection.json").exists())
            self.assertFalse((repo / f"{lab}/selection.md").exists())
            self.assertIn("新想法", (repo / f"{lab}/original_idea.md").read_text(encoding="utf-8"))

    def test_close_ship_requires_structured_candidate_selection(self) -> None:
        with copy_repo() as temp:
            repo = temp
            write(repo, "state/context_pack/v01_c001.md", "context\n")
            write(repo, "chapters/v01/c001.md", "Official chapter text.\n")
            write(repo, "reviews/v01_c001/codex_integrated_review.md", "# Codex Review\n\n建议动作: Ship\n")
            write(repo, "reviews/v01_c001/deepseek_integrated_review.md", "# DeepSeek Review\n\n建议动作: Ship\n")
            write(repo, "reviews/v01_c001/model_disagreement.md", "# Model Disagreement\n\n无核心冲突。\n")
            write(
                repo,
                "reviews/v01_c001/continuity.md",
                "# Continuity\n\nstatus: CLEAR\np0_count: 0\np1_count: 0\n",
            )
            write(
                repo,
                "reviews/v01_c001/review_manifest.json",
                '{"codex":{"inputs":[]},"deepseek":{"inputs":[]}}\n',
            )
            event = run(
                repo,
                "scripts/novel.py",
                "event",
                "v01_c001",
                "--type",
                "character_decision",
                "--fact",
                "fact",
                "--evidence-quote",
                "Official chapter text",
                "--consequence",
                "consequence",
            )
            self.assertEqual(event.returncode, 0, event.stderr)

            close = run(repo, "scripts/novel.py", "close", "v01_c001", "--decision", "Ship")

            self.assertNotEqual(close.returncode, 0)
            self.assertIn("missing structured candidate selection", close.stdout)

    def test_close_non_ship_records_decision_without_chapter_evidence(self) -> None:
        with copy_repo() as temp:
            repo = temp
            close = run(
                repo,
                "scripts/novel.py",
                "close",
                "v01_c001",
                "--decision",
                "Kill chapter",
                "--notes",
                "No usable opening.",
            )

            self.assertEqual(close.returncode, 0, close.stdout + close.stderr)
            decision = (repo / "reviews/v01_c001/decision.md").read_text(encoding="utf-8")
            self.assertIn("decision: Kill chapter", decision)
            self.assertIn("No usable opening.", decision)

    def test_close_rewrite_brief_records_structured_failure_without_chapter_evidence(self) -> None:
        with copy_repo() as temp:
            repo = temp
            close = run(
                repo,
                "scripts/novel.py",
                "close",
                "v01_c001",
                "--decision",
                "Rewrite brief",
                "--keep",
                "core premise",
                "--change",
                "opening conflict",
                "--next-verify",
                "new first scene",
                "--setting-boundary",
                "no new canon",
                "--failure-condition",
                "goal remains unclear",
            )

            self.assertEqual(close.returncode, 0, close.stdout + close.stderr)
            decision = (repo / "reviews/v01_c001/decision.md").read_text(encoding="utf-8")
            self.assertIn("decision: Rewrite brief", decision)

    def test_stop_lock_blocks_writing_commands(self) -> None:
        with copy_repo() as temp:
            repo = temp
            lock = run(repo, "scripts/novel.py", "stop-record", "--reason", "blocked", "--lock-id", "lock_test")
            self.assertEqual(lock.returncode, 0, lock.stderr)

            commands = [
                ("start", "v01_c001", "--allow-placeholders"),
                ("brief-candidates", "v01_c001"),
                ("deepseek-brief", "v01_c001", "--dry-run"),
                ("select-brief", "v01_c001", "--choice", "Manual", "--reason", "blocked"),
                ("land-brief", "v01_c001", "--source", "Manual", "--attestation", "blocked"),
                ("deepseek-generate", "v01_c001", "--dry-run"),
                ("select-candidate", "v01_c001", "--choice", "Codex", "--reason", "blocked"),
                ("review", "v01_c001", "--allow-missing-reviews"),
                ("codex-review-start", "v01_c001"),
                ("decision", "v01_c001", "--decision", "Ship"),
                (
                    "event",
                    "v01_c001",
                    "--type",
                    "character_decision",
                    "--fact",
                    "fact",
                    "--evidence-quote",
                    "quote",
                    "--consequence",
                    "consequence",
                ),
                (
                    "close",
                    "v01_c001",
                    "--decision",
                    "Ship",
                    "--keep",
                    "blocked",
                    "--change",
                    "blocked",
                    "--next-verify",
                    "blocked",
                    "--setting-boundary",
                    "blocked",
                    "--failure-condition",
                    "blocked",
                ),
                ("reader-test", "add", "--gate", "A", "--reader", "r01"),
                ("reader-test", "summarize", "--gate", "A", "--risk", "risk"),
                ("derive",),
                ("gate-close", "A", "--decision", "pause", "--reason", "blocked"),
                ("commit", "--message", "blocked"),
            ]
            for command in commands:
                with self.subTest(command=command):
                    result = run(repo, "scripts/novel.py", *command)
                    self.assertNotEqual(result.returncode, 0)
                    self.assertIn("unresolved stop locks", result.stderr)

    def test_gate_continue_requires_ready_evidence(self) -> None:
        with copy_repo() as temp:
            repo = temp
            result = run(
                repo,
                "scripts/novel.py",
                "gate-close",
                "A",
                "--decision",
                "continue",
                "--reason",
                "not ready",
                "--next-limits",
                "limit",
                "--continue-to",
                "v01_c010",
                "--budget",
                "budget",
                "--primary-model",
                "Codex",
                "--must-fix",
                "fix",
                "--stop-trigger",
                "stop",
            )

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("gate evidence is not ready", result.stderr)

    def test_gate_continue_requires_structured_forward_plan(self) -> None:
        with copy_repo() as temp:
            repo = temp
            result = run(
                repo,
                "scripts/record_gate_decision.py",
                "--gate",
                "A",
                "--decision",
                "continue",
                "--reason",
                "continue",
            )

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("structured gate continue fields are required", result.stderr)

    def test_structured_decision_fields_required_for_ship(self) -> None:
        with copy_repo() as temp:
            repo = temp
            result = run(repo, "scripts/record_decision.py", "--chapter", "v01_c001", "--decision", "Ship")

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("structured decision fields are required", result.stderr)

    def test_reader_response_requires_complete_answers_and_target_reader(self) -> None:
        with copy_repo() as temp:
            repo = temp
            write(repo, "answers.json", "{}\n")
            result = run(
                repo,
                "scripts/reader_test.py",
                "add",
                "--gate",
                "A",
                "--reader",
                "r01",
                "--answers",
                "answers.json",
            )

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("target reader must be identified", result.stderr)
            self.assertIn("missing answer", result.stderr)

    def test_diff_scope_rejects_untracked_out_of_scope_file(self) -> None:
        with copy_repo() as temp:
            repo = temp
            subprocess.run(["git", "init"], cwd=repo, check=True, capture_output=True)
            subprocess.run(["git", "config", "user.name", "Test"], cwd=repo, check=True)
            subprocess.run(["git", "config", "user.email", "test@example.local"], cwd=repo, check=True)
            subprocess.run(["git", "add", "."], cwd=repo, check=True)
            subprocess.run(["git", "commit", "-m", "baseline"], cwd=repo, check=True, capture_output=True)

            write(repo, "bible/untracked_scope_violation.md", "bad\n")
            result = run(repo, "scripts/diff_scope_check.py", "--role", "state", "--chapter", "v01_c001")

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("bible/untracked_scope_violation.md", result.stdout)

    def test_candidate_scope_allows_selection_artifacts_from_roles_yaml(self) -> None:
        with copy_repo() as temp:
            repo = temp
            subprocess.run(["git", "init"], cwd=repo, check=True, capture_output=True)
            subprocess.run(["git", "config", "user.name", "Test"], cwd=repo, check=True)
            subprocess.run(["git", "config", "user.email", "test@example.local"], cwd=repo, check=True)
            subprocess.run(["git", "add", "."], cwd=repo, check=True)
            subprocess.run(["git", "commit", "-m", "baseline"], cwd=repo, check=True, capture_output=True)

            write(repo, "reviews/v01_c001/candidate_selection.md", "choice: Codex\n")
            write(repo, "state/selections/v01_c001.json", '{"choice":"Codex"}\n')
            result = run(repo, "scripts/novel.py", "diff-scope", "--role", "candidate", "--chapter", "v01_c001")

            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_append_event_invalid_duplicate_does_not_mutate_ledger(self) -> None:
        with copy_repo() as temp:
            repo = temp
            write(repo, "chapters/v01/c001.md", "A real quote anchors the event.\n")
            base_args = [
                "scripts/append_event.py",
                "--chapter",
                "v01_c001",
                "--type",
                "character_decision",
                "--fact",
                "fact",
                "--evidence-quote",
                "real quote anchors",
                "--consequence",
                "consequence",
                "--event-id",
                "v01_c001_e001",
            ]
            first = run(repo, *base_args)
            before = (repo / "state/event_ledger.jsonl").read_text(encoding="utf-8")
            second = run(repo, *base_args)
            after = (repo / "state/event_ledger.jsonl").read_text(encoding="utf-8")

            self.assertEqual(first.returncode, 0, first.stderr)
            self.assertNotEqual(second.returncode, 0)
            self.assertEqual(before, after)

    def test_append_event_requires_quote_from_official_chapter(self) -> None:
        with copy_repo() as temp:
            repo = temp
            write(repo, "chapters/v01/c001.md", "The protagonist chooses action on page.\n")
            before = (repo / "state/event_ledger.jsonl").read_text(encoding="utf-8")

            result = run(
                repo,
                "scripts/append_event.py",
                "--chapter",
                "v01_c001",
                "--type",
                "character_decision",
                "--fact",
                "fact",
                "--evidence-quote",
                "not in the chapter",
                "--consequence",
                "consequence",
            )
            after = (repo / "state/event_ledger.jsonl").read_text(encoding="utf-8")

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("evidence_quote not found", result.stderr)
            self.assertEqual(before, after)

    def test_append_event_accepts_quote_from_official_chapter_with_collapsed_whitespace(self) -> None:
        with copy_repo() as temp:
            repo = temp
            write(repo, "chapters/v01/c001.md", "The protagonist chooses\naction on page.\n")

            result = run(
                repo,
                "scripts/append_event.py",
                "--chapter",
                "v01_c001",
                "--type",
                "character_decision",
                "--fact",
                "fact",
                "--evidence-quote",
                "protagonist chooses action",
                "--consequence",
                "consequence",
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("protagonist chooses action", (repo / "state/event_ledger.jsonl").read_text(encoding="utf-8"))

    def test_deepseek_review_rejects_review_file_as_input(self) -> None:
        with copy_repo() as temp:
            repo = temp
            write(repo, "state/context_pack/v01_c001.md", "context\n")
            write(repo, "reviews/v01_c001/codex_integrated_review.md", "codex review\n")

            result = run(
                repo,
                "scripts/run_deepseek_review.py",
                "--chapter",
                "v01_c001",
                "--input",
                "reviews/v01_c001/codex_integrated_review.md",
                "--dry-run",
            )

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("Allowed inputs", result.stderr)

    def test_deepseek_generate_rejects_invalid_chapter_id(self) -> None:
        with copy_repo() as temp:
            repo = temp
            result = run(repo, "scripts/run_deepseek_generate.py", "--chapter", "../bad", "--dry-run")

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("Invalid chapter id", result.stderr)

    def test_deepseek_review_dry_run_does_not_write_manifest(self) -> None:
        with copy_repo() as temp:
            repo = temp
            write(repo, "state/context_pack/v01_c001.md", "context\n")
            write(repo, "chapters/v01/c001.md", "chapter\n")

            result = run(repo, "scripts/run_deepseek_review.py", "--chapter", "v01_c001", "--dry-run")

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertTrue((repo / "external_runs/deepseek/v01_c001/review.prompt.md").exists())
            self.assertFalse((repo / "reviews/v01_c001/review_manifest.json").exists())

    def test_deepseek_idea_rejects_malformed_response_without_artifacts(self) -> None:
        with copy_repo() as temp:
            repo = temp
            result = run_deepseek_module_with_response(
                repo,
                "run_deepseek_idea",
                "{}",
                "--idea-id",
                "idea_bad_response",
                "--text",
                "idea",
            )

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("invalid DeepSeek response", result.stderr)
            self.assertNotIn("Traceback", result.stderr)
            self.assertFalse((repo / "state/idea_lab/idea_bad_response/deepseek_idea.md").exists())
            self.assertFalse((repo / "external_runs/deepseek/idea_bad_response/idea.raw.json").exists())

    def test_deepseek_generate_rejects_malformed_response_without_artifacts(self) -> None:
        with copy_repo() as temp:
            repo = temp
            write_core_setting_freeze(repo)
            write(repo, "state/context_pack/v01_c001.md", "context\n")
            write(repo, "outline/chapter_briefs/v01_c001.md", "brief " + ("A" * 320) + "\n")
            write_context_quality(repo, "v01_c001")

            result = run_deepseek_module_with_response(
                repo,
                "run_deepseek_generate",
                "{}",
                "--chapter",
                "v01_c001",
            )

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("invalid DeepSeek response", result.stderr)
            self.assertNotIn("Traceback", result.stderr)
            self.assertFalse((repo / "drafts/deepseek/v01_c001.md").exists())
            self.assertFalse((repo / "external_runs/deepseek/v01_c001/generate.raw.json").exists())

    def test_deepseek_review_rejects_malformed_response_without_artifacts(self) -> None:
        with copy_repo() as temp:
            repo = temp
            write(repo, "state/context_pack/v01_c002.md", "context\n")
            write(repo, "chapters/v01/c002.md", "chapter\n")

            result = run_deepseek_module_with_response(
                repo,
                "run_deepseek_review",
                "{}",
                "--chapter",
                "v01_c002",
            )

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("invalid DeepSeek response", result.stderr)
            self.assertNotIn("Traceback", result.stderr)
            self.assertFalse((repo / "reviews/v01_c002/deepseek_integrated_review.md").exists())
            self.assertFalse((repo / "reviews/v01_c002/review_manifest.json").exists())
            self.assertFalse((repo / "external_runs/deepseek/v01_c002/review.raw.json").exists())

    def test_deepseek_generate_valid_response_writes_candidate_and_raw_json(self) -> None:
        with copy_repo() as temp:
            repo = temp
            write_core_setting_freeze(repo)
            write(repo, "state/context_pack/v01_c001.md", "context\n")
            write(repo, "outline/chapter_briefs/v01_c001.md", "brief " + ("A" * 320) + "\n")
            write_context_quality(repo, "v01_c001")

            result = run_deepseek_module_with_response(
                repo,
                "run_deepseek_generate",
                "{'choices': [{'message': {'content': 'candidate text'}}]}",
                "--chapter",
                "v01_c001",
            )

            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertEqual((repo / "drafts/deepseek/v01_c001.md").read_text(encoding="utf-8"), "candidate text\n")
            self.assertTrue((repo / "external_runs/deepseek/v01_c001/generate.raw.json").exists())

    def test_deepseek_brief_valid_response_writes_candidate_and_raw_json(self) -> None:
        with copy_repo() as temp:
            repo = temp
            write_core_setting_freeze(repo)
            write(repo, "state/context_pack/v01_c001_brief.md", "brief pack\n")

            result = run_deepseek_module_with_response(
                repo,
                "run_deepseek_brief",
                "{'choices': [{'message': {'content': '# v01_c001 Brief\\n\\n## 本章功能\\n\\n候选。'}}]}",
                "--chapter",
                "v01_c001",
            )

            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertTrue((repo / "drafts/deepseek/v01_c001_brief.md").exists())
            self.assertTrue((repo / "external_runs/deepseek/v01_c001/brief.raw.json").exists())

    def test_select_and_land_brief_from_codex_candidate(self) -> None:
        with copy_repo() as temp:
            repo = temp
            write(repo, "drafts/codex/v01_c001_brief.md", COMPLETE_BRIEF.format(chapter="v01_c001"))

            selection = run(
                repo,
                "scripts/novel.py",
                "select-brief",
                "v01_c001",
                "--choice",
                "Codex",
                "--reason",
                "human selected Codex brief",
            )
            self.assertEqual(selection.returncode, 0, selection.stdout + selection.stderr)

            landing = run(
                repo,
                "scripts/novel.py",
                "land-brief",
                "v01_c001",
                "--source",
                "Codex",
                "--from-candidate",
                "Codex",
                "--attestation",
                "Human selected the Codex brief candidate and Codex landed it.",
            )

            self.assertEqual(landing.returncode, 0, landing.stdout + landing.stderr)
            self.assertEqual(
                (repo / "outline/chapter_briefs/v01_c001.md").read_text(encoding="utf-8"),
                COMPLETE_BRIEF.format(chapter="v01_c001"),
            )
            self.assertTrue((repo / "reviews/v01_c001/brief_landing.json").exists())

    def test_land_allows_identical_selected_deepseek_candidate(self) -> None:
        with copy_repo() as temp:
            repo = temp
            chapter_text = "DeepSeek candidate copied exactly.\n"
            write(repo, "state/context_pack/v01_c001.md", "context\n")
            write(repo, "outline/chapter_briefs/v01_c001.md", "brief " + ("A" * 320) + "\n")
            write(repo, "chapters/v01/c001.md", chapter_text)
            write(repo, "drafts/deepseek/v01_c001.md", chapter_text)
            write_context_quality(repo, "v01_c001")
            selection = run(
                repo,
                "scripts/novel.py",
                "select-candidate",
                "v01_c001",
                "--choice",
                "DeepSeek",
                "--reason",
                "human selected external direction",
            )
            self.assertEqual(selection.returncode, 0, selection.stdout + selection.stderr)

            result = run(
                repo,
                "scripts/novel.py",
                "land",
                "v01_c001",
                "--selected-direction",
                "DeepSeek",
                "--attestation",
                "Human selected the DeepSeek draft as the official chapter.",
            )

            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            landing = json.loads((repo / "reviews/v01_c001/chapter_landing.json").read_text(encoding="utf-8"))
            self.assertTrue(landing["deepseek_direct_adoption"])
            self.assertFalse(landing["codex_integrated"])
            self.assertEqual(landing["direct_deepseek_candidate"]["path"], "drafts/deepseek/v01_c001.md")

    def test_land_rejects_identical_deepseek_candidate_mislabeled_as_codex(self) -> None:
        with copy_repo() as temp:
            repo = temp
            chapter_text = "DeepSeek candidate copied exactly.\n"
            write(repo, "state/context_pack/v01_c001.md", "context\n")
            write(repo, "outline/chapter_briefs/v01_c001.md", "brief " + ("A" * 320) + "\n")
            write(repo, "chapters/v01/c001.md", chapter_text)
            write(repo, "drafts/deepseek/v01_c001.md", chapter_text)
            write_context_quality(repo, "v01_c001")
            selection = run(
                repo,
                "scripts/novel.py",
                "select-candidate",
                "v01_c001",
                "--choice",
                "DeepSeek",
                "--reason",
                "human selected external direction",
            )
            self.assertEqual(selection.returncode, 0, selection.stdout + selection.stderr)

            result = run(
                repo,
                "scripts/novel.py",
                "land",
                "v01_c001",
                "--selected-direction",
                "Codex",
                "--attestation",
                "Mislabeled direct adoption.",
            )

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("use --selected-direction DeepSeek", result.stderr)

    def test_chapter_evidence_allows_direct_deepseek_adoption(self) -> None:
        with copy_repo() as temp:
            repo = temp
            chapter_text = "DeepSeek candidate copied exactly with a concrete protagonist choice.\n"
            write(repo, "state/context_pack/v01_c001.md", "context\n")
            write(repo, "outline/chapter_briefs/v01_c001.md", "brief " + ("A" * 320) + "\n")
            write(repo, "chapters/v01/c001.md", chapter_text)
            write(repo, "drafts/deepseek/v01_c001.md", chapter_text)
            write_context_quality(repo, "v01_c001")
            selection = run(
                repo,
                "scripts/novel.py",
                "select-candidate",
                "v01_c001",
                "--choice",
                "DeepSeek",
                "--reason",
                "human selected external direction",
            )
            self.assertEqual(selection.returncode, 0, selection.stdout + selection.stderr)
            landing = run(
                repo,
                "scripts/novel.py",
                "land",
                "v01_c001",
                "--selected-direction",
                "DeepSeek",
                "--attestation",
                "Human selected the DeepSeek draft as the official chapter.",
            )
            self.assertEqual(landing.returncode, 0, landing.stdout + landing.stderr)

            context_item = {"path": "state/context_pack/v01_c001.md", "sha256": file_sha(repo, "state/context_pack/v01_c001.md")}
            chapter_item = {"path": "chapters/v01/c001.md", "sha256": file_sha(repo, "chapters/v01/c001.md")}
            manifest = {
                "codex": {"recorded_at": "2000-01-01T00:00:00+00:00", "inputs": [context_item, chapter_item]},
                "deepseek": {"recorded_at": "2000-01-01T00:00:00+00:00", "inputs": [context_item, chapter_item]},
            }
            write(repo, "reviews/v01_c001/review_manifest.json", json.dumps(manifest) + "\n")
            write(repo, "reviews/v01_c001/codex_integrated_review.md", "# Codex Review\n\naction: Ship\n")
            write(repo, "reviews/v01_c001/deepseek_integrated_review.md", "# DeepSeek Review\n\naction: Ship\n")
            write(repo, "reviews/v01_c001/model_disagreement.md", MODEL_DISAGREEMENT_READY)
            write(repo, "reviews/v01_c001/continuity.md", "# Continuity\n\nstatus: CLEAR\np0_count: 0\np1_count: 0\n")
            write_auxiliary_reviews(repo, "v01_c001")

            result = run(repo, "scripts/novel.py", "evidence", "v01_c001")

            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn("status: READY", result.stdout)

    def test_empty_export_fails(self) -> None:
        with copy_repo() as temp:
            repo = temp
            result = run(repo, "scripts/export_clean.py", "--volume", "v01")

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("no non-empty chapters", result.stderr)

    def test_export_refuses_unshipped_chapter(self) -> None:
        with copy_repo() as temp:
            repo = temp
            write(repo, "chapters/v01/c001.md", "draft text\n")

            result = run(repo, "scripts/export_clean.py", "--volume", "v01")

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("refusing to export unshipped chapter v01_c001", result.stderr)

    def test_commit_all_requires_role_scope(self) -> None:
        with copy_repo() as temp:
            repo = temp
            result = run(repo, "scripts/novel.py", "commit", "--message", "test", "--all")

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("commit --all requires --role", result.stderr)

    def test_gate_check_not_ready_fails(self) -> None:
        with copy_repo() as temp:
            repo = temp
            result = run(repo, "scripts/gate_check.py", "--gate", "A")

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("status: NOT_READY", result.stdout)
            self.assertIn("reader responses below minimum", result.stdout)

    def test_gate_commands_read_same_yaml_config(self) -> None:
        with copy_repo() as temp:
            repo = temp
            write(
                repo,
                "ops/gate_rules.yaml",
                "gate_a_3_chapters:\n"
                "  gate: A\n"
                "  criteria: outline/gate_a_3_chapters.md\n"
                "  decide_only_after_chapters: 3\n"
                "  reader_synthesis: reader_tests/gate_a_synthesis.md\n"
                "  reader_response_dir: reader_tests/responses/gate_a\n"
                "  min_reader_responses: 3\n"
                "  assessment_sections: []\n"
                "gate_b_10_chapters:\n"
                "  gate: B\n"
                "  criteria: outline/gate_b_10_chapters.md\n"
                "  decide_only_after_chapters: 10\n"
                "  reader_synthesis: reader_tests/gate_b_synthesis.md\n"
                "  reader_response_dir: reader_tests/responses/gate_b\n"
                "  min_reader_responses: 3\n"
                "  assessment_sections: []\n"
                "gate_c_25_chapters:\n"
                "  gate: C\n"
                "  criteria: outline/custom_gate_c.md\n"
                "  decide_only_after_chapters: 1\n"
                "  required_assessment: state/gates/custom_c.md\n"
                "  assessment_sections:\n"
                "    - Custom Section\n"
                "gate_e_125_chapters:\n"
                "  gate: E\n"
                "  criteria: ops/gate_rules.yaml\n"
                "  decide_only_after_chapters: 125\n"
                "  required_assessment: state/gates/gate_e_300w_assessment.md\n"
                "  assessment_sections:\n"
                "    - 300 万字模式\n",
            )
            write(repo, "outline/custom_gate_c.md", "# Custom Gate C\n")

            gate = run(repo, "scripts/novel.py", "gate", "C")
            gate_check = run(repo, "scripts/novel.py", "gate-check", "C")

            self.assertNotEqual(gate.returncode, 0)
            self.assertNotEqual(gate_check.returncode, 0)
            self.assertIn("minimum chapters before decision: 1", gate.stdout)
            self.assertIn("criteria file: outline/custom_gate_c.md", gate.stdout)
            self.assertIn("required_chapters: 1", gate_check.stdout)
            self.assertIn("criteria_file: outline/custom_gate_c.md", gate_check.stdout)
            self.assertIn("missing gate assessment: state/gates/custom_c.md", gate_check.stdout)

    def test_gate_c_requires_and_accepts_structured_assessment(self) -> None:
        with copy_repo() as temp:
            repo = temp
            for number in range(1, 26):
                write_complete_chapter_evidence(repo, f"v01_c{number:03d}", number)
            write_human_events(repo, 25)

            missing = run(repo, "scripts/novel.py", "gate-check", "C")
            self.assertNotEqual(missing.returncode, 0)
            self.assertIn("missing gate assessment", missing.stdout)

            write(
                repo,
                "state/gates/gate_c_assessment.md",
                "# Gate C Assessment\n\n"
                "status: CLEAR\n\n"
                "## 阶段高潮\n完成。\n\n"
                "## 不可逆变化\n完成。\n\n"
                "## 伏笔负债\n可控。\n\n"
                "## 设定膨胀\n未失控。\n\n"
                "## 卷内结构\n清晰。\n",
            )
            ready = run(repo, "scripts/novel.py", "gate-check", "C")

            self.assertEqual(ready.returncode, 0, ready.stdout + ready.stderr)
            self.assertIn("READY_FOR_HUMAN_DECISION", ready.stdout)

    def test_gate_e_reports_300w_assessment_requirement(self) -> None:
        with copy_repo() as temp:
            repo = temp
            result = run(repo, "scripts/novel.py", "gate-check", "E")

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("gate_e_300w_assessment.md", result.stdout)

    def test_start_chapter_blocks_fourth_chapter_before_gate_a(self) -> None:
        with copy_repo() as temp:
            repo = temp
            write(repo, "outline/chapter_briefs/v01_c004.md", "# v01_c004 Brief\n\n" + ("A" * 320) + "\n")

            result = run(repo, "scripts/start_chapter.py", "--chapter", "v01_c004")

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("Gate A", result.stderr)

    def test_start_chapter_blocks_twenty_six_before_gate_c(self) -> None:
        with copy_repo() as temp:
            repo = temp
            write(repo, "state/gates/gate_a.json", '{"decision":"continue"}\n')
            write(repo, "state/gates/gate_b.json", '{"decision":"continue"}\n')
            write(repo, "outline/chapter_briefs/v01_c026.md", "# v01_c026 Brief\n\n" + ("A" * 320) + "\n")

            result = run(repo, "scripts/start_chapter.py", "--chapter", "v01_c026")

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("Gate C", result.stderr)

    def test_start_chapter_blocks_longform_gate_thresholds(self) -> None:
        with copy_repo() as temp:
            repo = temp
            for gate in ("a", "b", "c", "e"):
                write(repo, f"state/gates/gate_{gate}.json", '{"decision":"continue"}\n')
            write(repo, "outline/chapter_briefs/v01_c201.md", "# v01_c201 Brief\n\n" + ("A" * 320) + "\n")

            gate_f = run(repo, "scripts/start_chapter.py", "--chapter", "v01_c201")

            self.assertNotEqual(gate_f.returncode, 0)
            self.assertIn("Gate F", gate_f.stderr)

            write(repo, "state/gates/gate_f.json", '{"decision":"continue"}\n')
            write(repo, "outline/chapter_briefs/v01_c501.md", "# v01_c501 Brief\n\n" + ("A" * 320) + "\n")
            gate_g = run(repo, "scripts/start_chapter.py", "--chapter", "v01_c501")

            self.assertNotEqual(gate_g.returncode, 0)
            self.assertIn("Gate G", gate_g.stderr)

            write(repo, "state/gates/gate_g.json", '{"decision":"continue"}\n')
            write(repo, "outline/chapter_briefs/v01_c801.md", "# v01_c801 Brief\n\n" + ("A" * 320) + "\n")
            gate_h = run(repo, "scripts/start_chapter.py", "--chapter", "v01_c801")

            self.assertNotEqual(gate_h.returncode, 0)
            self.assertIn("Gate H", gate_h.stderr)

    def test_stop_check_records_project_lock_on_stop(self) -> None:
        with copy_repo() as temp:
            repo = temp
            write(repo, "reviews/v01_c001/continuity.md", "# Continuity\n\nstatus: BLOCKED\np0_count: 0\np1_count: 1\n")

            result = run(repo, "scripts/stop_check.py", "--chapter", "v01_c001")
            locks = (repo / "state/stops/project_locks.json").read_text(encoding="utf-8")

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("status: STOP", result.stdout)
            self.assertIn("continuity_check has unresolved P0/P1", locks)

    def test_direct_write_script_blocks_stop_lock(self) -> None:
        with copy_repo() as temp:
            repo = temp
            lock = run(repo, "scripts/project_lock.py", "record", "--reason", "blocked", "--lock-id", "direct_lock")
            self.assertEqual(lock.returncode, 0, lock.stderr)

            result = run(
                repo,
                "scripts/record_decision.py",
                "--chapter",
                "v01_c001",
                "--decision",
                "Kill chapter",
            )

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("unresolved stop locks", result.stderr)

    def test_chapter_evidence_rejects_bad_manifest_shapes(self) -> None:
        with copy_repo() as temp:
            repo = temp
            write(repo, "state/context_pack/v01_c001.md", "context\n")
            write(repo, "chapters/v01/c001.md", "Official chapter text.\n")
            write(repo, "state/selections/v01_c001.json", '{"choice":"Codex"}\n')
            write(repo, "reviews/v01_c001/codex_integrated_review.md", "# Codex Review\n\n建议动作: Ship\n")
            write(repo, "reviews/v01_c001/deepseek_integrated_review.md", "# DeepSeek Review\n\n建议动作: Ship\n")
            write(repo, "reviews/v01_c001/model_disagreement.md", "# Model Disagreement\n\n无核心冲突。\n")
            write(repo, "reviews/v01_c001/continuity.md", "# Continuity\n\nstatus: CLEAR\np0_count: 0\np1_count: 0\n")

            write(repo, "state/selections/v01_c001.json", '{"choice":"Invalid","reason":"bad","selected_candidates":[]}\n')
            invalid_choice = run(repo, "scripts/chapter_evidence.py", "--chapter", "v01_c001")
            self.assertNotEqual(invalid_choice.returncode, 0)
            self.assertIn("invalid candidate selection choice", invalid_choice.stdout)

            write(repo, "state/selections/v01_c001.json", '{"choice":"Codex","reason":"ok","selected_candidates":[]}\n')

            write(repo, "reviews/v01_c001/review_manifest.json", '{"codex":{"inputs":[]},"deepseek":{"inputs":[]}}\n')
            empty_inputs = run(repo, "scripts/chapter_evidence.py", "--chapter", "v01_c001")
            self.assertNotEqual(empty_inputs.returncode, 0)
            self.assertIn("has no inputs", empty_inputs.stdout)

            context_item = {
                "path": "state/context_pack/v01_c001.md",
                "sha256": file_sha(repo, "state/context_pack/v01_c001.md"),
            }
            chapter_item = {
                "path": "chapters/v01/c001.md",
                "sha256": file_sha(repo, "chapters/v01/c001.md"),
            }
            write(
                repo,
                "reviews/v01_c001/review_manifest.json",
                '{"codex":{"inputs":[%s]},"deepseek":{"inputs":[%s]}}\n'
                % (__import__("json").dumps(context_item), __import__("json").dumps(context_item)),
            )
            missing_required = run(repo, "scripts/chapter_evidence.py", "--chapter", "v01_c001")
            self.assertNotEqual(missing_required.returncode, 0)
            self.assertIn("manifest missing input chapters/v01/c001.md", missing_required.stdout)

            bad_chapter_item = dict(chapter_item)
            bad_chapter_item["sha256"] = "bad"
            write(
                repo,
                "reviews/v01_c001/review_manifest.json",
                '{"codex":{"inputs":[%s,%s]},"deepseek":{"inputs":[%s,%s]}}\n'
                % (
                    __import__("json").dumps(context_item),
                    __import__("json").dumps(bad_chapter_item),
                    __import__("json").dumps(context_item),
                    __import__("json").dumps(chapter_item),
                ),
            )
            hash_mismatch = run(repo, "scripts/chapter_evidence.py", "--chapter", "v01_c001")
            self.assertNotEqual(hash_mismatch.returncode, 0)
            self.assertIn("hash mismatch", hash_mismatch.stdout)

            missing_item = {"path": "state/context_pack/missing.md", "sha256": "bad"}
            write(
                repo,
                "reviews/v01_c001/review_manifest.json",
                '{"codex":{"inputs":[%s,%s,%s]},"deepseek":{"inputs":[%s,%s]}}\n'
                % (
                    __import__("json").dumps(context_item),
                    __import__("json").dumps(chapter_item),
                    __import__("json").dumps(missing_item),
                    __import__("json").dumps(context_item),
                    __import__("json").dumps(chapter_item),
                ),
            )
            missing_disk = run(repo, "scripts/chapter_evidence.py", "--chapter", "v01_c001")
            self.assertNotEqual(missing_disk.returncode, 0)
            self.assertIn("manifest has disallowed input state/context_pack/missing.md", missing_disk.stdout)

    def test_chapter_evidence_rejects_disallowed_manifest_input(self) -> None:
        with copy_repo() as temp:
            repo = temp
            write(repo, "state/context_pack/v01_c001.md", "context\n")
            write(repo, "chapters/v01/c001.md", "Official chapter text.\n")
            write(repo, "reviews/v01_c001/codex_integrated_review.md", "# Codex Review\n\n建议动作: Ship\n")
            write(repo, "reviews/v01_c001/deepseek_integrated_review.md", "# DeepSeek Review\n\n建议动作: Ship\n")
            context_item = {
                "path": "state/context_pack/v01_c001.md",
                "sha256": file_sha(repo, "state/context_pack/v01_c001.md"),
            }
            chapter_item = {
                "path": "chapters/v01/c001.md",
                "sha256": file_sha(repo, "chapters/v01/c001.md"),
            }
            review_item = {
                "path": "reviews/v01_c001/deepseek_integrated_review.md",
                "sha256": file_sha(repo, "reviews/v01_c001/deepseek_integrated_review.md"),
            }
            write(
                repo,
                "reviews/v01_c001/review_manifest.json",
                '{"codex":{"inputs":[%s,%s,%s]},"deepseek":{"inputs":[%s,%s]}}\n'
                % (
                    __import__("json").dumps(context_item),
                    __import__("json").dumps(chapter_item),
                    __import__("json").dumps(review_item),
                    __import__("json").dumps(context_item),
                    __import__("json").dumps(chapter_item),
                ),
            )

            result = run(repo, "scripts/chapter_evidence.py", "--chapter", "v01_c001")

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("manifest has disallowed input reviews/v01_c001/deepseek_integrated_review.md", result.stdout)

    def test_chapter_evidence_rejects_blocked_auxiliary_review(self) -> None:
        with copy_repo() as temp:
            repo = temp
            write_complete_chapter_evidence(repo, "v01_c001", 1)
            write_auxiliary_reviews(repo, "v01_c001", status="BLOCKED")

            result = run(repo, "scripts/novel.py", "evidence", "v01_c001")

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("status is BLOCKED", result.stdout)

    def test_chapter_evidence_rejects_stale_context_quality_hash(self) -> None:
        with copy_repo() as temp:
            repo = temp
            write_complete_chapter_evidence(repo, "v01_c001", 1)
            write(repo, "state/context_pack/v01_c001.md", "changed context after quality\n")

            result = run(repo, "scripts/chapter_evidence.py", "--chapter", "v01_c001")

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("context quality context_pack_sha256 is stale", result.stdout)

    def test_chapter_evidence_rejects_review_written_before_manifest(self) -> None:
        with copy_repo() as temp:
            repo = temp
            write_complete_chapter_evidence(repo, "v01_c001", 1)
            manifest = json.loads((repo / "reviews/v01_c001/review_manifest.json").read_text(encoding="utf-8"))
            manifest["codex"]["recorded_at"] = "2999-01-01T00:00:00+00:00"
            write(repo, "reviews/v01_c001/review_manifest.json", json.dumps(manifest) + "\n")

            result = run(repo, "scripts/chapter_evidence.py", "--chapter", "v01_c001")

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("codex review artifact predates manifest", result.stdout)

    def test_event_id_must_match_chapter(self) -> None:
        with copy_repo() as temp:
            repo = temp
            write(repo, "chapters/v01/c001.md", "quote\n")
            write(
                repo,
                "bad_ledger.jsonl",
                '{"event_id":"v01_c002_e001","chapter":"v01_c001","type":"character_decision","fact":"fact","evidence_quote":"quote","consequence":"consequence","verified_by":"human"}\n',
            )

            result = run(repo, "scripts/validate_event_ledger.py", "--path", "bad_ledger.jsonl")

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("does not match chapter", result.stderr)

    def test_validate_event_ledger_rejects_unanchored_quote(self) -> None:
        with copy_repo() as temp:
            repo = temp
            write(repo, "chapters/v01/c001.md", "Official text with real evidence.\n")
            write(
                repo,
                "bad_ledger.jsonl",
                '{"event_id":"v01_c001_e001","chapter":"v01_c001","type":"character_decision","fact":"fact","evidence_quote":"missing quote","consequence":"consequence","verified_by":"human"}\n',
            )

            result = run(repo, "scripts/validate_event_ledger.py", "--path", "bad_ledger.jsonl")

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("evidence_quote not found", result.stderr)

    def test_context_pack_oversize_fails_without_allow_truncated(self) -> None:
        with copy_repo() as temp:
            repo = temp
            write_core_setting_freeze(repo)
            write(repo, "outline/premise.md", "# Premise\n\n" + ("x" * 4000) + "\n")
            write(repo, "outline/chapter_briefs/v01_c001.md", COMPLETE_BRIEF.format(chapter="v01_c001"))

            result = run(repo, "scripts/build_context_pack.py", "--chapter", "v01_c001", "--limit", "500")

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("context pack exceeds", result.stdout)
            self.assertTrue((repo / "state/snapshots/v01_c001_oversize_context.md").exists())

    def test_context_quality_rejects_allow_truncated_pack(self) -> None:
        with copy_repo() as temp:
            repo = temp
            write_core_setting_freeze(repo)
            write(repo, "outline/chapter_briefs/v01_c001.md", COMPLETE_BRIEF.format(chapter="v01_c001"))

            build = run(repo, "scripts/build_context_pack.py", "--chapter", "v01_c001", "--limit", "500", "--allow-truncated")
            quality = run(repo, "scripts/context_pack_quality.py", "--chapter", "v01_c001")

            self.assertEqual(build.returncode, 0, build.stdout + build.stderr)
            self.assertNotEqual(quality.returncode, 0)
            self.assertIn("allow-truncated", quality.stdout)

    def test_context_pack_includes_selected_object_and_ability_entries(self) -> None:
        with copy_repo() as temp:
            repo = temp
            write_core_setting_freeze(repo)
            long_rule = "A" * 650
            write(
                repo,
                "bible/objects.yaml",
                "objects:\n"
                "  - id: mirror_lingxi\n"
                "    name: 灵犀镜\n"
                "    current_state: 主角持有\n"
                "    limits:\n"
                f"      - {long_rule}\n"
                "  - id: unselected_compass\n"
                "    name: 误导罗盘\n"
                "    current_state: 不在本章使用\n",
            )
            write(
                repo,
                "bible/abilities.yaml",
                "abilities:\n"
                "  - id: signal_trace\n"
                "    name: 信号追踪\n"
                "    can_do:\n"
                "      - 定位被放大的执念信号\n"
                "    cannot_do:\n"
                "      - 不能证明鬼存在\n",
            )
            brief = COMPLETE_BRIEF.format(chapter="v01_c001").replace(
                "## 本章可用道具 IDs\n\nnone",
                "## 本章可用道具 IDs\n\n- mirror_lingxi",
            ).replace(
                "## 本章可用技能 IDs\n\nnone",
                "## 本章可用技能 IDs\n\n- signal_trace",
            )
            write(repo, "outline/chapter_briefs/v01_c001.md", brief)

            result = run(repo, "scripts/build_context_pack.py", "--chapter", "v01_c001", "--limit", "12000")

            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            pack = (repo / "state/context_pack/v01_c001.md").read_text(encoding="utf-8")
            self.assertIn("## 本章可用道具完整条目", pack)
            self.assertIn("mirror_lingxi", pack)
            self.assertIn(long_rule, pack)
            self.assertIn("signal_trace", pack)
            self.assertNotIn("误导罗盘", pack)
            self.assertIn("不得靠未授权新道具、新能力或新规则解决", pack)

    def test_context_pack_rejects_unknown_declared_element_id(self) -> None:
        with copy_repo() as temp:
            repo = temp
            write_core_setting_freeze(repo)
            brief = COMPLETE_BRIEF.format(chapter="v01_c001").replace(
                "## 本章可用道具 IDs\n\nnone",
                "## 本章可用道具 IDs\n\n- missing_object",
            )
            write(repo, "outline/chapter_briefs/v01_c001.md", brief)

            result = run(repo, "scripts/build_context_pack.py", "--chapter", "v01_c001")

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("unknown object id: missing_object", result.stderr)

    def test_backup_excludes_secrets_raw_json_and_prompts(self) -> None:
        with copy_repo() as temp:
            repo = temp
            write(repo, ".env", "SECRET=1\n")
            write(repo, "external_runs/deepseek/v01_c001/generate.raw.json", "{}\n")
            write(repo, "external_runs/deepseek/v01_c001/generate.prompt.md", "private prompt\n")

            result = run(repo, "scripts/build_backup.py", "--label", "test")

            self.assertEqual(result.returncode, 0, result.stderr)
            backup = next((repo / "backups").glob("*_test.zip"))
            with zipfile.ZipFile(backup) as archive:
                names = set(archive.namelist())
            self.assertNotIn(".env", names)
            self.assertNotIn("external_runs/deepseek/v01_c001/generate.raw.json", names)
            self.assertNotIn("external_runs/deepseek/v01_c001/generate.prompt.md", names)

    def test_check_template_rejects_invalid_or_placeholder_source_log(self) -> None:
        with copy_repo() as temp:
            repo = temp
            write(repo, "references/source_log.yaml", "sources: [\n")
            invalid = run(repo, "scripts/novel.py", "check")
            self.assertNotEqual(invalid.returncode, 0)
            self.assertIn("source_log", invalid.stderr)

            write(
                repo,
                "references/source_log.yaml",
                "sources:\n"
                "  - id: source_id\n"
                "    title: 待定\n"
                "    allowed_use: [抽象技法]\n"
                "    forbidden_reuse: [设定名词]\n",
            )
            placeholder = run(repo, "scripts/novel.py", "check")
            self.assertNotEqual(placeholder.returncode, 0)
            self.assertIn("placeholder", placeholder.stderr)

    def test_doctor_reports_missing_git_as_error(self) -> None:
        with copy_repo() as temp:
            repo = temp
            result = run(repo, "scripts/novel.py", "doctor")

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("status: ERROR", result.stdout)
            self.assertIn("not a Git repository", result.stdout)

    def test_next_prompt_prefers_unselected_idea_lab(self) -> None:
        with copy_repo() as temp:
            repo = temp
            write_ready_idea_lab(repo, "idea_next")
            result = run(repo, "scripts/novel.py", "next-prompt")

            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn("总结开书实验", result.stdout)
            self.assertIn("idea_next", result.stdout)

    def test_next_prompt_routes_to_gate_a_after_three_shipped_chapters(self) -> None:
        with copy_repo() as temp:
            repo = temp
            for number in range(1, 4):
                write_complete_chapter_evidence(repo, f"v01_c{number:03d}", number)
            write_human_events(repo, 3)

            result = run(repo, "scripts/novel.py", "next-prompt")

            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn("进入 Gate A 检查", result.stdout)

    def test_brief_check_requires_anti_drift_sections(self) -> None:
        with copy_repo() as temp:
            repo = temp
            missing = run(repo, "scripts/novel.py", "brief-check", "v01_c001")
            self.assertNotEqual(missing.returncode, 0)
            self.assertIn("status: NOT_READY", missing.stdout)

            write(repo, "outline/chapter_briefs/v01_c001.md", COMPLETE_BRIEF.format(chapter="v01_c001"))
            ready = run(repo, "scripts/novel.py", "brief-check", "v01_c001")

            self.assertEqual(ready.returncode, 0, ready.stdout + ready.stderr)
            self.assertIn("status: READY", ready.stdout)

    def test_derived_state_and_context_pack_include_objects_and_abilities(self) -> None:
        with copy_repo() as temp:
            repo = temp
            chapter_text = "主角握住义眼。义眼只能捕捉被数据放大的执念信号。\n"
            write(repo, "chapters/v01/c001.md", chapter_text)
            write(
                repo,
                "state/event_ledger.jsonl",
                json.dumps(
                    {
                        "event_id": "v01_c001_e001",
                        "chapter": "v01_c001",
                        "type": "object_change",
                        "fact": "义眼成为关键调查装备",
                        "evidence_quote": "主角握住义眼",
                        "consequence": "后续必须追踪义眼状态",
                        "verified_by": "human",
                    },
                    ensure_ascii=False,
                )
                + "\n"
                + json.dumps(
                    {
                        "event_id": "v01_c001_e002",
                        "chapter": "v01_c001",
                        "type": "rule_reveal",
                        "fact": "义眼只能捕捉被数据放大的执念信号",
                        "evidence_quote": "义眼只能捕捉被数据放大的执念信号",
                        "consequence": "限制能力边界",
                        "verified_by": "human",
                    },
                    ensure_ascii=False,
                )
                + "\n",
            )
            write(repo, "outline/chapter_briefs/v01_c001.md", COMPLETE_BRIEF.format(chapter="v01_c001"))
            write_core_setting_freeze(repo)

            derived = run(repo, "scripts/build_derived_state.py")
            self.assertEqual(derived.returncode, 0, derived.stdout + derived.stderr)
            self.assertIn("义眼成为关键调查装备", (repo / "state/derived/current_objects.yaml").read_text(encoding="utf-8"))
            self.assertIn("义眼只能捕捉", (repo / "state/derived/current_abilities.yaml").read_text(encoding="utf-8"))

            context = run(repo, "scripts/build_context_pack.py", "--chapter", "v01_c001", "--limit", "10000")
            self.assertEqual(context.returncode, 0, context.stdout + context.stderr)
            pack = (repo / "state/context_pack/v01_c001.md").read_text(encoding="utf-8")
            self.assertIn("开书前核心设定冻结", pack)
            self.assertIn("A anomaly cause.", pack)
            self.assertIn("A family anchor.", pack)
            self.assertIn("当前道具 / 装备变化", pack)
            self.assertIn("当前技能 / 规则揭示", pack)

    def test_derived_state_simulates_200_500_800_chapter_indexes(self) -> None:
        with copy_repo() as temp:
            repo = temp
            entries = []
            for number in (200, 500, 800):
                chapter = f"v01_c{number:03d}"
                quote = f"Official chapter {chapter}"
                write(repo, f"chapters/v01/c{number:03d}.md", f"{quote} keeps the long thread visible.\n")
                entries.append(
                    json.dumps(
                        {
                            "event_id": f"{chapter}_e001",
                            "chapter": chapter,
                            "type": "thread_advanced",
                            "fact": f"thread milestone {number}",
                            "evidence_quote": quote,
                            "consequence": "long-range governance must retain this fact",
                            "verified_by": "human",
                            "entities": ["protagonist"],
                            "thread_id": "thread_main",
                            "importance": "P1",
                            "tags": ["thread", "longform"],
                        },
                        ensure_ascii=False,
                    )
                )
            write(repo, "state/event_ledger.jsonl", "\n".join(entries) + "\n")

            result = run(repo, "scripts/build_derived_state.py")

            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            for chunk in ("chunk_151_200.md", "chunk_451_500.md", "chunk_751_800.md"):
                self.assertTrue((repo / f"state/derived/arcs/{chunk}").exists())
            self.assertTrue((repo / "state/derived/indexes/events_by_chapter/v01_c800.json").exists())
            self.assertIn("thread_main", (repo / "state/derived/threads/active.yaml").read_text(encoding="utf-8"))

    def test_suggestion_commands_do_not_write_canon_or_ledger(self) -> None:
        with copy_repo() as temp:
            repo = temp
            chapter = "v01_c001"
            write(repo, "chapters/v01/c001.md", "主角握住义眼，发现规则只能解释一半线索。\n")
            ledger_before = (repo / "state/event_ledger.jsonl").read_text(encoding="utf-8")
            canon_before = (repo / "bible/canon.md").read_text(encoding="utf-8")

            suggest = run(repo, "scripts/novel.py", "event-suggest", chapter)
            propose = run(repo, "scripts/novel.py", "canon-propose", chapter)

            self.assertEqual(suggest.returncode, 0, suggest.stdout + suggest.stderr)
            self.assertEqual(propose.returncode, 0, propose.stdout + propose.stderr)
            self.assertIn("object_change", suggest.stdout)
            self.assertEqual(ledger_before, (repo / "state/event_ledger.jsonl").read_text(encoding="utf-8"))
            self.assertEqual(canon_before, (repo / "bible/canon.md").read_text(encoding="utf-8"))

    def test_second_revise_once_is_blocked(self) -> None:
        with copy_repo() as temp:
            repo = temp
            args = (
                "scripts/novel.py",
                "decision",
                "v01_c001",
                "--decision",
                "Revise once",
                "--keep",
                "保留主角主动性",
                "--change",
                "加强章末钩子",
                "--next-verify",
                "复查留存风险",
                "--setting-boundary",
                "不新增规则",
                "--failure-condition",
                "主角目标仍不清",
            )
            first = run(repo, *args)
            second = run(repo, *args)

            self.assertEqual(first.returncode, 0, first.stdout + first.stderr)
            self.assertNotEqual(second.returncode, 0)
            self.assertIn("already used Revise once", second.stderr)

    def test_reader_response_template_can_be_recorded_as_incomplete_draft(self) -> None:
        with copy_repo() as temp:
            repo = temp
            result = run(
                repo,
                "scripts/reader_test.py",
                "add",
                "--gate",
                "A",
                "--reader",
                "reader_001",
                "--answers",
                "templates/reader_response_gate_a.json",
                "--allow-incomplete",
                "--allow-unknown",
            )

            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertTrue((repo / "reader_tests/responses/gate_a/reader_001.json").exists())


if __name__ == "__main__":
    unittest.main()
