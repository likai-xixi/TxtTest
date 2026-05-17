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

## 总编口令

人类总编不需要记脚本细节。若用户使用下列口令，Codex app 必须自动翻译为流程动作：

- `开书`：运行 `python scripts/novel.py go`，如缺启动问卷就生成并请用户填写。
- `想法：...` / `开书实验`：必须进入 idea-lab。先运行 `python scripts/novel.py idea --text "..."` 或 `idea-form`；必须真实调用 DeepSeek，不能 dry-run；必须同时启用 `product_founder`、`technical_lead`、`qa_release` 三类 agent。
- `继续`：运行 `python scripts/novel.py go` 和 `status`，判断下一步；只在需要人类回答、确认或裁决时停下。
- `开章 v01_c001` / `写下一章`：运行 `python scripts/novel.py draft {chapter}`。若 brief 缺失或仍有占位，先请用户给本章功能、开篇吸引点、主角目标、阻力、主动选择、章末问题；不要直接写正文。
- `收章 v01_c001`：Codex 自行执行候选选择记录、正式落章 provenance、Codex review manifest、DeepSeek review、continuity、model_disagreement、evidence 检查；缺人类裁决或 event ledger 事实时再问用户。
- `查状态`：运行 `python scripts/novel.py status`，用一句话告诉用户现在卡在哪里。

回复用户时优先使用这些口令，不要把完整脚本链条甩给用户。

### 开书实验室硬规则

- 如果当前 Codex 环境不能启用 `product_founder`、`technical_lead`、`qa_release`，必须停止并说明“开书实验要求多 agent，当前环境不满足”，不能降级成单模型。
- 如果 `DEEPSEEK_API_KEY` 不可用，必须停止；开书实验不能用 dry-run 替代。
- idea-lab 只能写 `state/idea_lab/`、`external_runs/deepseek/` 和被人类选择后的试点资产；不得写 `bible/canon.md`、`chapters/`、`state/event_ledger.jsonl`。
- Codex 汇总必须固定给三种方向：A 最强商业钩子、B 最强人物驱动、C 最大差异化/反套路。
- 每个方向必须包含：一句话卖点、主角欲望、核心冲突、世界异常、前三章验证点、最大风险、适合继续/不适合继续的信号。

常用入口：

```bash
python scripts/novel.py go
python scripts/novel.py idea --text "..."
python scripts/novel.py idea-select --id idea_xxx --choice A
python scripts/novel.py draft v01_c001
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
