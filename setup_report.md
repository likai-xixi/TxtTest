# Setup Report

初始化状态：模板仓库已准备。DeepSeek 脚本会从环境变量 `DEEPSEEK_API_KEY` 读取密钥；不要把真实密钥写进仓库。

复制到新目录后可运行：

```bash
python scripts/novel.py init --name "你的小说名"
python scripts/novel.py check
python scripts/novel.py status
```

## 你需要回答的启动问卷

请复制 `templates/questionnaire_answers.md` 为 `setup_answers.md` 后填写，再运行：

```bash
python scripts/novel.py apply-questionnaire --answers setup_answers.md
```

答案会先进入 `outline/premise.md` 与 `bible/open_questions.md`，不会直接进入 `bible/canon.md`。

1. 类型是什么？
2. 一句话卖点是什么？
3. 主角是谁？
4. 主角想要什么？
5. 主角怕失去什么？
6. 主角误信念是什么？
7. 世界最大异常是什么？
8. 核心冲突来自哪里？
9. 第一章开篇吸引点是什么？
10. 前三章要验证什么？
11. 绝对不写什么？
12. 参考作品只允许借鉴哪些抽象技法？

## 当前缺口

- 未配置 `DEEPSEEK_API_KEY`。
- 未填写启动问卷。
- 未有人类确认的 canon 事实。
- `event_ledger.jsonl` 尚无正文事实事件。

## 推荐下一步

先回答启动问卷。Codex 将据此生成最小世界观、主角卡、第一卷 mini-outline，并等待你确认。确认后再填写 `outline/chapter_briefs/v01_c001.md` 并运行：

```bash
python scripts/novel.py start v01_c001 --deepseek-dry-run
```
