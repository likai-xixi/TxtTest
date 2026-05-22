# Release Checklist

Before publishing or copying this template:

- Run `python -B -m compileall -q scripts tests` with `PYTHONDONTWRITEBYTECODE=1` in the environment.
- Run `python scripts/novel.py check`.
- Run `python scripts/novel.py self-test` with a 10 minute timeout budget.
- Run `python scripts/novel.py workflow-smoke`.
- Run `python scripts/novel.py ci` with a 10 minute timeout budget.
- Run `python scripts/novel.py longrun-smoke --chapters 10`.
- Run `python scripts/novel.py audit --mode template`.
- Capture `python scripts/novel.py audit --mode release --json`; an unopened template should be `NOT_READY` because of expected story blockers, never `ERROR`.
- Confirm `reader-promise-check` returns `NOT_READY` until the project manually declares `reader_reward_intensity_policy`; no template default R档 is inferred.
- Confirm `reader-promise-check --require-ready` rejects missing Reader Promise v2 fields, placeholder arrays, and empty release/agency/language/efficiency policies.
- Confirm `new-chapter` scaffolds opening/personality/retention/charm/world/suspense/language/genre review files plus `ai_taste.md/json`, `dialogue_function.md/json`, `codex_anti_ai_review.md/json`, `deepseek_anti_ai_review.md/json`, `codex_semantic_reader_review.md/json`, `deepseek_semantic_reader_review.md/json`, and `semantic_reader_review.md/json`.
- Confirm `new-chapter` and `record_idea_selection` produce `schema_version: 2` briefs with `Story Card` first and `Machine Contract Appendix` second.
- Confirm v1 legacy briefs still pass the compatibility path, while v2 `brief-check` blocks missing `Story Card.before -> after` and missing `reader_reward_intensity`.
- Confirm `deepseek-brief --dry-run` emits a v2 brief prompt and `codex-draft-prompt` sends `Story Card + Hard Boundaries`, not the old long audit contract list.
- Confirm `new-chapter` also scaffolds `revision_plan`, `review_arbitration`, `gray_consequence`, `chapter_shape`, `reader_reward_gate`, `reader_feedback`, and `receive_chapter` Markdown/JSON artifacts.
- Confirm `receive-chapter --preview` writes nothing and lists the full control-plane sequence, including `reader-risk-index` before `chapter-evidence`.
- Confirm `revision-plan`, `review-arbitration`, `gray-consequence`, `chapter-shape-check`, `reader-reward-check`, `reader-reward-index`, `reader-risk-index`, `long-health`, and `reader-feedback summarize --no-write` return `NOT_READY`/`BLOCKED` cleanly on an unopened template, not tracebacks.
- Confirm `deepseek-manifest-check` rejects missing, stale, and forbidden-input DeepSeek run manifests.
- Confirm `accept-review` writes current human metadata and rejects infrastructure blockers.
- Confirm `chapter-evidence` rejects missing, stale, quote-less, or `BLOCKED` auxiliary reviews unless `ACCEPTED_BY_HUMAN` is bound to the current official chapter hash and current review body hash.
- Confirm `chapter-evidence` rejects missing, stale, malformed, or contaminated review context at `state/context_pack/{chapter}_review_context.md/json`, and that the review context does not include previous chapters as full text.
- Confirm `chapter-evidence` rejects missing, stale, quote-less, or `BLOCKED` `reader_reward_gate.json/md`, rejects stale `reader_reward_index.json`, and rejects missing/stale/`BLOCKED` `state/derived/reader_risk/latest.json`.
- Confirm `reader-reward-check` blocks R2+ chapters with no matched reward quote, v2 chapters with no matched protagonist action, and v2 world rules that only explain instead of being tested in scene.
- Confirm `reader-risk-index --to v01_c006 --write --json` can BLOCK all 8 reader risk categories on synthetic bad chapters: pace, repetition, suspense, protagonist, worldview, perspective, language, and structural efficiency.
- Confirm `reader-feedback add` requires answers for next-click intent, memorable moment, frustration, protagonist charm, author-explanation feel, and suspense expectation/fatigue unless explicitly recorded as incomplete.
- Confirm `pacing-check` blocks a 3-chapter window with no effective progress.
- Confirm `chapter-shape-check` treats repeated shape as warmup warning for chapters 1-3 and as BLOCKED from chapter 6.
- Confirm `pilot-reader-experience A --write` returns NOT_READY/BLOCKED when the first three chapters lack small payoff, protagonist active choice, or world-rule scene testing.
- Confirm `pilot-reader-experience A --write` only recommends `continue` when protagonist establishment, next-read reason, world anomaly differentiation, reader-promise delivery, and 100-chapter fun sustainability are all proven.
- Confirm `long-health --to v01_c010 --write` outputs a 5-chapter rolling health window and marks fatigue risks; chapter 10+ evidence must reject BLOCKED long-health.
- Confirm `pilot-reader-experience` and `long-health` ignore non-human event-ledger entries and reject stale `reader_reward_gate` / `chapter_shape` inputs.
- Confirm `ai-taste-check`, `dialogue-function-check`, and `deepseek-anti-ai-review --dry-run` produce `NOT_READY`, not `ERROR`, when a copied template has no official chapter yet.
- Confirm `migrate-anti-ai-reviews` creates draft scaffolds without overwriting existing human review files and without marking anything `CLEAR`.
- Confirm `python scripts/novel.py codex-anti-ai-review-start v01_c001` writes only the isolated prompt and manifest, and never writes final `codex_anti_ai_review.md/json`.
- Confirm `chapter-evidence` rejects missing, stale, quote-less, malformed, or `BLOCKED` `codex_anti_ai_review.md/json`.
- Confirm `chapter-evidence` rejects missing, stale, quote-less, malformed, or `BLOCKED` `deepseek_anti_ai_review.md/json`.
- Confirm `python scripts/novel.py codex-semantic-reader-review-start v01_c001` writes only the isolated prompt and manifest, and never writes final `codex_semantic_reader_review.md/json`.
- Confirm `python scripts/novel.py semantic-reader-review v01_c001 --write` returns `NOT_READY` until both Codex and DeepSeek semantic LLM source reviews exist.
- Confirm `chapter-evidence` rejects missing, stale, quote-less, malformed, contaminated, or `BLOCKED` `codex_semantic_reader_review.md/json`, `deepseek_semantic_reader_review.md/json`, and the DeepSeek `semantic_reader_review` run manifest.
- Confirm `python scripts/novel.py deepseek-anti-ai-review v01_c001 --dry-run` does not write final review files and its prompt excludes Codex review outputs.
- Confirm `python scripts/novel.py deepseek-semantic-reader-review v01_c001 --dry-run` does not write final review files and its prompt excludes Codex semantic/review outputs.
- Confirm DeepSeek review, anti-AI review, semantic reader review, and style review dry runs write only prompt/run manifest evidence and never final review artifacts.
- Confirm high-impact gray behavior without fact-card/event coverage blocks `gray-consequence`.
- Confirm chapter 6+ repeated shape blocks `chapter-shape-check`.
- Confirm per-chapter reader feedback writes only `reader_tests/`, `reviews/`, and `state/derived/reader_feedback.json`.
- Confirm `desk --write-report --html` writes `state/audit/dashboard.md/html` with reader risk, long-health, suspense debt, shape repetition, agency/release-valve signals, and Gate countdown.
- Confirm high-explanation/low-scene-anchor samples make `style-check` return `NOT_READY`.
- Confirm `python scripts/novel.py series-style-check v01_c004` is documented as the post-warmup series-style evidence path.
- Confirm `python scripts/novel.py deepseek-style-review v01_c004 --dry-run` writes only a prompt when no live API call is intended.
- Confirm report commands do not dirty the worktree unless an explicit `--write` or landing command is used.

Explicit report writes are derived artifacts by default:

- `python scripts/novel.py audit --write-report` writes under `state/audit/`, which is ignored.
- `python scripts/novel.py long-health --write` writes under `state/derived/long_health/`, which is ignored.
- `python scripts/novel.py reader-risk-index --write` writes under `state/derived/reader_risk/`, which is ignored.
- `python scripts/novel.py desk --write-report --html` writes under `state/audit/`, which is ignored.
- Chapter evidence artifacts such as `reviews/{chapter}/element_usage.json`, `reviews/{chapter}/fact_cards.json`, `reviews/{chapter}/style_metrics.json`, and `reviews/{chapter}/series_style.json` are part of the chapter workflow and may be tracked with the chapter.
- Reader/personality derived artifacts such as `state/derived/personality/protagonist.json`, `state/derived/protagonist_progression.json`, `state/derived/world_reveal_ledger.json`, and `state/derived/suspense_ledger.json` are regenerated from core freeze, brief, and event ledger.
