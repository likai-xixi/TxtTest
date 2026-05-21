# Command Return Codes

This template uses three command classes:

- Template quality commands return non-zero only for code, schema, or template integrity failures: `check`, `ci`, `self-test`, `workflow-smoke`.
- Informational commands return zero when they can produce a report, even if the project is not ready: `desk`, `status`, `idea-status`, `opening-status`, `pacing-dashboard`, `long-health`.
- Gate and workflow blocker commands return non-zero on `NOT_READY` / `BLOCKED`: `audit`, `core-freeze-check`, `reader-promise-check --require-ready`, `reader-reward-check`, `reader-reward-index`, `reader-reward-migration-report`, `brief-precheck`, `brief-check`, `context-quality`, `review-context`, `reader-experience-check`, `ai-taste-check`, `dialogue-function-check`, `deepseek-anti-ai-review`, `deepseek-manifest-check`, `review-arbitration`, `revision-plan`, `gray-consequence`, `chapter-shape-check`, `reader-feedback summarize`, `personality-check`, `suspense-check`, `world-reveal-check`, `protagonist-progression-check`, `style-check`, `series-style-check`, `evidence`, `gate-check`, `land`, `idea-agent-manifest`.

`series-style-check` returns zero for `READY`, `WARNING`, and `ACCEPTED_BY_HUMAN`, and non-zero for `NOT_READY`. Ship evidence interprets that more strictly: chapter 4-5 may accept `WARNING`, while chapter 6+ requires `READY` or `ACCEPTED_BY_HUMAN`.

`audit` is a project health exam. A copied but unopened template can pass `check` and `ci` while `audit --mode project` returns non-zero because story evidence is still missing.

`audit --mode template` runs `reader-promise-check` without `--require-ready`, so a fresh copied template may keep `state/project_reader_promise.json` in `DRAFT`. `go/start/write/deepseek-generate` require the same contract to be `READY`.

`review-context --write` returns zero only when the review context is `READY`; stale or unanchored key quotes return non-zero. `codex-anti-ai-review-start` returns zero after writing only the isolated Codex subagent prompt and manifest when the official chapter exists. `ai-taste-check` and `dialogue-function-check` return zero only for `CLEAR`. `deepseek-anti-ai-review --dry-run` returns zero after writing only the prompt when the official chapter exists; missing official chapter text returns `status: NOT_READY` and non-zero. Live `deepseek-anti-ai-review` returns `2` when `DEEPSEEK_API_KEY` is missing. `migrate-anti-ai-reviews` returns zero when it creates or skips draft scaffolds; it never marks a review clear.

`receive-chapter --preview` returns zero and writes nothing. A live `receive-chapter` returns zero only when the receive control plane is ready; missing human decisions, DeepSeek review evidence, fact-card acceptance, review arbitration, or chapter anchors return non-zero with a next action.

`accept-review` returns zero only when it records a human acceptance for an allowed taste/style artifact. It refuses infrastructure failures such as schema errors, manifest/hash mismatch, quote mismatch, event-ledger gaps, unauthorized breakers, and continuity P0/P1.
