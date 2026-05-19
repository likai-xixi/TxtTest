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

同时只会生成试点资产：`outline/premise.md`、`bible/open_questions.md`、`outline/gate_a_3_chapters.md`、`outline/chapter_briefs/v01_c001.md`。不会写 canon、正文或 event ledger。

检查冻结证据：

```bash
python scripts/novel.py core-freeze-check
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
python scripts/novel.py codex-review-start v01_c001
```

先运行 `codex-review-start` 记录 Codex 审查输入 manifest，再写 `reviews/v01_c001/codex_integrated_review.md`。随后：

```bash
python scripts/novel.py review v01_c001 --deepseek
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
- DeepSeek 只能写 `drafts/deepseek/`、`reviews/{chapter}/deepseek_integrated_review.md` 和 `external_runs/deepseek/`；被人类选择的 DeepSeek 候选稿可由 Codex 原样落入 `chapters/`。
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
# Context Governance

`context_pack` 是单章驾驶舱，不是全书资料包。预算读取 `ops/process_budget.yaml`；每次 `start` 会生成 `state/context_pack/{chapter}.md`、同名 `.manifest.json` 和 `state/derived/context_quality/{chapter}.json`。Gate F/G/H 分别在 200/500/800 章检查长期状态索引、伏笔账本、设定债务和终局治理。
