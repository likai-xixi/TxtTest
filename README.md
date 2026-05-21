# Novel 300w Template

## 3-minute copied-template guide

```bash
python scripts/novel.py start-here
python scripts/novel.py opening-preflight --json
python scripts/novel.py opening-preflight --live
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

这个命令必须真实调用 DeepSeek；没有 `DEEPSEEK_API_KEY` 会直接停止。DeepSeek 完成后，Codex app 必须启用 `product_founder`、`technical_lead`、`qa_release` 三类 agent，并把审查写入 `state/idea_lab/{idea_id}/`。三类审查完成后先记录 provenance：

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

每章 brief 还要声明场景连续性、节奏档位和新元素边界：

- `上章章末锚点`：记录上一章最后可见状态，包括时间、地点、在场人物、主角状态、携带物 / 证据、未完成动作；首章写“开篇章，无上章”。
- `本章开场落点`：记录本章第一场的时间、地点、在场人物、主角状态和第一动作。
- `场景承接说明`：写 `类型：原地承接 / 明示跳切 / 省略过桥 / 开篇起始` 和具体说明；如果从办公室跳到街边，必须写清时间差、离开原因和转移动作。
- `主线牵引档位`：以 `S0`-`S4` 开头，说明本章与核心主线的距离；低档章必须有功能，高档章必须写后果。
- `外部压力档位`：以 `W0`-`W4` 开头，说明外部世界、制度、势力、资源或关系如何影响本章行动。
- `本章继承变化`：写明本章承接的状态、关系、信息或限制；开篇章也要写初始状态，不能写 none。
- `本章节奏用途` / `节奏说明`：说明本章是推进、缓冲、兑现、铺垫、转场、蓄压还是爆发，并解释为什么不会空转或强行加速。
- `本章进展契约`：声明进展类型、推进对象、起始状态依据、结束状态变化、最低落账事件、进展重要度和低牵引功能；每章都必须留下可核验的状态变化。
- `本章代价与后果契约`：声明推进重量 `C0`-`C4`、后果等级 `reversible/scar/structure_change`、代价、后果承接义务、消化窗口和冷却范围；高推进不能无代价解决。
- `本章解决边界`：声明新开、推进、解决和禁止解决的伏笔；解决伏笔非空时必须付代价。
- `本章可用道具 IDs`：只列本章允许使用的 `bible/objects.yaml` ID。
- `本章可用技能 IDs`：只列本章允许使用的 `bible/abilities.yaml` ID。
- `本章允许新增元素`：L0 场景细节、L1 一次性线索、L2 伏笔、L3 长期机制、L4 核心设定分别说明。
- `本章禁止临场解决`：禁止靠未授权新道具、新能力或新规则解决本章核心问题。
- `本章留存合同`：第一屏钩子、核心问题、中段加压、小兑现、章末钩子和下一章点击理由。
- `本章主角魅力合同`：主动目标、过人之处、弱点误判、金手指/特殊资源、刻度变化和读者喜欢主角的瞬间。
- `本章初始人格挑战合同`：声明本章压迫哪些初始人格字段，若真实改变必须走 `personality_delta`。
- `本章世界观展示合同` / `本章名词预算`：限制新名词，并要求规则通过场景、冲突或人物反应展示。
- `本章悬念推进合同`：旧问题、新线索、部分解答、新问题和状态。
- `本章语言记忆点`：金句、梗/反差句、口头禅或标志动作，以及禁止的平铺语气。

`python scripts/novel.py brief-precheck {chapter}` 是生成候选 brief 前的智能预检，会检查核心冻结、上一章锚点、Gate、stop lock、关键源占位和后果承接债务；`python scripts/novel.py brief-check {chapter}` 是正式 brief 的单章硬门禁；`python scripts/novel.py pacing-check {chapter} --write` 是跨章硬门禁加预警：连续 3 章都是 `C0/C1` 会 BLOCK，高推进或 payoff 后没有在消化窗口内承接也会 BLOCK。`python scripts/novel.py pacing-dashboard {chapter} --write` 会生成节奏与 aftermath 人读报告，不替代硬门禁。

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
- `python scripts/novel.py review-context {chapter} --write` writes review-only structured state and key quotes; it is for reviewers and excludes previous chapters as full text.
- `python scripts/novel.py codex-anti-ai-review-start {chapter}` writes an isolated Codex subagent prompt and manifest; the subagent must write `reviews/{chapter}/codex_anti_ai_review.md/json`.
- `python scripts/novel.py deepseek-anti-ai-review {chapter}` writes `reviews/{chapter}/deepseek_anti_ai_review.md` and `deepseek_anti_ai_review.json`; this is required Ship evidence, not optional style advice.
- `python scripts/novel.py series-style-check {chapter}` writes `reviews/{chapter}/series_style.json`.
- Chapters 1-3 are warmup. From chapter 4 the series-style report is required; chapters 4-5 allow `WARNING`; chapter 6+ requires `READY` or `ACCEPTED_BY_HUMAN`.
- Optional DeepSeek style review: `python scripts/novel.py deepseek-style-review {chapter}` writes `reviews/{chapter}/deepseek_style_review.json`; `series-style-check --require-deepseek` can make it a required input.

Anti-AI taste evidence is a hard Ship gate in this template. `ai_taste` keeps its legacy name but now means the structured anti-AI review: show-don't-tell, rhythm disorder, emotional risk, gray motive, dialogue agenda, detail economy, and consequence integrity. Codex has a separate isolated subagent hard-gate report at `codex_anti_ai_review.md/json`; DeepSeek also has an independent hard-gate report at `deepseek_anti_ai_review.md/json`. The two independent reports both receive the review context, but they do not read each other, the integrated reviews, model disagreement, or legacy anti-AI/dialogue outputs. All auxiliary reviews marked `CLEAR` must include the current official chapter hash, a current `review_sha256`, and at least one `Evidence Quotes` line that matches the official chapter after whitespace folding. `ACCEPTED_BY_HUMAN` is allowed for taste disputes only when it records `accepted_by: human`, `accepted_at`, `reason`, current official chapter hash, and current review body hash.

New chapter briefs must include the six human-texture contracts: anti-AI taste, emotional boundary crossing, private motive and dirty play, dialogue function, rhythm disorder, and detail economy. Candidate prompts receive the same instructions, including that gray behavior is allowed but must leave consequences and, when it changes durable state, still goes through event ledger and personality-delta gates.

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
python scripts/novel.py reader-feedback summarize v01_c001
python scripts/novel.py deepseek-manifest-check v01_c001 --kind anti_ai_review
```

It writes `reviews/{chapter}/receive_chapter.json/md` and reports the exact next action. It does not auto-Ship, does not write canon, and does not write event ledger entries. Ship still goes through `chapter-evidence` and the human editor decision.

DeepSeek review, anti-AI review, and style review now require run manifests at `external_runs/deepseek/{chapter}/{kind}.manifest.json`. These manifests bind model, prompt, raw response, output, allowed inputs, forbidden inputs, and isolation attestation. Missing, stale, or contaminated manifests block Ship.

Revision plans, review arbitration, gray consequence reports, chapter-shape reports, and reader-feedback summaries are scaffolded for every chapter. High-impact gray behavior must be covered by human-verified event/fact evidence. Chapter-shape repetition is advisory during warmup and hard from chapter 6 when it repeats the same shape. Reader feedback is reader-experience evidence only and never a canon or event-ledger source.

## Gate

```bash
python scripts/novel.py gate-check A
python scripts/novel.py gate A
python scripts/novel.py gate-close A --decision continue --reason "..." --next-limits "..." --continue-to v01_c010 --budget "..." --primary-model Codex --must-fix "..." --stop-trigger "..."
```

Gate A/B 需要章节证据、reader promise 兑现、主角主动性、初始人格稳定性、悬念推进、世界观场景化展示、读者反馈和 synthesis。Gate F/G/H 还会复盘 suspense ledger、world reveal/concept ledger 和 protagonist progression 的长线债务。Gate 命令只检查证据和记录人类裁决，不会自动通过。

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
python scripts/novel.py evidence v01_c001
python scripts/novel.py gate-check A
python scripts/novel.py export --volume v01
python scripts/novel.py backup --label release-smoke
python scripts/run_deepseek_generate.py --chapter v01_c001 --dry-run
python scripts/run_deepseek_review.py --chapter v01_c001 --dry-run
python scripts/run_deepseek_style_review.py --chapter v01_c001 --dry-run
python scripts/run_deepseek_anti_ai_review.py --chapter v01_c001 --dry-run
```

`evidence`、`gate-check` 和 `export` 在未完成项目里应返回 NOT_READY 或拒绝导出；这说明守卫在工作。
# Context Governance

`context_pack` 是单章驾驶舱，不是全书资料包。预算读取 `ops/process_budget.yaml`；每次 `start` 会生成 `state/context_pack/{chapter}.md`、同名 `.manifest.json` 和 `state/derived/context_quality/{chapter}.json`。Gate F/G/H 分别在 200/500/800 章检查长期状态索引、伏笔账本、设定债务和终局治理。
