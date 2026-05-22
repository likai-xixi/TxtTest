# Novel 300w Template

## 3-minute copied-template guide

```bash
python scripts/novel.py start-here
python scripts/novel.py opening-preflight --agents-ready --json
python scripts/novel.py opening-preflight --agents-ready --live
python scripts/novel.py idea --text "your seed idea"
python scripts/novel.py opening-status --id idea_xxx
python scripts/novel.py freeze-preview --id idea_xxx --choice A
```

`check` / `ci` mean the template is structurally healthy. `audit --mode project` means the story workflow is ready or blocked. A copied template is expected to pass `check` while still being `STORY_NOT_READY` until the opening experiment and core freeze are complete.

这是一个长篇小说试点模板仓库。目标不是自动替人类决定故事，而是把“人类总编 + Codex 工程总控 + DeepSeek 外部候选/审查”落成可复制、可校验、可追踪的工程系统。

## 一个入口

正式流程优先使用：

```bash
python scripts/novel.py desk
python scripts/novel.py flow
python scripts/novel.py status
python scripts/novel.py check
python scripts/novel.py self-test
python scripts/novel.py audit
python scripts/novel.py audit --write-report
python scripts/novel.py ci
```

底层脚本保留给排查和测试；正式写入候选选择、落章、审查、裁决、Gate、事件和提交时使用 `scripts/novel.py`。`desk/status` 会给出当前阶段、卡点、下一条总编口令、风险标记和证据路径。`audit` 是总编体检，会报告业务 NOT_READY；`audit --write-report` 会额外生成 `state/audit/latest.md` 和时间戳报告；`ci` 是本地模板 CI，只检查代码与流程回归。

## 复制后开工

最省事的方式是反复跑一个命令：

```bash
python scripts/novel.py go --name "你的小说名"
```

第一次会初始化目录、检测模板，然后检查开书前核心设定冻结。现在开正文前必须先完成开书实验和核心设定冻结；如果缺冻结证据，`go` 会停止并提示先走 `想法：...` / `开书实验`。后续不知道该干什么时，也可以先跑 `desk` 或 `status`。

## 日常口令

在 Codex app 里不用记后面的脚本链条，直接说：

```text
想法：……
定盘
继续
加设定：……
写下一章
收章 v01_c001
查状态
```

有新书念头时再说 `想法：……` / `开书实验` / `开书`。有指定章节时说 `开章 v01_c001`。

Codex 会按 `AGENTS.md` 自己运行检查、生成 context pack、调用 DeepSeek、记录 provenance、跑审查和 evidence。只有需要你给 brief、选择方向、裁决章节或确认正文事实时才停下来问你。

## 开书实验室

如果只有一个模糊念头，先走开书实验：

```bash
python scripts/novel.py idea --text "赛博民俗悬疑，主角是不信鬼的人"
```

这个命令必须真实调用 DeepSeek；没有 `DEEPSEEK_API_KEY` 会直接停止。DeepSeek 完成后，Codex app 必须启用 `product_founder`、`technical_lead`、`qa_release` 三类 agent，并把审查写入 `state/idea_lab/{idea_id}/`。`opening-preflight` 默认会阻断未确认的三 agent 能力；只有在当前 Codex 环境确实可启用三类 agent 时，才可加 `--agents-ready`。三类审查完成后先记录 provenance：

```bash
python scripts/novel.py idea-agent-manifest --id idea_xxx
```

三类 agent 审查必须先用结构化运行记录落证据，再生成 manifest：

```bash
python scripts/novel.py idea-agent-run --id idea_xxx --role product_founder --agent-id agent_pf_001 --runner-id codex_pf_001 --transcript state/idea_lab/idea_xxx/product_founder_transcript.md --isolation-attestation "Read only original_idea.md and deepseek_idea.md." --output state/idea_lab/idea_xxx/product_founder_review.md
python scripts/novel.py idea-agent-run --id idea_xxx --role technical_lead --agent-id agent_tl_001 --runner-id codex_tl_001 --transcript state/idea_lab/idea_xxx/technical_lead_transcript.md --isolation-attestation "Read only original_idea.md and deepseek_idea.md." --output state/idea_lab/idea_xxx/technical_lead_review.md
python scripts/novel.py idea-agent-run --id idea_xxx --role qa_release --agent-id agent_qa_001 --runner-id codex_qa_001 --transcript state/idea_lab/idea_xxx/qa_release_transcript.md --isolation-attestation "Read only original_idea.md and deepseek_idea.md." --output state/idea_lab/idea_xxx/qa_release_review.md
python scripts/novel.py idea-agent-manifest --id idea_xxx
```

Codex 汇总后，你只需要选择：

```bash
python scripts/novel.py idea-select --id idea_xxx --choice A --reason "商业钩子最强"
```

选择后会生成开正文前的核心设定冻结：`state/idea_lab/{idea_id}/core_setting_freeze.json` 和 `.md`。它必须固定世界观核心规则、世界观硬边界、主角异常原因、主角家属/亲密关系、家属剧情功能与风险、前三章约束、不可违背红线、仍可开放的问题。
冻结里还必须包含 `fields.initial_personality`，并镜像到 `bible/characters.yaml` 的 protagonist。第 1 章之前，主角人格只来自这个初始人格合同；第 1 章之后，只有人类确认的 `character_state_change + personality_delta` 能改变当前人格。

同时只会生成试点资产：`outline/premise.md`、`bible/open_questions.md`、`outline/gate_a_3_chapters.md`、`outline/chapter_briefs/v01_c001.md`。不会写 canon、正文或 event ledger。

检查冻结证据：

```bash
python scripts/novel.py core-freeze-check
```

开正文前还要锁定读者体验合同。它是写作/审稿指令源，不是 canon，也不进 event ledger：

```bash
python scripts/novel.py reader-promise-start
python scripts/novel.py reader-promise-check
python scripts/novel.py reader-promise-land --ready
```

如果不想一句话输入，可先生成短表单：

```bash
python scripts/novel.py idea-form
```

如果你想用命令行开章，先走 brief 候选，而不是直接填正式 brief：

```bash
python scripts/novel.py write
python scripts/novel.py brief-precheck v01_c001
python scripts/novel.py brief-candidates v01_c001
python scripts/novel.py deepseek-brief v01_c001
python scripts/novel.py select-brief v01_c001 --choice Codex --reason "..."
python scripts/novel.py land-brief v01_c001 --source Codex --from-candidate Codex --attestation "Human selected the Codex brief candidate; Codex landed the official brief."
python scripts/novel.py start v01_c001
```

如果你只是临时想到一个设定，不要直接改 canon。先暂存：

```bash
python scripts/novel.py setting --chapter v01_c001 --text "这个设定先进入本章新增设定，等正文出现后再确认。"
```

如果你想手动走细分命令：

```bash
python scripts/novel.py init --name "你的小说名"
python scripts/novel.py questionnaire
python scripts/novel.py apply-questionnaire --answers setup_answers.md
```

Codex / DeepSeek brief 都只是候选。正式 brief 只有在 `select-brief` 和 `land-brief` 之后才可作为 `start` 的输入。

正式 brief 落盘后：

```bash
python scripts/novel.py start v01_c001 --deepseek-dry-run
```

如果已配置 `DEEPSEEK_API_KEY`：

```bash
python scripts/novel.py deepseek-generate v01_c001
```

## 每章简化流程

日常建议先用：

```bash
python scripts/novel.py write
python scripts/novel.py desk
```

如果核心设定冻结缺失，`write`、`draft`、`brief-candidates`、`deepseek-brief`、`start`、`build_context_pack` 和 `deepseek-generate` 都会停止；`--allow-placeholders` 也不能绕过核心冻结。

每章 brief 默认使用 `schema_version: 2`。写作入口看 `Story Card`，机器治理看 `Machine Contract Appendix`：

- `Story Card`：只保留创作输入，包括第一屏扰动、主角想要、主角主动动作、最大阻力、中段变化点、小兑现、`before -> after`、章末点击理由、一条世界规则和禁止临场破局。
- `Machine Contract Appendix`：保留机器硬门禁，包括上章锚点、开场落点、场景承接、S/W 档位、继承变化、节奏用途、进展契约、代价后果、解决边界、R 档回报、低戏剧载体、核心机制状态、可用道具/技能 ID、允许新增元素和最低落账事件。
- v1 旧 brief 仍可读取和检查，但新模板、新候选 brief、新 DeepSeek prompt、新首章试点 brief 都应输出 v2。
- 正文候选 prompt 只接收 `Story Card + Hard Boundaries + Context Pack + Candidate Style Requirements`，不再把“防 AI 味合同 / 对白功能合同 / 句式破整合同 / 细节经济合同”整段塞进创作输入。

`python scripts/novel.py brief-precheck {chapter}` 是生成候选 brief 前的智能预检；`python scripts/novel.py brief-check {chapter}` 是正式 brief 的单章硬门禁，会拦截缺 `before -> after`、缺 R 档、缺主角主动动作、缺小兑现和缺点击理由。`python scripts/novel.py reader-reward-check {chapter} --write` 会检查 R2+ 正文回报 quote、主角主动选择 evidence 和世界规则场景测试。`python scripts/novel.py pacing-check {chapter} --write` 会拦截三章窗口无有效推进、高推进无消化和连续小事；`python scripts/novel.py reader-reward-index --write` 会跟踪三章无小兑现、低戏剧载体重复和章末钩子重复。10 章后还要跑 `python scripts/novel.py long-health --to {chapter} --write`，用最近 5 章窗口拦主角被动、只调查/会议/解释、只开不合和无小兑现。

`build_derived_state` 会从 `chapter_anchor` 人类确认事件生成 `state/derived/chapter_anchors/{chapter}.json`，也会从正式 brief 生成 `state/derived/pacing/progress_index.json` 和 `state/derived/pacing/aftermath_obligations.json`。下一章 brief pack 和 context pack 会读取上一章章末锚点与后果承接债务。`chapter_evidence` 会检查 brief 承诺的 `最低落账事件` 是否真的写入 `state/event_ledger.jsonl`。`build_context_pack` 会按 ID 拉完整道具/技能条目；未列入 ID 或新增授权的元素，只能做细节、线索或伏笔，不能临场破局。

需要排查时再拆成细分命令：

```bash
python scripts/novel.py new-chapter v01_c001
python scripts/novel.py brief-precheck v01_c001
python scripts/novel.py brief-candidates v01_c001
python scripts/novel.py deepseek-brief v01_c001
python scripts/novel.py select-brief v01_c001 --choice "Mixed" --reason "..."
python scripts/novel.py land-brief v01_c001 --source Mixed --attestation "Human selected and Codex landed the official brief."
python scripts/novel.py start v01_c001 --deepseek-dry-run
python scripts/novel.py deepseek-generate v01_c001
python scripts/novel.py select-candidate v01_c001 --choice "DeepSeek" --reason "..."
```

Codex 写正式正文到 `chapters/v01/c001.md` 后；若人类选择 DeepSeek，可以把被选 DeepSeek 候选原样作为该文件：

```bash
python scripts/novel.py land v01_c001 --selected-direction DeepSeek --attestation "Human selected the DeepSeek draft as the official chapter; Codex recorded provenance before review."
python scripts/novel.py review-context v01_c001 --write
python scripts/novel.py codex-review-start v01_c001
```

先运行 `codex-review-start` 记录 Codex 审查输入 manifest，再写 `reviews/v01_c001/codex_integrated_review.md`。随后：

```bash
python scripts/novel.py review v01_c001 --deepseek
python scripts/novel.py ai-taste-check v01_c001
python scripts/novel.py dialogue-function-check v01_c001
python scripts/novel.py prose-risk-check v01_c001 --write
python scripts/novel.py prose-risk-index --to v01_c001 --write
python scripts/novel.py codex-anti-ai-review-start v01_c001
python scripts/novel.py deepseek-anti-ai-review v01_c001
python scripts/novel.py evidence v01_c001
python scripts/novel.py decision v01_c001 --decision "Ship" --keep "..." --change "..." --next-verify "..." --setting-boundary "..." --failure-condition "..."
python scripts/novel.py event v01_c001 --type chapter_anchor --fact "v01_c001 章末锚点已确认" --evidence-quote "..." --consequence "下一章必须承接..." --importance P1 --tag chapter_anchor --anchor-end-time "深夜" --anchor-end-location "办公室" --anchor-present-character protagonist --anchor-protagonist-state "紧张但清醒" --anchor-carried-item "旧硬盘" --anchor-unfinished-action "还没决定是否离开办公室" --anchor-next-required-continuity "下一章必须交代主角是否离开办公室以及硬盘去向"
python scripts/novel.py event v01_c001 --type character_decision --fact "..." --evidence-quote "..." --consequence "..."
python scripts/novel.py close v01_c001 --decision "Ship" --commit-message "complete v01 c001"
```

## Ship 证据

Ship 前 `python scripts/novel.py evidence {chapter}` 必须 READY。它会检查：

- 结构化候选选择和候选 hash。
- 官方正文落章 provenance。
- 官方正文可以与被选中的 DeepSeek 候选完全相同，但仅限候选选择和 landing 都记录为 DeepSeek 直采。
- Codex/DeepSeek review manifest 的输入 hash 与禁止互读。
- review artifact 必须晚于对应 manifest。
- model_disagreement、continuity、辅助审查齐全。
- `ai_taste.md/json`、`dialogue_function.md/json`、`codex_anti_ai_review.md/json`、`deepseek_anti_ai_review.md/json`、`web_satisfaction.md`、`retention_risk.md`、`originality.md`、`similarity_risk.md` 的 `status` 必须是 `CLEAR` 或 `ACCEPTED_BY_HUMAN`。
- `opening_retention.md`（前三章）、`personality_drift.md`、`hook_retention.md`、`protagonist_charm.md`、`world_reveal.md`、`suspense_ladder.md`、`language_memorability.md`、`genre_fit.md` 必须是 `CLEAR` 或带当前 official chapter hash、review hash 和人工理由的 `ACCEPTED_BY_HUMAN`；`CLEAR` 必须带可匹配正文的 `Evidence Quotes`。
- 人格变化必须有 `character_state_change + personality_delta`；世界观名词超预算、P0/P1 悬念长期不推进、主角成长刻度长期停滞都会阻断 Ship 或 Gate。

- Review context `state/context_pack/{chapter}_review_context.md/json` must be READY, current, and must not include previous chapters as full text.
- Ship requires both independent Codex subagent `codex_anti_ai_review.md/json` and DeepSeek `deepseek_anti_ai_review.md/json`; either missing, stale, quote-less, malformed, or `BLOCKED` review blocks evidence.

Style and series-feel evidence:

- `python scripts/novel.py style-check {chapter}` writes `reviews/{chapter}/style_metrics.json`.
- `python scripts/novel.py ai-taste-check {chapter}` writes `reviews/{chapter}/ai_taste.md` and `ai_taste.json`.
- `python scripts/novel.py dialogue-function-check {chapter}` writes `reviews/{chapter}/dialogue_function.md` and `dialogue_function.json`.
- `python scripts/novel.py prose-risk-check {chapter} --write` writes `reviews/{chapter}/prose_risk.md/json` for the seven finished-prose risks: subject repetition, process bloat, invulnerable protagonist, flat side characters, homogeneous hooks, Q&A dialogue, and anomaly density.
- `python scripts/novel.py prose-risk-index --to {chapter} --write` writes `state/derived/prose_risk/latest.md/json`; chapters 1-3 warn, chapters 4-5 carry next-chapter obligations, and chapter 6+ repeated blockers stop Ship.
- `python scripts/novel.py review-context {chapter} --write` writes review-only structured state and key quotes; it is for reviewers and excludes previous chapters as full text.
- `python scripts/novel.py codex-anti-ai-review-start {chapter}` writes an isolated Codex subagent prompt and manifest; the subagent must write `reviews/{chapter}/codex_anti_ai_review.md/json`.
- `python scripts/novel.py deepseek-anti-ai-review {chapter}` writes `reviews/{chapter}/deepseek_anti_ai_review.md` and `deepseek_anti_ai_review.json`; this is required Ship evidence, not optional style advice.
- `python scripts/novel.py series-style-check {chapter}` writes `reviews/{chapter}/series_style.json`.
- Chapters 1-3 are warmup. From chapter 4 the series-style report is required; chapters 4-5 allow `WARNING`; chapter 6+ requires `READY` or `ACCEPTED_BY_HUMAN`.
- Optional DeepSeek style review: `python scripts/novel.py deepseek-style-review {chapter}` writes `reviews/{chapter}/deepseek_style_review.json`; `series-style-check --require-deepseek` can make it a required input.

Anti-AI taste evidence is a hard Ship gate in this template. `ai_taste` keeps its legacy name but now means the structured anti-AI review: show-don't-tell, rhythm disorder, emotional risk, gray motive, dialogue agenda, detail economy, and consequence integrity. Codex has a separate isolated subagent hard-gate report at `codex_anti_ai_review.md/json`; DeepSeek also has an independent hard-gate report at `deepseek_anti_ai_review.md/json`. The two independent reports both receive the review context, but they do not read each other, the integrated reviews, model disagreement, or legacy anti-AI/dialogue outputs. All auxiliary reviews marked `CLEAR` must include the current official chapter hash, a current `review_sha256`, and at least one `Evidence Quotes` line that matches the official chapter after whitespace folding. `ACCEPTED_BY_HUMAN` is allowed for taste disputes only when it records `accepted_by: human`, `accepted_at`, `reason`, current official chapter hash, and current review body hash.

v2 brief 主体不再要求填写六段长审计合同。防 AI 味、对白功能、句式破整、细节经济、角色私心和情绪越界改由正文风格要求与收章 review 检查，Ship evidence 仍会阻断缺失、过期、无 quote 或 `BLOCKED` 的审查。

### Receive Chapter Control Plane

`receive-chapter` is the full receive/close-prep control plane:

```bash
python scripts/novel.py receive-chapter v01_c001 --preview
python scripts/novel.py receive-chapter v01_c001 --resume
python scripts/novel.py review-context v01_c001 --write
python scripts/novel.py review-arbitration v01_c001
python scripts/novel.py revision-plan v01_c001
python scripts/novel.py accept-review v01_c001 --artifact ai_taste --reason "intentional style"
python scripts/novel.py gray-consequence v01_c001 --write
python scripts/novel.py chapter-shape-check v01_c006 --write
python scripts/novel.py prose-risk-check v01_c006 --write
python scripts/novel.py prose-risk-index --to v01_c006 --write
python scripts/novel.py reader-feedback summarize v01_c001
python scripts/novel.py reader-risk-index --to v01_c010 --write --json
python scripts/novel.py deepseek-manifest-check v01_c001 --kind anti_ai_review
python scripts/novel.py deepseek-manifest-check v01_c001 --kind semantic_reader_review
```

It writes `reviews/{chapter}/receive_chapter.json/md` and reports the exact next action. It does not auto-Ship, does not write canon, and does not write event ledger entries. Ship still goes through `chapter-evidence` and the human editor decision.

DeepSeek review, anti-AI review, semantic reader review, and style review now require run manifests at `external_runs/deepseek/{chapter}/{kind}.manifest.json`. These manifests bind model, prompt, raw response, output, allowed inputs, forbidden inputs, and isolation attestation. Missing, stale, or contaminated manifests block Ship.

`semantic-reader-review` is a real Codex/DeepSeek LLM aggregate, not a keyword heuristic. First run `codex-semantic-reader-review-start`, complete the isolated Codex LLM review into `codex_semantic_reader_review.md/json`, then run `deepseek-semantic-reader-review` to produce `deepseek_semantic_reader_review.md/json` and its DeepSeek run manifest. The aggregate `semantic_reader_review.md/json` is accepted only when both source reviews are current, quote-bound, and clear.

Revision plans, review arbitration, gray consequence reports, chapter-shape reports, prose-risk reports, emotion/relationship gates, semantic reader reviews, memorable-scene checks, reader-feedback summaries, reader-reward gates, the cross-chapter `prose-risk-index`, and the cross-chapter `reader-risk-index` are part of the receive evidence chain. High-impact gray behavior must be covered by human-verified event/fact evidence. Chapter-shape and prose-risk repetition are advisory during warmup and hard from chapter 6 when they repeat the same risk shape. Reader feedback is reader-experience evidence only and never a canon or event-ledger source.

Reader Promise v2 is the project-level reader-experience contract. `reader-promise-land --ready` must declare positive promises, negative failure modes, release-valve policy, protagonist agency policy, information clarity, language experience, structural efficiency, and R-level reward policy. Missing fields, placeholder arrays, and empty thresholds keep it out of `READY`.

`reader-risk-index` aggregates pace, repetition, suspense, protagonist agency, worldview, perspective, language, and structural efficiency through a target chapter, including suspense age budgets for P0/P1 threads. `BLOCKED` reader risk blocks `chapter-evidence` and release audit; `WARNING` remains visible in `desk/status` and audit reports.

`prose-risk-index` aggregates the seven finished-prose risks through a target chapter. `BLOCKED` prose risk blocks `chapter-evidence`; `WARNING` remains visible in `desk/status` and audit reports.

## Gate

```bash
python scripts/novel.py gate-check A
python scripts/novel.py gate A
python scripts/novel.py gate-close A --decision continue --reason "..." --next-limits "..." --continue-to v01_c010 --budget "..." --primary-model Codex --must-fix "..." --stop-trigger "..."
```

Gate A/B 需要章节证据、reader promise 兑现、主角主动性、初始人格稳定性、悬念推进、世界观场景化展示、真实读者反馈或带 reason/accepted_by/accepted_at/hash/risk_acceptance_items 的人工说明，以及 synthesis。Gate F/G/H 还会复盘 suspense ledger、world reveal/concept ledger 和 protagonist progression 的长线债务。Gate 命令只检查证据和记录人类裁决，不会自动通过。

Gate A 前可先跑 `python scripts/novel.py pilot-reader-experience A --write` 汇总前三章体验证据；它会给出 `continue/rework/reopen_direction/stop` 机器建议，不写 canon，也不写 event ledger。第 10 章后，`chapter-evidence` 会要求当前的 `long-health --to {chapter} --write` 报告不是 `BLOCKED`。

## DeepSeek 边界

- DeepSeek 通过本地脚本调用 API。
- 默认模型：`deepseek-v4-pro`。
- 真实密钥只从 `DEEPSEEK_API_KEY` 读取，不写入仓库。
- DeepSeek 只能写 `drafts/deepseek/`、`reviews/{chapter}/deepseek_integrated_review.md` 和 `external_runs/deepseek/`；被人类选择的 DeepSeek 候选稿可由 Codex 原样落入 `chapters/`。
- DeepSeek review 不能把 Codex review 作为输入。
- Codex 子 agent 防 AI 味审查先通过 `python scripts/novel.py codex-anti-ai-review-start {chapter}` 生成 prompt 和 manifest；子 agent 只能读取官方正文、正式 brief、context pack、review context、style contract 和 reader promise，不能读取 DeepSeek review、integrated review、model disagreement、`ai_taste.*` 或 `dialogue_function.*`。
- DeepSeek 防 AI 味审查只能通过 `python scripts/novel.py deepseek-anti-ai-review {chapter}` 写 `reviews/{chapter}/deepseek_anti_ai_review.md/json` 和 `external_runs/deepseek/{chapter}/anti_ai_review.*`；它不能读取 `ai_taste.*`、`dialogue_function.*`、Codex review、Codex anti-AI review 或 `model_disagreement.md`。

## 维护与发布前检查

```bash
python -m compileall scripts tests
python scripts/novel.py check
python scripts/novel.py self-test
python scripts/novel.py status
python scripts/novel.py desk --write-report --html
python scripts/novel.py evidence v01_c001
python scripts/novel.py gate-check A
python scripts/novel.py export --volume v01
python scripts/novel.py backup --label release-smoke
python scripts/run_deepseek_generate.py --chapter v01_c001 --dry-run
python scripts/run_deepseek_review.py --chapter v01_c001 --dry-run
python scripts/run_deepseek_style_review.py --chapter v01_c001 --dry-run
python scripts/run_deepseek_anti_ai_review.py --chapter v01_c001 --dry-run
python scripts/run_deepseek_semantic_reader_review.py --chapter v01_c001 --dry-run
```

`evidence`、`gate-check` 和 `export` 在未完成项目里应返回 NOT_READY 或拒绝导出；这说明守卫在工作。
# Context Governance

`context_pack` 是单章驾驶舱，不是全书资料包。预算读取 `ops/process_budget.yaml`；每次 `start` 会生成 `state/context_pack/{chapter}.md`、同名 `.manifest.json` 和 `state/derived/context_quality/{chapter}.json`。Gate F/G/H 分别在 200/500/800 章检查长期状态索引、伏笔账本、设定债务和终局治理。
