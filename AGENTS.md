# Novel 300w Workflow

本仓库由 Codex app 做工程总控：管理文件、Git、脚本、状态、汇总与最终落盘。人类总编拥有最高裁决权，决定主线、人物命运、设定取舍、章节是否继续。

## 核心原则

1. 先跑 3 章轻量试点；3 章前不判断 300 万字可行性。
2. AI 不靠记忆写长篇，只读 `state/context_pack/{chapter}.md` 和当章 brief。
3. Codex 与 DeepSeek 可以同时生成候选稿，但 DeepSeek 输出默认只是候选和建议。
4. Codex 与 DeepSeek 必须独立审查，互不读取对方报告。
5. `chapters/`、`bible/canon.md`、`state/event_ledger.jsonl`、Gate 通过权，只能由 Codex 在规则内落盘，并由人类最终裁决。

## 模板仓库使用方式

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
5. Codex 落正式 draft 到 chapters/
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
- `scripts/check_template.py`：检查模板完整性。
- `scripts/project_status.py`：输出下一步建议。
