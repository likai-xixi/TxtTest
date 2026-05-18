# Novel 300w Workflow

本仓库由 Codex app 做工程总控：管理文件、Git、脚本、状态、汇总与最终落盘。人类总编拥有最高裁决权，决定主线、人物命运、设定取舍、章节是否继续。

## 核心原则

1. 先跑 3 章轻量试点；3 章前不判断 300 万字可行性。
2. 开正文前必须先完成 DeepSeek + `product_founder` + `technical_lead` + `qa_release` 的开书实验，并锁定核心设定冻结证据。
3. 核心设定冻结至少固定：世界观核心规则、世界观硬边界、主角异常原因、主角家属/亲密关系、家属剧情功能与风险、前三章约束、不可违背红线、仍可开放的问题。
4. AI 不靠记忆写长篇，只读 `state/context_pack/{chapter}.md` 和当章 brief。
5. Codex 与 DeepSeek 可以同时生成候选稿；DeepSeek 直出稿经人类选择并由 Codex 记录 provenance 后，可作为正式章。
6. Codex 与 DeepSeek 必须独立审查，互不读取对方报告。
7. 新元素按 L0-L4 分级：L0 场景细节和 L1 一次性线索可自由出现；L2 只能作为伏笔或提案；L3 长期机制必须 brief 授权；L4 核心设定必须人类裁决。
8. `chapters/`、`bible/canon.md`、`state/event_ledger.jsonl`、Gate 通过权，只能由 Codex 在规则内落盘，并由人类最终裁决。

## 统一入口

正式流程以 `scripts/novel.py` 为准。底层脚本保留给统一入口、测试和排查调用；不得绕过 `novel.py` 直接落候选选择、裁决、Gate、事件或提交。

## 总编口令

人类总编不需要记脚本细节。若用户使用下列口令，Codex app 必须自动翻译为流程动作：

- `开书`：运行 `python scripts/novel.py go`；若缺核心设定冻结，必须引导用户先说 `想法：...` / `开书实验`，不得生成正文或 context pack。
- `想法：...` / `开书实验`：必须进入 idea-lab。先运行 `python scripts/novel.py idea --text "..."` 或 `idea-form`；必须真实调用 DeepSeek，不能 dry-run；必须同时启用 `product_founder`、`technical_lead`、`qa_release` 三类 agent。
- `定盘` / `锁定设定`：在三类 agent 审查和 `codex_synthesis.md` 完成后，运行 `python scripts/novel.py idea-select --id idea_xxx --choice A`；该命令必须生成 `state/idea_lab/{idea_id}/core_setting_freeze.json` 和 `.md`，并通过 `core-freeze-check`。
- `继续`：运行 `python scripts/novel.py go` 和 `status`，判断下一步；只在需要人类回答、确认或裁决时停下。
- `加设定：...` / `设定：...`：运行 `python scripts/novel.py setting --text "..."`，若用户指定章节则加 `--chapter {chapter}`；只能暂存到 `bible/open_questions.md` 和当章 brief 的“新增设定”，不得直接写 canon；若触碰已冻结核心设定，必须重新人类裁决，不得暗改。
- `开章 v01_c001` / `写下一章` / `写书`：优先运行 `python scripts/novel.py write {chapter}`；无明确章节时运行 `python scripts/novel.py write`。若核心设定冻结缺失，停止并回到开书实验；若 brief 缺失或仍有占位，必须先走 brief 候选流程：Codex 写 `drafts/codex/{chapter}_brief.md`，DeepSeek 写 `drafts/deepseek/{chapter}_brief.md`，Codex 汇总优劣，等待人类选择 / 混合 / 修改后，再由 Codex 运行 `select-brief` 与 `land-brief` 落正式 `outline/chapter_briefs/{chapter}.md`；不得直接写正文。
- `收章 v01_c001`：Codex 自行执行候选选择记录、正式落章 provenance、Codex review manifest、DeepSeek review、continuity、model_disagreement、evidence 检查；缺人类裁决或 event ledger 事实时再问用户。
- `总编台` / `下一步`：运行 `python scripts/novel.py desk`，只给用户一句当前卡点和可选口令。
- `查状态`：运行 `python scripts/novel.py status`，用一句话告诉用户现在卡在哪里。

回复用户时优先使用这些口令，不要把完整脚本链条甩给用户。

### 开书实验室硬规则

- 如果当前 Codex 环境不能启用 `product_founder`、`technical_lead`、`qa_release`，必须停止并说明“开书实验要求多 agent，当前环境不满足”，不能降级成单模型。
- 如果 `DEEPSEEK_API_KEY` 不可用，必须停止；开书实验不能用 dry-run 替代。
- idea-lab 只能写 `state/idea_lab/`、`external_runs/deepseek/` 和被人类选择后的试点资产；不得写 `bible/canon.md`、`chapters/`、`state/event_ledger.jsonl`。
- Codex 汇总必须固定给三种方向：A 最强商业钩子、B 最强人物驱动、C 最大差异化/反套路。
- 每个方向必须包含：一句话卖点、主角欲望、核心冲突、世界异常、世界观核心规则、世界观硬边界、主角异常原因、主角家属/亲密关系、家属剧情功能与风险、前三章约束、不可违背红线、仍可开放的问题、前三章验证点、最大风险、适合继续/不适合继续的信号。
- `core_setting_freeze.json` 是开正文硬门禁；`start`、`write`、`build_context_pack`、`deepseek-generate` 均不得绕过它，包括 `--allow-placeholders`。

常用入口：

```bash
python scripts/novel.py go
python scripts/novel.py idea --text "..."
python scripts/novel.py idea-select --id idea_xxx --choice A
python scripts/novel.py core-freeze-check
python scripts/novel.py setting --text "..."
python scripts/novel.py write
python scripts/novel.py draft v01_c001
python scripts/novel.py desk
python scripts/novel.py flow
python scripts/novel.py check
python scripts/novel.py status
python scripts/novel.py self-test
```

## 每章流程

每章 brief 必须声明：`本章可用道具 IDs`、`本章可用技能 IDs`、`本章允许新增元素`、`本章禁止临场解决`。`build_context_pack` 只能按这些 ID 拉取完整道具/技能条目；未授权的新道具、新能力或新规则不得成为本章破局钥匙。

```text
1. python scripts/novel.py brief-candidates {chapter}
2. Codex 生成 `drafts/codex/{chapter}_brief.md`
3. python scripts/novel.py deepseek-brief {chapter}
4. Codex 汇总 brief 候选优劣；人类选择 / 混合 / 修改
5. python scripts/novel.py select-brief {chapter} --choice ...
6. Codex 落正式 brief；python scripts/novel.py land-brief {chapter} --source ...
7. python scripts/novel.py start {chapter}
8. Codex / DeepSeek 生成正文候选稿
9. python scripts/novel.py select-candidate {chapter} --choice ...
10. Codex 落正式正文到 chapters/；若人类选择 DeepSeek，允许正式正文与被选 DeepSeek 候选完全一致。
11. python scripts/novel.py land {chapter} --selected-direction ...
12. python scripts/novel.py codex-review-start {chapter}
13. Codex 写独立审查，不读取 DeepSeek review
14. python scripts/novel.py review {chapter} --deepseek
15. python scripts/novel.py evidence {chapter}
16. 人类判定：Ship / Revise once / Rewrite brief / Kill chapter / Pause project
17. python scripts/novel.py event ...
18. python scripts/novel.py close {chapter} --decision Ship
```

Ship close 必须具备：结构化候选选择、官方正文落章 provenance、Codex/DeepSeek 审查、review manifest、model_disagreement、无 P0/P1 continuity、辅助审查；若直采 DeepSeek，必须证明人类已选择 DeepSeek 且 landing 记录为 `deepseek_direct_adoption`。

## DeepSeek 边界

- 默认模型名：`deepseek-v4-pro`。
- 环境变量：`DEEPSEEK_API_KEY`。
- DeepSeek 只能写候选输出目录、独立审查文件和 `external_runs/deepseek/`。
- DeepSeek brief 只能写 `drafts/deepseek/{chapter}_brief.md` 和 `external_runs/deepseek/{chapter}/brief.*`；不能直接写 `outline/chapter_briefs/`。
- DeepSeek 不能直接改 `chapters/`、`bible/`、`state/event_ledger.jsonl`；但被人类选择的 DeepSeek 候选稿可由 Codex 原样落入 `chapters/` 并记录为正式章来源。
- dry-run 只生成 prompt，不触网。

## Gate

- Gate A：3 章后，由 `python scripts/novel.py gate-check A` 检查证据。
- Gate B：10 章后，由 `python scripts/novel.py gate-check B` 检查证据。
- Gate C：25 章后，还必须有 `state/gates/gate_c_assessment.md`。
- Gate E：125 章后，还必须有 `state/gates/gate_e_300w_assessment.md`。

Gate 命令只检查证据和记录人类裁决，永不自动通过 Gate。
# Context Governance Update

- `context_pack` 是单章驾驶舱，不是全书资料包。
- 全书事实只进 `state/event_ledger.jsonl`；可重建状态进 `state/derived/`；本章写作只读 `state/context_pack/{chapter}.md` 和正式 brief。
- `python scripts/novel.py start {chapter}` 必须依次生成 derived state、context pack、`state/context_pack/{chapter}.manifest.json` 和 `state/derived/context_quality/{chapter}.json`。
- `context_quality` 必须 READY 后才可进入 DeepSeek 正文生成或正式落章；`--allow-truncated` 产物不得进入正式写作。
- Gate F/G/H 已纳入长期治理：F=200 章状态索引与伏笔账本，G=500 章重复套路/设定债务/长线兑现，H=800 章终局治理并限制新长期机制。
