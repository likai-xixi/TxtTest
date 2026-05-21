# Release Checklist

Before publishing or copying this template:

- Run `python -m compileall scripts tests`.
- Run `python scripts/novel.py check`.
- Run `python scripts/novel.py self-test`.
- Run `python scripts/novel.py workflow-smoke`.
- Run `python scripts/novel.py ci`.
- Run `python scripts/novel.py longrun-smoke --chapters 10`.
- Run `python scripts/novel.py audit --mode template`.
- Capture `python scripts/novel.py audit --mode release --json`; an unopened template should be `NOT_READY` because of expected story blockers, never `ERROR`.
- Confirm `reader-promise-check` returns `NOT_READY` until the project manually declares `reader_reward_intensity_policy`; no template default R档 is inferred.
- Confirm `new-chapter` scaffolds opening/personality/retention/charm/world/suspense/language/genre review files plus `ai_taste.md/json`, `dialogue_function.md/json`, `codex_anti_ai_review.md/json`, and `deepseek_anti_ai_review.md/json`.
- Confirm `new-chapter` also scaffolds `revision_plan`, `review_arbitration`, `gray_consequence`, `chapter_shape`, `reader_reward_gate`, `reader_feedback`, and `receive_chapter` Markdown/JSON artifacts.
- Confirm `receive-chapter --preview` writes nothing and lists the full control-plane sequence.
- Confirm `revision-plan`, `review-arbitration`, `gray-consequence`, `chapter-shape-check`, `reader-reward-check`, `reader-reward-index`, and `reader-feedback summarize --no-write` return `NOT_READY`/`BLOCKED` cleanly on an unopened template, not tracebacks.
- Confirm `deepseek-manifest-check` rejects missing, stale, and forbidden-input DeepSeek run manifests.
- Confirm `accept-review` writes current human metadata and rejects infrastructure blockers.
- Confirm `chapter-evidence` rejects missing, stale, quote-less, or `BLOCKED` auxiliary reviews unless `ACCEPTED_BY_HUMAN` is bound to the current official chapter hash and current review body hash.
- Confirm `chapter-evidence` rejects missing, stale, malformed, or contaminated review context at `state/context_pack/{chapter}_review_context.md/json`, and that the review context does not include previous chapters as full text.
- Confirm `chapter-evidence` rejects missing, stale, quote-less, or `BLOCKED` `reader_reward_gate.json/md`, and rejects stale `reader_reward_index.json`.
- Confirm `ai-taste-check`, `dialogue-function-check`, and `deepseek-anti-ai-review --dry-run` produce `NOT_READY`, not `ERROR`, when a copied template has no official chapter yet.
- Confirm `migrate-anti-ai-reviews` creates draft scaffolds without overwriting existing human review files and without marking anything `CLEAR`.
- Confirm `python scripts/novel.py codex-anti-ai-review-start v01_c001` writes only the isolated prompt and manifest, and never writes final `codex_anti_ai_review.md/json`.
- Confirm `chapter-evidence` rejects missing, stale, quote-less, malformed, or `BLOCKED` `codex_anti_ai_review.md/json`.
- Confirm `chapter-evidence` rejects missing, stale, quote-less, malformed, or `BLOCKED` `deepseek_anti_ai_review.md/json`.
- Confirm `python scripts/novel.py deepseek-anti-ai-review v01_c001 --dry-run` does not write final review files and its prompt excludes Codex review outputs.
- Confirm DeepSeek review, anti-AI review, and style review dry runs write only prompt/run manifest evidence and never final review artifacts.
- Confirm high-impact gray behavior without fact-card/event coverage blocks `gray-consequence`.
- Confirm chapter 6+ repeated shape blocks `chapter-shape-check`.
- Confirm per-chapter reader feedback writes only `reader_tests/`, `reviews/`, and `state/derived/reader_feedback.json`.
- Confirm high-explanation/low-scene-anchor samples make `style-check` return `NOT_READY`.
- Confirm `python scripts/novel.py series-style-check v01_c004` is documented as the post-warmup series-style evidence path.
- Confirm `python scripts/novel.py deepseek-style-review v01_c004 --dry-run` writes only a prompt when no live API call is intended.
- Confirm report commands do not dirty the worktree unless an explicit `--write` or landing command is used.

Explicit report writes are derived artifacts by default:

- `python scripts/novel.py audit --write-report` writes under `state/audit/`, which is ignored.
- `python scripts/novel.py long-health --write` writes under `state/derived/long_health/`, which is ignored.
- Chapter evidence artifacts such as `reviews/{chapter}/element_usage.json`, `reviews/{chapter}/fact_cards.json`, `reviews/{chapter}/style_metrics.json`, and `reviews/{chapter}/series_style.json` are part of the chapter workflow and may be tracked with the chapter.
- Reader/personality derived artifacts such as `state/derived/personality/protagonist.json`, `state/derived/protagonist_progression.json`, `state/derived/world_reveal_ledger.json`, and `state/derived/suspense_ledger.json` are regenerated from core freeze, brief, and event ledger.
