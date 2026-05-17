# Novel 300w Workflow

本仓库由 Codex app 做工程总控：管理文件、Git、脚本、状态、汇总与最终落盘。人类总编拥有最高裁决权，决定主线、人物命运、设定取舍、章节是否继续。

## 核心原则

1. 先跑 3 章轻量试点；3 章前不判断 300 万字可行性。
2. AI 不靠记忆写长篇，只读 `state/context_pack/{chapter}.md` 和当章 brief。
3. Codex 与 DeepSeek 可以同时生成候选稿，但 DeepSeek 输出默认只是候选和建议。
4. Codex 与 DeepSeek 必须独立审查，互不读取对方报告。
5. `chapters/`、`bible/canon.md`、`state/event_ledger.jsonl`、Gate 通过权，只能由 Codex 在规则内落盘，并由人类最终裁决。

## 模板仓库使用方式

正式流程的写入口以 `scripts/novel.py` 为准。底层脚本保留给统一入口、测试和排查调用；不得绕过 `novel.py` 直接落候选选择、裁决、Gate、事件或提交。

复制本仓库到新目录后，先运行：

```bash
python scripts/novel.py init --name "你的小说名"
python scripts/novel.py check
python scripts/novel.py status
```

然后复制 `templates/questionnaire_answers.md` 为 `setup_answers.md`，填写启动问卷并运行：

```bash
python scripts/novel.py apply-questionnaire --answers setup_answers.md
```

第一章 brief 填完后运行：

```bash
python scripts/novel.py start v01_c001 --deepseek-dry-run
```

如果要创建后续章节：

```bash
python scripts/novel.py new-chapter v01_c002
```

完整简化流程可随时查看：

```bash
python scripts/novel.py flow
```

## 资产优先级

```text
canon
> event_ledger
> derived state
> context_pack
> chapter brief
> candidate draft
> model suggestion
```

## 试点期每章流程

```text
1. 写 chapter brief
2. build_context_pack
3. Codex / DeepSeek 生成候选稿
4. 人类选定候选方向
5. Codex 落正式 draft 到 chapters/，并记录 chapter_landing provenance
6. Codex 独立审查
7. DeepSeek 独立审查
8. continuity_check
9. compare_model_reviews
10. 人类判定
11. 最多一次 revision
12. 追加 event_ledger
13. build_derived_state
14. diff_scope_check
15. commit
```

人类判定只选：`Ship`、`Revise once`、`Rewrite brief`、`Kill chapter`、`Pause project`。

候选方向必须通过 `python scripts/novel.py select-candidate {chapter} --choice ...` 留痕。没有候选选择记录，不允许 Ship close。
Ship close 还必须通过 `chapter_evidence.py`：结构化候选选择、官方正文落章 provenance、Codex/DeepSeek 审查、review manifest、model_disagreement 和无 P0/P1 continuity 必须齐全。

## DeepSeek 边界

- DeepSeek 通过本地脚本调用 API。
- 默认模型名：`deepseek-v4-pro`。
- 环境变量：`DEEPSEEK_API_KEY`。
- DeepSeek 只能写候选输出目录和独立审查文件，不能直接改 `chapters/`、`bible/`、`state/`。
- `scripts/run_deepseek_generate.py --dry-run` 和 `scripts/run_deepseek_review.py --dry-run` 只生成 prompt，不触网。

## 写作硬规则

- 写正文前必须运行：`python scripts/build_context_pack.py --chapter v01_c001`。
- 正文只依据 context pack 和 chapter brief。
- 上下文不足时列缺口，不自行补设定。
- context pack 与 brief 冲突时停止并请求人类裁决。
- 重大设定先进入 chapter brief，再由人类确认是否进 canon。

## 关键脚本

- `scripts/novel.py`：模板的统一入口，覆盖开书、问卷、章节、候选、审查、裁决、事件、Gate、备份、导出、提交。
- `scripts/template_init.py`：复制后初始化模板目录和空账本。
- `scripts/apply_questionnaire.py`：把启动问卷写入 premise 与 open questions。
- `scripts/new_chapter.py`：创建章节 brief 与 review 工作区。
- `scripts/start_chapter.py`：校验 brief、生成 derived state、构建 context pack。
- `scripts/append_event.py`：追加人类确认事件到账本。
- `scripts/record_decision.py`：记录章节人类裁决。
- `scripts/record_candidate_selection.py`：记录人类选定候选方向。
- `scripts/record_chapter_landing.py`：记录正式正文落章 provenance，证明 Codex 依据 context pack、brief 和候选选择整合，不直接复制 DeepSeek。
- `scripts/chapter_evidence.py`：检查单章 Ship 前证据。
- `scripts/review_manifest.py`：记录 Codex / DeepSeek 审查输入哈希，审计防污染。
- `scripts/gate_check.py` / `scripts/record_gate_decision.py`：检查 Gate 证据并记录人类 Gate 裁决。
- `scripts/project_lock.py` / `scripts/stop_check.py`：管理 stop rules 锁和机器可判定停止条件。
- `scripts/self_test.py`：运行本地回归测试。
- `scripts/check_template.py`：检查模板完整性。
- `scripts/project_status.py`：输出下一步建议。
