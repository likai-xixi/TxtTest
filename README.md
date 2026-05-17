# Novel 300w Template

这是一个长篇小说试点模板仓库。目标不是自动替人类决定故事，而是把“人类总编 + Codex 工程总控 + DeepSeek 外部候选/审查”落成可复制、可校验、可追踪的工程系统。

## 一个入口

正式流程优先使用：

```bash
python scripts/novel.py flow
python scripts/novel.py status
python scripts/novel.py check
python scripts/novel.py self-test
```

底层脚本保留给排查和测试；正式写入候选选择、落章、审查、裁决、Gate、事件和提交时使用 `scripts/novel.py`。

## 复制后开工

```bash
python scripts/novel.py init --name "你的小说名"
python scripts/novel.py questionnaire
python scripts/novel.py apply-questionnaire --answers setup_answers.md
```

填写 `outline/chapter_briefs/v01_c001.md` 后：

```bash
python scripts/novel.py start v01_c001 --deepseek-dry-run
```

如果已配置 `DEEPSEEK_API_KEY`：

```bash
python scripts/novel.py deepseek-generate v01_c001
```

## 每章简化流程

```bash
python scripts/novel.py new-chapter v01_c001
python scripts/novel.py start v01_c001 --deepseek-dry-run
python scripts/novel.py deepseek-generate v01_c001
python scripts/novel.py select-candidate v01_c001 --choice "Mixed" --reason "..." --mixed-strategy "..."
```

Codex 写正式正文到 `chapters/v01/c001.md` 后：

```bash
python scripts/novel.py land v01_c001 --selected-direction Mixed --attestation "Codex integrated the official chapter from the context pack, brief, and selected direction; no direct DeepSeek copy."
python scripts/novel.py codex-review-start v01_c001
```

先运行 `codex-review-start` 记录 Codex 审查输入 manifest，再写 `reviews/v01_c001/codex_integrated_review.md`。随后：

```bash
python scripts/novel.py review v01_c001 --deepseek
python scripts/novel.py evidence v01_c001
python scripts/novel.py decision v01_c001 --decision "Ship" --keep "..." --change "..." --next-verify "..." --setting-boundary "..." --failure-condition "..."
python scripts/novel.py event v01_c001 --type character_decision --fact "..." --evidence-quote "..." --consequence "..."
python scripts/novel.py close v01_c001 --decision "Ship" --commit-message "complete v01 c001"
```

## Ship 证据

Ship 前 `python scripts/novel.py evidence {chapter}` 必须 READY。它会检查：

- 结构化候选选择和候选 hash。
- 官方正文落章 provenance。
- 官方正文不得与被选中的 DeepSeek 候选完全相同。
- Codex/DeepSeek review manifest 的输入 hash 与禁止互读。
- review artifact 必须晚于对应 manifest。
- model_disagreement、continuity、辅助审查齐全。
- `ai_taste.md`、`web_satisfaction.md`、`retention_risk.md`、`originality.md` 的 `status` 必须是 `CLEAR` 或 `ACCEPTED_BY_HUMAN`。

## Gate

```bash
python scripts/novel.py gate-check A
python scripts/novel.py gate A
python scripts/novel.py gate-close A --decision continue --reason "..." --next-limits "..." --continue-to v01_c010 --budget "..." --primary-model Codex --must-fix "..." --stop-trigger "..."
```

Gate A/B 需要章节证据、读者反馈和 synthesis。Gate C 还需要 `state/gates/gate_c_assessment.md`；Gate E 还需要 `state/gates/gate_e_300w_assessment.md`。Gate 命令只检查证据和记录人类裁决，不会自动通过。

## DeepSeek 边界

- DeepSeek 通过本地脚本调用 API。
- 默认模型：`deepseek-v4-pro`。
- 真实密钥只从 `DEEPSEEK_API_KEY` 读取，不写入仓库。
- DeepSeek 只能写 `drafts/deepseek/`、`reviews/{chapter}/deepseek_integrated_review.md` 和 `external_runs/deepseek/`。
- DeepSeek review 不能把 Codex review 作为输入。

## 维护与发布前检查

```bash
python -m compileall scripts tests
python scripts/novel.py check
python scripts/novel.py self-test
python scripts/novel.py status
python scripts/novel.py evidence v01_c001
python scripts/novel.py gate-check A
python scripts/novel.py export --volume v01
python scripts/novel.py backup --label release-smoke
python scripts/run_deepseek_generate.py --chapter v01_c001 --dry-run
python scripts/run_deepseek_review.py --chapter v01_c001 --dry-run
```

`evidence`、`gate-check` 和 `export` 在未完成项目里应返回 NOT_READY 或拒绝导出；这说明守卫在工作。
