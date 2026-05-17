# Novel 300w Template

这是一个长篇小说试点模板仓库。它的目标不是替你自动决定故事，而是把“人类总编 + Codex 工程总控 + DeepSeek 外部候选/审查”的流程落成可复制、可校验、可追踪的工程系统。

## 一个入口

日常只需要记住一个入口：

```bash
python scripts/novel.py flow
python scripts/novel.py status
```

底层脚本仍然保留，方便排查和自动化；但在 Codex app 里开新书、写章节、收章节、Gate、备份、导出，都优先用 `scripts/novel.py`。

工作流写入口以 `scripts/novel.py` 为准。底层脚本用于内部编排、排查和测试；绕过 `novel.py` 直接调用底层写脚本，等同于绕过 stop lock、Gate 和审查证据链，不作为正式流程。

## 复制后 5 步开工

1. 复制整个仓库到新目录。
2. 在新目录运行：

   ```bash
   python scripts/novel.py init --name "你的小说名"
   ```

3. 如需 DeepSeek，设置环境变量 `DEEPSEEK_API_KEY`。不要把真实 key 写进仓库。
4. 复制并填写问卷：

   ```bash
   python scripts/novel.py questionnaire
   python scripts/novel.py apply-questionnaire --answers setup_answers.md
   ```

5. 填写 `outline/chapter_briefs/v01_c001.md` 后启动第一章：

   ```bash
   python scripts/novel.py start v01_c001 --deepseek-dry-run
   ```

如果你已经配置了 `DEEPSEEK_API_KEY`，可以把 `--deepseek-dry-run` 换成：

```bash
python scripts/novel.py deepseek-generate v01_c001
```

## 完整简化流程

创建下一章工作区：

```bash
python scripts/novel.py new-chapter v01_c002
```

构建 context pack：

```bash
python scripts/novel.py start v01_c002
```

生成 DeepSeek 候选：

```bash
python scripts/novel.py deepseek-generate v01_c002
```

记录人类选择的候选方向：

```bash
python scripts/novel.py select-candidate v01_c002 --choice "Mixed" --reason "人类选择混合方向" --mixed-strategy "DeepSeek 提供冲突方向，Codex 重写正文"
```

Codex 落正式正文后记录落章 provenance：

```bash
python scripts/novel.py land v01_c002 --source "Mixed" --attestation "Codex integrated the official chapter from the context pack, brief, and selected direction; no direct DeepSeek copy."
```

落正式正文后审查：

```bash
python scripts/novel.py codex-review-start v01_c002
python scripts/novel.py review v01_c002 --deepseek
```

人类裁决后记录决定：

```bash
python scripts/novel.py decision v01_c002 --decision "Ship"
```

追加人类确认事实：

```bash
python scripts/novel.py event v01_c002 --type character_decision --fact "事实" --evidence-quote "正文证据" --consequence "后果"
```

收章并提交：

```bash
python scripts/novel.py close v01_c002 --decision "Ship" --commit-message "complete v01 c002"
```

Gate 检查：

```bash
python scripts/novel.py reader-test summarize --gate A --risk "..." --recommendation "..."
python scripts/novel.py gate-check A
python scripts/novel.py gate A
python scripts/novel.py gate-close A --decision continue --reason "人类总编确认继续" --next-limits "只进入10章小连载验证" --continue-to v01_c010 --budget "10章小连载验证" --primary-model Codex --must-fix "主角目标保持清晰" --stop-trigger "连续三章目标不清"
```

备份和导出：

```bash
python scripts/novel.py backup --label before_gate_a
python scripts/novel.py export --volume v01
```

## 关键边界

- `bible/canon.md` 只放正文出现且人类确认的硬事实。
- `state/event_ledger.jsonl` 只追加，不由外部模型直接写。
- DeepSeek 输出默认只是候选或审查建议。
- 3 章前不判断 300 万字可行性。
- 正文只读 `state/context_pack/{chapter}.md` 和当章 brief。
- `close --commit-message` 会先跑章节校验、连续性、stop-check、event ledger、derived state 和 `diff_scope_check --role chapter`。
- `Ship` close 还要求结构化候选选择、官方正文落章 provenance、Codex/DeepSeek 审查、review manifest、model_disagreement 和无 P0/P1 continuity。
- DeepSeek review 只能审查正式正文或候选稿，不能把 Codex review 作为输入。
- Gate 命令只做证据检查和记录人类裁决，不会自动通过 Gate。
- 有未解决 stop lock 时，不能 start/review/close/new-chapter/gate-close。

## 自检

模板完整性检查：

```bash
python scripts/novel.py check
```

项目状态：

```bash
python scripts/novel.py status
```

回归测试：

```bash
python scripts/self_test.py
```

发布前至少运行：

```bash
python -m compileall scripts tests
python scripts/novel.py check
python scripts/self_test.py
python scripts/novel.py status
python scripts/novel.py chapter-evidence v01_c001
python scripts/novel.py gate-check A
python scripts/novel.py export --volume v01
python scripts/novel.py backup --label release-smoke
python scripts/run_deepseek_generate.py --chapter v01_c001 --dry-run
python scripts/run_deepseek_review.py --chapter v01_c001 --dry-run
```

说明：

- `chapter_evidence` 和 `gate-check` 在未完成章节时应返回 `NOT_READY`；真实章节 Ship / Gate 继续前必须通过。
- Gate A/B 至少需要三份 `reader_tests/responses/gate_a|gate_b/*.json` 读者反馈；每份必须有具体 `target_reader` 并完整回答 Gate 问题，然后生成无占位 synthesis。
- `stop-check` 触发 STOP 时会自动写入 open stop lock；lock 未解决前写入口会被阻断。
- 空卷导出应失败，避免把空正文当成可交付结果。
- DeepSeek live API 只有配置 `DEEPSEEK_API_KEY` 后才能验证；未配置时只能证明 dry-run 与输入隔离。DeepSeek review dry-run 只写 prompt，不写 review manifest。
- 备份包不得包含 `.env`、`*.raw.json`、`*.prompt.md`、`exports/`、`backups/` 或 `.git/`。
