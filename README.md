# Novel 300w Template

这是一个长篇小说试点模板仓库。目标不是自动替人类决定故事，而是把“人类总编 + Codex 工程总控 + DeepSeek 外部候选/审查”落成可复制、可校验、可追踪的工程系统。

## 一个入口

正式流程优先使用：

```bash
python scripts/novel.py desk
python scripts/novel.py flow
python scripts/novel.py status
python scripts/novel.py check
python scripts/novel.py self-test
```

底层脚本保留给排查和测试；正式写入候选选择、落章、审查、裁决、Gate、事件和提交时使用 `scripts/novel.py`。

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

每章 brief 还要声明新元素边界：

- `本章可用道具 IDs`：只列本章允许使用的 `bible/objects.yaml` ID。
- `本章可用技能 IDs`：只列本章允许使用的 `bible/abilities.yaml` ID。
- `本章允许新增元素`：L0 场景细节、L1 一次性线索、L2 伏笔、L3 长期机制、L4 核心设定分别说明。
- `本章禁止临场解决`：禁止靠未授权新道具、新能力或新规则解决本章核心问题。

`build_context_pack` 会按 ID 拉完整道具/技能条目；未列入 ID 或新增授权的元素，只能做细节、线索或伏笔，不能临场破局。

需要排查时再拆成细分命令：

```bash
python scripts/novel.py new-chapter v01_c001
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
