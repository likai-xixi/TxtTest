# 总编口令

在 Codex app 里优先说口令，不需要记脚本链条。

## 常用

```text
想法：……
开书实验
定盘
继续
加设定：……
写下一章
收章 v01_c001
查状态
```

## 诊断工具

```bash
python scripts/novel.py desk
python scripts/novel.py idea-status --id idea_xxx
python scripts/novel.py deepseek-preflight
python scripts/novel.py workflow-map --format mermaid
python scripts/novel.py brief-precheck v01_c001
python scripts/novel.py brief-diagnose v01_c001
python scripts/novel.py health-report
python scripts/novel.py opening-preflight --agents-ready --json
python scripts/novel.py pilot-reader-experience A --write
python scripts/novel.py long-health --to v01_c010 --write
python scripts/novel.py event-suggest v01_c001
python scripts/novel.py pacing-dashboard v01_c001 --write
python scripts/novel.py desk --json
python scripts/novel.py status --json
python scripts/novel.py context-diff v01_c001
python scripts/novel.py candidate-compare v01_c001 --brief
python scripts/novel.py gate-rehearsal A
python scripts/novel.py stale-check v01_c001
python scripts/novel.py workflow-smoke
python scripts/novel.py audit
python scripts/novel.py audit --write-report
python scripts/novel.py ci
python scripts/novel.py reader-promise-start
python scripts/novel.py reader-promise-check
python scripts/novel.py reader-reward-check v01_c001 --write
python scripts/novel.py reader-reward-index --write
python scripts/novel.py reader-reward-migration-report
python scripts/novel.py reader-experience-check v01_c001
python scripts/novel.py ai-taste-check v01_c001
python scripts/novel.py dialogue-function-check v01_c001
python scripts/novel.py review-context v01_c001 --write
python scripts/novel.py codex-anti-ai-review-start v01_c001
python scripts/novel.py deepseek-anti-ai-review v01_c001 --dry-run
python scripts/novel.py migrate-anti-ai-reviews v01_c001
python scripts/novel.py personality-check
python scripts/novel.py suspense-check
python scripts/novel.py world-reveal-check
python scripts/novel.py protagonist-progression-check
python scripts/novel.py idea-form --commercial --id idea_xxx
python scripts/novel.py market-scan --id idea_xxx
python scripts/novel.py table-build
python scripts/novel.py polish-start v01_c001
```

`desk` 是总编台，优先看当前阶段、唯一卡点、推荐口令、风险标记和证据路径。`audit` 是总编全量体检，会完整跑业务门禁并汇总当前卡点；`audit --write-report` 额外写 `state/audit/latest.md` 和时间戳报告，业务 NOT_READY 仍会返回非 0。`ci` 是本地模板 CI，只跑代码和流程回归，不因项目尚未开书而失败。`idea-status` 用于定盘前检查 DeepSeek、三类 agent、agent run 元数据、manifest 与 synthesis 是否齐。`brief-precheck` 是生成 brief 候选前的智能检查；`brief-diagnose` 只解释 `brief-check` 失败原因，不替代硬门禁。`pacing-dashboard` 是节奏和后果债务的人读视图，不新增门禁。`event-suggest` 只输出人类可确认的事件命令草案，不写事件账本。

## 开书前定盘

开正文前必须先完成 DeepSeek + `product_founder` + `technical_lead` + `qa_release` 的开书实验，运行 `idea-agent-manifest` 记录三类审查 provenance，并生成 `core_setting_freeze`。冻结内容至少包括：

- 世界观核心规则
- 世界观硬边界
- 主角异常原因
- 主角家属/亲密关系
- 家属剧情功能与风险
- 前三章约束
- 不可违背红线
- 仍可开放的问题
- 主角初始人格合同 `initial_personality`

检查：

```bash
python scripts/novel.py core-freeze-check
```

核心冻结通过后，开正文前还必须把读者体验合同落为 READY：

```bash
python scripts/novel.py reader-promise-start
python scripts/novel.py reader-promise-land --ready
python scripts/novel.py reader-promise-check --require-ready
```

`reader promise` 必须手动声明 R0-R4 回报强度策略：`opening_chapter_count`、`opening_intensity_by_chapter`、`default_chapter_intensity`、`allowed_chapter_overrides` 和 `rationale`。模板只定义 R 档含义，不默认前三章 R3，也不默认全书 R2。

三类 agent 审查完成后，先逐条记录结构化运行证据，再生成 manifest：

```bash
python scripts/novel.py idea-agent-run --id idea_xxx --role product_founder --agent-id agent_pf_001 --runner-id codex_pf_001 --transcript state/idea_lab/idea_xxx/product_founder_transcript.md --isolation-attestation "Read only original_idea.md and deepseek_idea.md." --output state/idea_lab/idea_xxx/product_founder_review.md
python scripts/novel.py idea-agent-run --id idea_xxx --role technical_lead --agent-id agent_tl_001 --runner-id codex_tl_001 --transcript state/idea_lab/idea_xxx/technical_lead_transcript.md --isolation-attestation "Read only original_idea.md and deepseek_idea.md." --output state/idea_lab/idea_xxx/technical_lead_review.md
python scripts/novel.py idea-agent-run --id idea_xxx --role qa_release --agent-id agent_qa_001 --runner-id codex_qa_001 --transcript state/idea_lab/idea_xxx/qa_release_transcript.md --isolation-attestation "Read only original_idea.md and deepseek_idea.md." --output state/idea_lab/idea_xxx/qa_release_review.md
python scripts/novel.py idea-agent-manifest --id idea_xxx
```

## 开章

```text
写下一章
开章 v01_c001
```

如果核心设定冻结缺失，开章会停止，不会生成 context pack 或候选稿。

若正式 brief 缺失或仍有占位，`写下一章` 先进入 brief 候选流程：

```text
写下一章
-> Codex 生成 drafts/codex/{chapter}_brief.md
-> DeepSeek 生成 drafts/deepseek/{chapter}_brief.md
-> Codex 汇总优劣
-> 人类选择 / 混合 / 修改
-> Codex 落正式 outline/chapter_briefs/{chapter}.md
-> start 生成 context pack
-> 再分别生成正文候选
```

命令行等价入口：

```bash
python scripts/novel.py brief-precheck v01_c001
python scripts/novel.py brief-candidates v01_c001
python scripts/novel.py deepseek-brief v01_c001
python scripts/novel.py select-brief v01_c001 --choice Codex --reason "..."
python scripts/novel.py land-brief v01_c001 --source Codex --from-candidate Codex --attestation "..."
python scripts/novel.py start v01_c001
```

## Story Card / Machine Appendix

新 brief 默认是 `schema_version: 2`：

- 写作入口看 `Story Card`：第一屏扰动、主角想要、主角主动动作、最大阻力、中段变化点、本章小兑现、`before -> after`、章末点击理由、一条世界规则和禁止临场破局。
- 机器治理看 `Machine Contract Appendix`：上章锚点、开场落点、场景承接、S/W 档位、继承变化、节奏用途、进展契约、代价后果、解决边界、R 档回报、低戏剧载体、核心机制状态、可用道具/技能 ID、允许新增元素和最低落账事件。
- v1 旧 brief 仍可兼容读取，但新生成、新模板、新提示和开书试点 brief 都用 v2。
- 六段长审计合同不再放在 brief 主体；防 AI 味、对白功能、句式、细节、私心和情绪越界由正文风格要求与收章 review 检查。

`brief-precheck` 在生成候选 brief 前检查核心冻结、上一章锚点、Gate、stop lock、后果债务和关键源占位；`brief-check` 做正式 brief 的单章硬检查，并硬拦缺标题、缺 `before -> after`、缺 R 档、缺小兑现、缺主角主动动作和缺下一章点击理由；`reader-reward-check --write` 生成单章 reader reward gate，并拦 R2+ 无正文回报 quote、主角无主动动作 evidence、世界规则只有解释没有场景测试；`reader-reward-index --write` 汇总跨章等待、核心机制沉默、三章无小兑现、低戏剧载体重复和章末钩子重复。`pacing-check` 会硬拦三章窗口无有效推进、连续小事和高推进无消化。10 章后用 `long-health --to {chapter} --write` 看最近 5 章滚动健康窗。

DeepSeek 和 Codex 可以创造新鲜细节，但重要新元素必须有授权、伏笔或后续归档。

## Candidate Prompt Style Evidence

Candidate chapter generation must now leave prompt evidence before candidate selection.

```bash
python scripts/novel.py codex-draft-prompt v01_c001
python scripts/novel.py deepseek-generate v01_c001 --dry-run
python scripts/novel.py deepseek-generate v01_c001
```

- Codex prompt evidence is written to `external_runs/codex/{chapter}/draft.prompt.md` and `draft.prompt.manifest.json`.
- DeepSeek prompt evidence is written to `external_runs/deepseek/{chapter}/generate.prompt.md` and `generate.prompt.manifest.json`.
- Both prompts must start with `# Candidate Style Requirements`.
- `select-candidate`, `land`, and `evidence` verify the selected provider prompt manifests, context pack hash, and style source hashes.
- Candidate Style Requirements now inject anti-AI constraints: no safe summary voice, no role-as-theme-mouthpiece dialogue, no decorative detail dump, and no gray action without visible cost or later accountability.

## Anti-AI Review Gates

```bash
python scripts/novel.py ai-taste-check v01_c001
python scripts/novel.py dialogue-function-check v01_c001
python scripts/novel.py review-context v01_c001 --write
python scripts/novel.py codex-anti-ai-review-start v01_c001
python scripts/novel.py deepseek-anti-ai-review v01_c001
python scripts/novel.py migrate-anti-ai-reviews --all
```

`ai_taste` is kept for compatibility, but it is now the structured anti-AI review. Ship evidence requires `ai_taste.md/json`, `dialogue_function.md/json`, independent Codex subagent `codex_anti_ai_review.md/json`, and independent DeepSeek `deepseek_anti_ai_review.md/json`. `review-context` provides structured state and key prior quotes to reviewers without including previous chapters as full text. Markdown reviews marked `CLEAR` must bind to the current official chapter hash, current review body hash, and at least one matching `Evidence Quotes` line. Human acceptance is available only with `accepted_by: human`, `accepted_at`, `reason`, current official chapter hash, and current review hash.

## Receive Chapter Control Plane

```bash
python scripts/novel.py receive-chapter v01_c001 --preview
python scripts/novel.py receive-chapter v01_c001 --resume
python scripts/novel.py review-context v01_c001 --write
python scripts/novel.py revision-plan v01_c001
python scripts/novel.py review-arbitration v01_c001
python scripts/novel.py accept-review v01_c001 --artifact ai_taste --reason "intentional house style"
python scripts/novel.py gray-consequence v01_c001 --write
python scripts/novel.py chapter-shape-check v01_c006 --write
python scripts/novel.py emotion-relationship-gate v01_c001 --write
python scripts/novel.py semantic-reader-review v01_c001 --write
python scripts/novel.py memorable-scene-check v01_c001 --write
python scripts/novel.py reader-feedback add v01_c001 --reader reader_001 --target-reader "pilot reader" --stuck-point "..." --continue-reason "..." --promise-gap "..." --favorite-moment "..." --skip-moment "..." --next-click-intent "..." --protagonist-charm "..." --author-explanation-feel "..." --suspense-feel "..."
python scripts/novel.py reader-feedback summarize v01_c001
python scripts/novel.py reader-risk-index --to v01_c010 --write --json
python scripts/novel.py deepseek-manifest-check v01_c001 --kind anti_ai_review
```

`receive-chapter` is an orchestrator, not an auto-Ship command. It may run deterministic local checks and report the next editor action, but it does not write canon, does not write event ledger entries, and does not replace the human editor decision.

`reader-feedback summarize` only counts recorded reader responses as real feedback. Responses saved with `--allow-incomplete` remain visible as ignored drafts and cannot satisfy Gate evidence by themselves.

Codex anti-AI subagent review leaves `reviews/{chapter}/codex_anti_ai_review_prompt.md` and `codex_anti_ai_review_manifest.json`; Ship evidence rejects missing manifest inputs, stale hashes, forbidden inputs, and missing final `codex_anti_ai_review.md/json`. Codex semantic reader review uses the same prompt/manifest pattern at `codex_semantic_reader_review_prompt.md` and `codex_semantic_reader_review_manifest.json`. DeepSeek review, anti-AI review, semantic reader review, and style review leave run manifests under `external_runs/deepseek/{chapter}/`. Ship evidence rejects missing manifests, stale hashes, and forbidden inputs such as Codex review files being included in DeepSeek anti-AI or semantic reader review inputs.

## Gate 提醒

第 3、10、25、125 章完成后，必须优先进入对应 Gate。Gate 只检查证据，不会自动通过，最终由人类总编裁决。

第 3 章前后可用 `pilot-reader-experience A --write` 汇总前三章体验证据，并查看 `continue/rework/reopen_direction/stop` 建议；第 10 章后，Ship evidence 还会要求当前 `long-health --to {chapter} --write` 报告不为 `BLOCKED`。每章收章前可跑 `reader-risk-index --to {chapter} --write` 汇总节奏、重复、悬念、人物、世界观、视角、语言和结构效率风险。

## P0.6 / P0.7 Contracts

Book outline and style contract are planning and writing-voice assets. They are not canon, not event ledger entries, and not chapter text.

```bash
python scripts/novel.py book-outline-start --id idea_xxx
python scripts/novel.py book-outline-check --id idea_xxx
python scripts/novel.py book-outline-land --id idea_xxx --source selected --build-volume
python scripts/novel.py volume-outline-build --volume v01
python scripts/novel.py volume-outline-check --volume v01

python scripts/novel.py style-contract-start --id idea_xxx
python scripts/novel.py style-contract-check --id idea_xxx
python scripts/novel.py style-contract-land --id idea_xxx --source selected
python scripts/novel.py style-profile-build
python scripts/novel.py style-check v01_c001
python scripts/novel.py series-style-check v01_c004
python scripts/novel.py deepseek-style-review v01_c004 --dry-run
python scripts/novel.py deepseek-anti-ai-review v01_c004 --dry-run
python scripts/novel.py codex-semantic-reader-review-start v01_c004
python scripts/novel.py deepseek-semantic-reader-review v01_c004 --dry-run
python scripts/novel.py style-drift-report
```

`semantic-reader-review` is a Codex/DeepSeek LLM aggregate. Run the Codex semantic start command, complete the isolated Codex review into `reviews/{chapter}/codex_semantic_reader_review.md/json`, run the DeepSeek semantic reader review, then run `semantic-reader-review --write`.

Series-style policy:

- Chapters 1-3 are style warmup and are used to build `state/derived/style_profile.json`.
- From chapter 4, run `series-style-check` after `style-check`; the report is required by Ship evidence.
- Chapters 4-5 can Ship with `WARNING`; chapter 6+ must be `READY` or explicitly `ACCEPTED_BY_HUMAN`.
- `deepseek-style-review` is optional by default, but `series-style-check --require-deepseek` can make the external style review a required input.

`start` and `write` are blocked until `core_setting_freeze`, `outline/book_outline.json`, and `state/project_style_contract.json` are READY. `context_pack` may include the book outline only as `strategic_plan_not_fact_source`, and style assets only as `style_instruction_not_fact_source`.
`start` and `write` are also blocked until `state/project_reader_promise.json` is `READY`. Reader Promise v2 must declare positive promises, negative failure modes, release-valve policy, protagonist agency, information clarity, language experience, structural efficiency, and R-level reward policy. Reader promise is an instruction source only; it is included in context pack as `reader_promise_instruction_not_fact_source`, while initial/current personality and reader experience ledgers are derived state.
