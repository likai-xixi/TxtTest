# Command Return Codes

This template uses three command classes:

- Template quality commands return non-zero only for code, schema, or template integrity failures: `check`, `ci`, `self-test`, `workflow-smoke`.
- Informational commands return zero when they can produce a report, even if the project is not ready: `desk`, `status`, `idea-status`, `opening-status`, `pacing-dashboard`, `long-health`.
- Gate and workflow blocker commands return non-zero on `NOT_READY` / `BLOCKED`: `audit`, `core-freeze-check`, `brief-precheck`, `brief-check`, `context-quality`, `style-check`, `series-style-check`, `evidence`, `gate-check`, `land`, `idea-agent-manifest`.

`series-style-check` returns zero for `READY`, `WARNING`, and `ACCEPTED_BY_HUMAN`, and non-zero for `NOT_READY`. Ship evidence interprets that more strictly: chapter 4-5 may accept `WARNING`, while chapter 6+ requires `READY` or `ACCEPTED_BY_HUMAN`.

`audit` is a project health exam. A copied but unopened template can pass `check` and `ci` while `audit --mode project` returns non-zero because story evidence is still missing.
