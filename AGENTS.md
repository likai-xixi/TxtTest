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

## 商业辅助 + 事实硬门禁

商业化、标题、简介、赛道扫描、表格视图、章末阅读理由、润色，只能作为总编辅助层；不得直接写入 `bible/canon.md`、`chapters/`、`state/event_ledger.jsonl`，不得进入 `state/context_pack/*.manifest.json` 的事实源输入链。

事实、设定、授权、因果、后果、相似风险、落账，继续作为 Ship 硬门禁。`reviews/{chapter}/similarity_risk.md`、`reviews/{chapter}/fact_cards.json` 与至少一张已通过 `accept-fact-card` 写入 event ledger 的 fact card，是 `chapter-evidence` 的必查证据。fact card 只能写 `state/event_ledger.jsonl`，不能写 canon。

辅助入口：

```bash
python scripts/novel.py idea-form --commercial --id idea_xxx
python scripts/novel.py commercial-idea-check --id idea_xxx
python scripts/novel.py market-scan --id idea_xxx
python scripts/novel.py market-scan-check --id idea_xxx
python scripts/novel.py table-build
python scripts/novel.py table-check
python scripts/novel.py polish-start v01_c001
python scripts/novel.py polish-check v01_c001
python scripts/novel.py similarity-risk-check v01_c001
python scripts/novel.py fact-card-check v01_c001
```

`audit --mode project/release` 会汇总这些辅助检查，但硬裁决仍以 `core-freeze-check`、`brief-check`、`context-quality` 和 `chapter-evidence` 为准。

## 总编口令

人类总编不需要记脚本细节。若用户使用下列口令，Codex app 必须自动翻译为流程动作：

- `开书`：运行 `python scripts/novel.py go`；若缺核心设定冻结，必须引导用户先说 `想法：...` / `开书实验`，不得生成正文或 context pack。
- `想法：...` / `开书实验`：必须进入 idea-lab。先运行 `python scripts/novel.py idea --text "..."` 或 `idea-form`；必须真实调用 DeepSeek，不能 dry-run；必须同时启用 `product_founder`、`technical_lead`、`qa_release` 三类 agent。
- `定盘` / `锁定设定`：在三类 agent 审查、`agent_review_manifest.json` 和 `codex_synthesis.md` 完成后，运行 `python scripts/novel.py idea-select --id idea_xxx --choice A`；该命令必须生成 `state/idea_lab/{idea_id}/core_setting_freeze.json` 和 `.md`，并通过 `core-freeze-check`。
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
- 三类 agent 审查完成后，必须运行 `python scripts/novel.py idea-agent-manifest --id idea_xxx` 记录 role、输入 hash、输出 hash 和完成时间；缺该 manifest 不得 `idea-select`。
- Codex 汇总必须固定给三种方向：A 最强商业钩子、B 最强人物驱动、C 最大差异化/反套路。
- 每个方向必须包含：一句话卖点、主角欲望、核心冲突、世界异常、世界观核心规则、世界观硬边界、主角异常原因、主角家属/亲密关系、家属剧情功能与风险、前三章约束、不可违背红线、仍可开放的问题、前三章验证点、最大风险、适合继续/不适合继续的信号。
- `core_setting_freeze.json` 是开正文硬门禁；`start`、`write`、`build_context_pack`、`deepseek-generate` 均不得绕过它，包括 `--allow-placeholders`。

常用入口：

```bash
python scripts/novel.py go
python scripts/novel.py idea --text "..."
python scripts/novel.py idea-agent-manifest --id idea_xxx
python scripts/novel.py idea-select --id idea_xxx --choice A
python scripts/novel.py core-freeze-check
python scripts/novel.py setting --text "..."
python scripts/novel.py write
python scripts/novel.py brief-precheck v01_c001
python scripts/novel.py draft v01_c001
python scripts/novel.py desk
python scripts/novel.py audit --write-report
python scripts/novel.py flow
python scripts/novel.py check
python scripts/novel.py status
python scripts/novel.py pacing-dashboard v01_c001 --write
python scripts/novel.py self-test
```

## 每章流程

每章 brief 必须声明：`上章章末锚点`、`本章开场落点`、`场景承接说明`、`主线牵引档位`、`外部压力档位`、`本章继承变化`、`本章节奏用途`、`节奏说明`、`本章进展契约`、`本章代价与后果契约`、`本章解决边界`、`本章可用道具 IDs`、`本章可用技能 IDs`、`本章允许新增元素`、`本章禁止临场解决`。`brief_check` 硬查字段完整、场景承接、档位合法、进展契约、代价后果和解决边界；`pacing_check` 硬查跨章连续低推进、连续小事、高推进后无消化，并保留过热预警。`build_derived_state` 必须生成 `state/derived/pacing/progress_index.json` 和 `state/derived/pacing/aftermath_obligations.json`；`build_context_pack` 只能按这些 ID 拉取完整道具/技能条目，并带入上一章人类确认的章末锚点和当前后果承接债务；未授权的新道具、新能力或新规则不得成为本章破局钥匙。Ship evidence 必须核验 brief 承诺的 `最低落账事件` 已进入 `state/event_ledger.jsonl`。

```text
1. python scripts/novel.py brief-precheck {chapter}
2. python scripts/novel.py brief-candidates {chapter}
3. Codex 生成 `drafts/codex/{chapter}_brief.md`
4. python scripts/novel.py deepseek-brief {chapter}
5. Codex 汇总 brief 候选优劣；人类选择 / 混合 / 修改
6. python scripts/novel.py select-brief {chapter} --choice ...
7. Codex 落正式 brief；python scripts/novel.py land-brief {chapter} --source ...
8. python scripts/novel.py start {chapter}
9. Codex / DeepSeek 生成正文候选稿
10. python scripts/novel.py select-candidate {chapter} --choice ...
11. Codex 落正式正文到 chapters/；若人类选择 DeepSeek，允许正式正文与被选 DeepSeek 候选完全一致。
12. python scripts/novel.py land {chapter} --selected-direction ...
13. python scripts/novel.py codex-review-start {chapter}
14. Codex 写独立审查，不读取 DeepSeek review
15. python scripts/novel.py review {chapter} --deepseek
16. python scripts/novel.py evidence {chapter}
17. 人类判定：Ship / Revise once / Rewrite brief / Kill chapter / Pause project
18. python scripts/novel.py event ...（Ship 前至少记录一个 `chapter_anchor` 章末锚点事件，供下一章承接）
19. python scripts/novel.py close {chapter} --decision Ship
```

Ship close 必须具备：结构化候选选择、官方正文落章 provenance、Codex/DeepSeek 审查、review manifest、model_disagreement、无 P0/P1 continuity、辅助审查、`style-check` 与 post-warmup `series-style-check`；若直采 DeepSeek，必须证明人类已选择 DeepSeek 且 landing 记录为 `deepseek_direct_adoption`。

跨章文风与系列感：前三章是 warmup；第 4 章起必须有 `reviews/{chapter}/series_style.json`；第 4-5 章允许 `WARNING` 作为人工观察期，第 6 章起 Ship evidence 只接受 `READY` 或 `ACCEPTED_BY_HUMAN`。可选 DeepSeek 独立文风审查由 `deepseek-style-review` 生成，若本章使用 `series-style-check --require-deepseek`，缺失或过期的 DeepSeek 文风审查必须阻断收章。

## DeepSeek 边界

- 默认模型名：`deepseek-v4-pro`。
- 环境变量：`DEEPSEEK_API_KEY`。
- DeepSeek 只能写候选输出目录、独立审查文件和 `external_runs/deepseek/`。
- DeepSeek 文风审查只能通过 Codex wrapper 写 `reviews/{chapter}/deepseek_style_review.json`、`.md` 和 `external_runs/deepseek/{chapter}/style_review.*`，不得写正文、canon 或 event ledger。
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
- `python scripts/novel.py start {chapter}` 必须依次生成 derived state、context pack、`state/context_pack/{chapter}.manifest.json`、`state/derived/context_quality/{chapter}.json` 和同名 Markdown 人读报告。
- `context_quality` 必须 READY 后才可进入 DeepSeek 正文生成或正式落章；`--allow-truncated` 产物不得进入正式写作。
- 正式收章时应记录 `chapter_anchor` 人类确认事件；`build_derived_state` 会生成 `state/derived/chapter_anchors/{chapter}.json`，供下一章 brief pack、context pack 和 continuity 检查使用。
- 正式 brief 的进展契约会生成 `state/derived/pacing/progress_index.json`；高推进、兑现或解决伏笔产生的后果债务会进入 `state/derived/pacing/aftermath_obligations.json`，供下一章 brief、context pack、pacing check 和 Ship evidence 使用。
- Gate F/G/H 已纳入长期治理：F=200 章状态索引与伏笔账本，G=500 章重复套路/设定债务/长线兑现，H=800 章终局治理并限制新长期机制。
