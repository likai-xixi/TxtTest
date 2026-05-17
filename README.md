# Novel 300w Template

这是一个长篇小说试点模板仓库。它的目标不是替你自动决定故事，而是把“人类总编 + Codex 工程总控 + DeepSeek 外部候选/审查”的流程落成可复制、可校验、可追踪的工程系统。

## 复制后 5 步开工

1. 复制整个仓库到新目录。
2. 在新目录运行：

   ```bash
   python scripts/template_init.py --project-name "你的小说名"
   ```

3. 如需 DeepSeek，设置环境变量 `DEEPSEEK_API_KEY`。不要把真实 key 写进仓库。
4. 复制并填写问卷：

   ```bash
   copy templates\questionnaire_answers.md setup_answers.md
   python scripts/apply_questionnaire.py --answers setup_answers.md
   ```

5. 填写 `outline/chapter_briefs/v01_c001.md` 后启动第一章：

   ```bash
   python scripts/start_chapter.py --chapter v01_c001 --deepseek-dry-run
   ```

如果你已经配置了 `DEEPSEEK_API_KEY`，可以把 `--deepseek-dry-run` 换成：

```bash
python scripts/run_deepseek_generate.py --chapter v01_c001
```

## 每章标准命令

创建下一章工作区：

```bash
python scripts/new_chapter.py --chapter v01_c002
```

构建 context pack：

```bash
python scripts/start_chapter.py --chapter v01_c002
```

落正式正文后检查：

```bash
python scripts/validate_chapter.py --chapter v01_c002
python scripts/continuity_check.py --chapter v01_c002
python scripts/compare_model_reviews.py --chapter v01_c002
```

人类裁决后记录决定：

```bash
python scripts/record_decision.py --chapter v01_c002 --decision "Ship"
```

追加人类确认事实：

```bash
python scripts/append_event.py --chapter v01_c002 --type character_decision --fact "事实" --evidence-quote "正文证据" --consequence "后果"
python scripts/build_derived_state.py
```

## 关键边界

- `bible/canon.md` 只放正文出现且人类确认的硬事实。
- `state/event_ledger.jsonl` 只追加，不由外部模型直接写。
- DeepSeek 输出默认只是候选或审查建议。
- 3 章前不判断 300 万字可行性。
- 正文只读 `state/context_pack/{chapter}.md` 和当章 brief。

## 自检

模板完整性检查：

```bash
python scripts/check_template.py
```

项目状态：

```bash
python scripts/project_status.py
```

