# Novel 300w Template

这是一个长篇小说试点模板仓库。它的目标不是替你自动决定故事，而是把“人类总编 + Codex 工程总控 + DeepSeek 外部候选/审查”的流程落成可复制、可校验、可追踪的工程系统。

## 一个入口

日常只需要记住一个入口：

```bash
python scripts/novel.py flow
python scripts/novel.py status
```

底层脚本仍然保留，方便排查和自动化；但在 Codex app 里开新书、写章节、收章节、Gate、备份、导出，都优先用 `scripts/novel.py`。

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

落正式正文后审查：

```bash
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
python scripts/novel.py gate A
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

## 自检

模板完整性检查：

```bash
python scripts/novel.py check
```

项目状态：

```bash
python scripts/novel.py status
```
