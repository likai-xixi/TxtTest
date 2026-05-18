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

检查：

```bash
python scripts/novel.py core-freeze-check
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
python scripts/novel.py brief-candidates v01_c001
python scripts/novel.py deepseek-brief v01_c001
python scripts/novel.py select-brief v01_c001 --choice Codex --reason "..."
python scripts/novel.py land-brief v01_c001 --source Codex --from-candidate Codex --attestation "..."
python scripts/novel.py start v01_c001
```

## 新元素授权

每章 brief 必须写清：

- `本章可用道具 IDs`：只列本章允许使用的 `bible/objects.yaml` ID。
- `本章可用技能 IDs`：只列本章允许使用的 `bible/abilities.yaml` ID。
- `本章允许新增元素`：按 L0/L1/L2/L3/L4 标明哪些新元素可出现。
- `本章禁止临场解决`：禁止靠未授权新道具、新能力或新规则解决本章核心问题。

DeepSeek 和 Codex 可以创造新鲜细节，但重要新元素必须有授权、伏笔或后续归档。

## Gate 提醒

第 3、10、25、125 章完成后，必须优先进入对应 Gate。Gate 只检查证据，不会自动通过，最终由人类总编裁决。
