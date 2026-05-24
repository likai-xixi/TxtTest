# Command Return Codes

This template uses three command classes:

- Template quality commands return non-zero only for code, schema, or template integrity failures: `check`, `ci`, `self-test`, `workflow-smoke`.
- Informational commands return zero when they can produce a report, even if the project is not ready: `desk`, `status`, `idea-status`, `opening-status`, `pacing-dashboard`.
- Gate and workflow blocker commands return non-zero on `NOT_READY` / `BLOCKED`: `audit`, `opening-preflight`, `core-freeze-check`, `reader-promise-check --require-ready`, `reader-reward-check`, `reader-reward-index`, `reader-risk-index`, `prose-risk-check`, `prose-risk-index`, `reader-reward-migration-report`, `pilot-reader-experience`, `pilot-health`, `long-health`, `brief-precheck`, `brief-check`, `context-quality`, `review-context`, `reader-experience-check`, `ai-taste-check`, `dialogue-function-check`, `emotion-relationship-gate`, `semantic-reader-review`, `memorable-scene-check`, `deepseek-anti-ai-review`, `deepseek-semantic-reader-review`, `deepseek-manifest-check`, `review-arbitration`, `revision-plan`, `revision-closure`, `gray-consequence`, `chapter-shape-check`, `reader-feedback summarize`, `personality-check`, `suspense-check`, `world-reveal-check`, `protagonist-progression-check`, `style-check`, `series-style-check`, `evidence`, `gate-check`, `land`, `idea-agent-manifest`.

Shadow Memory commands follow the same write contract as the rest of the workflow. `shadow-build`, `shadow-route`, `shadow-check`, `shadow-diff`, and `shadow-audit` write nothing unless `--write` is present. `shadow-check` and `shadow-diff` return non-zero when shadow artifacts are missing, stale, malformed, or violate the `shadow_advisory_not_fact_source` boundary. `shadow-build --json` may return `READY` without writing files; it is a dry preview unless `--write` is supplied.

Ship evidence treats `shadow_memory` as an always-required gate once a chapter is being closed. Shadow artifacts can raise review route strength, but they cannot lower the route, satisfy Ship evidence, write canon, or write `state/event_ledger.jsonl`.

`series-style-check` returns zero for `READY`, `WARNING`, and `ACCEPTED_BY_HUMAN`, and non-zero for `NOT_READY`. Ship evidence interprets that more strictly: chapter 4-5 may accept `WARNING`, while chapter 6+ requires `READY` or `ACCEPTED_BY_HUMAN`.

`audit` is a project health exam. A copied but unopened template can pass `check` and `ci` while `audit --mode project` returns non-zero because story evidence is still missing.

`audit --mode template` runs `reader-promise-check` without `--require-ready`, so a fresh copied template may keep `state/project_reader_promise.json` in `DRAFT`. `go/start/write/deepseek-generate` require the same contract to be `READY`.

`reader-risk-index` returns zero for `READY` or `WARNING` and non-zero for `BLOCKED`. Ship evidence and release audit interpret `BLOCKED` as a hard stop; `WARNING` stays visible in `desk/status` and audit JSON.

`prose-risk-check` returns non-zero for `NOT_READY` or `BLOCKED`, and zero for `CLEAR` or `WARNING`. `prose-risk-index` returns zero for `READY` or `WARNING` and non-zero for `BLOCKED`; Ship evidence interprets `BLOCKED` as a hard stop.

`review-context --write` returns zero only when the review context is `READY`; stale or unanchored key quotes return non-zero. `codex-anti-ai-review-start` and `codex-semantic-reader-review-start` return zero after writing only the isolated Codex subagent prompt and manifest when the official chapter exists. `ai-taste-check`, `dialogue-function-check`, `emotion-relationship-gate`, `semantic-reader-review`, and `memorable-scene-check` return zero only for `CLEAR`; `semantic-reader-review` is now an aggregate gate and returns `NOT_READY` until both `codex_semantic_reader_review.md/json` and `deepseek_semantic_reader_review.md/json` exist and bind to the current official chapter. `deepseek-anti-ai-review --dry-run` and `deepseek-semantic-reader-review --dry-run` return zero after writing only the prompt and run manifest when the official chapter exists; missing official chapter text returns `status: NOT_READY` and non-zero. Live DeepSeek review commands return `2` when `DEEPSEEK_API_KEY` is missing. `migrate-anti-ai-reviews` returns zero when it creates or skips draft scaffolds; it never marks a review clear.

`receive-chapter --preview` returns zero and writes nothing. A live `receive-chapter` returns zero only when the receive control plane is ready; missing human decisions, DeepSeek review evidence, fact-card acceptance, review arbitration, or chapter anchors return non-zero with a next action.

`accept-review` returns zero only when it records a human acceptance for an allowed taste/style artifact. It refuses infrastructure failures such as schema errors, manifest/hash mismatch, quote mismatch, event-ledger gaps, unauthorized breakers, and continuity P0/P1.
