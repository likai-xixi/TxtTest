# Privacy Checklist

- 不提交 `.env` 或真实 API key。
- DeepSeek raw JSON 放在 `external_runs/**/*.raw.json`，默认由 `.gitignore` 忽略。
- `external_runs/**/*.manifest.json` 是可审计元数据：只有随正式章节证据有意提交时才保留；发布空模板前必须确认没有无关运行残留。
- 不把私人素材、读者隐私、未授权原文输入外部模型。
- 外部模型输出默认是候选或建议，不是事实；DeepSeek 候选只有经人类选择和 Codex landing provenance 后才可成为正式章。
