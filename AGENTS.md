# Novel 300w Workflow

本仓库由 Codex app 做工程总控：管理文件、Git、脚本、状态、汇总与最终落盘。人类总编拥有最高裁决权，决定主线、人物命运、设定取舍、章节是否继续。

## 核心原则

1. 先跑 3 章轻量试点；3 章前不判断 300 万字可行性。
2. AI 不靠记忆写长篇，只读 `state/context_pack/{chapter}.md` 和当章 brief。
3. Codex 与 DeepSeek 可以同时生成候选稿，但 DeepSeek 输出默认只是候选和建议。
4. Codex 与 DeepSeek 必须独立审查，互不读取对方报告。
5. `chapters/`、`bible/canon.md`、`state/event_ledger.jsonl`、Gate 通过权，只能由 Codex 在规则内落盘，并由人类最终裁决。

## 统一入口

正式流程以 `scripts/novel.py` 为准。底层脚本保留给统一入口、测试和排查调用；不得绕过 `novel.py` 直接落候选选择、裁决、Gate、事件或提交。

常用入口：

```bash
python scripts/novel.py flow
python scripts/novel.py check
python scripts/novel.py status
python scripts/novel.py self-test
```

## 每章流程

```text
1. 写 chapter brief
2. python scripts/novel.py start {chapter}
3. Codex / DeepSeek 生成候选稿
4. python scripts/novel.py select-candidate {chapter} --choice ...
5. Codex 落正式正文到 chapters/
6. python scripts/novel.py land {chapter} --selected-direction ...
7. python scripts/novel.py codex-review-start {chapter}
8. Codex 写独立审查，不读取 DeepSeek review
9. python scripts/novel.py review {chapter} --deepseek
10. python scripts/novel.py evidence {chapter}
11. 人类判定：Ship / Revise once / Rewrite brief / Kill chapter / Pause project
12. python scripts/novel.py event ...
13. python scripts/novel.py close {chapter} --decision Ship
```

Ship close 必须具备：结构化候选选择、官方正文落章 provenance、Codex/DeepSeek 审查、review manifest、model_disagreement、无 P0/P1 continuity、辅助审查、非 DeepSeek 直拷证明。

## DeepSeek 边界

- 默认模型名：`deepseek-v4-pro`。
- 环境变量：`DEEPSEEK_API_KEY`。
- DeepSeek 只能写候选输出目录、独立审查文件和 `external_runs/deepseek/`。
- DeepSeek 不能直接改 `chapters/`、`bible/`、`state/event_ledger.jsonl`。
- dry-run 只生成 prompt，不触网。

## Gate

- Gate A：3 章后，由 `python scripts/novel.py gate-check A` 检查证据。
- Gate B：10 章后，由 `python scripts/novel.py gate-check B` 检查证据。
- Gate C：25 章后，还必须有 `state/gates/gate_c_assessment.md`。
- Gate E：125 章后，还必须有 `state/gates/gate_e_300w_assessment.md`。

Gate 命令只检查证据和记录人类裁决，永不自动通过 Gate。
