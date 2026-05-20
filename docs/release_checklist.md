# Release Checklist

Before publishing or copying this template:

- Run `python -m compileall scripts tests`.
- Run `python scripts/novel.py check`.
- Run `python scripts/novel.py self-test`.
- Run `python scripts/novel.py workflow-smoke`.
- Run `python scripts/novel.py ci`.
- Run `python scripts/novel.py longrun-smoke --chapters 10`.
- Confirm `python scripts/novel.py series-style-check v01_c004` is documented as the post-warmup series-style evidence path.
- Confirm `python scripts/novel.py deepseek-style-review v01_c004 --dry-run` writes only a prompt when no live API call is intended.
- Confirm report commands do not dirty the worktree unless an explicit `--write` or landing command is used.

Explicit report writes are derived artifacts by default:

- `python scripts/novel.py audit --write-report` writes under `state/audit/`, which is ignored.
- `python scripts/novel.py long-health --write` writes under `state/derived/long_health/`, which is ignored.
- Chapter evidence artifacts such as `reviews/{chapter}/element_usage.json`, `reviews/{chapter}/fact_cards.json`, `reviews/{chapter}/style_metrics.json`, and `reviews/{chapter}/series_style.json` are part of the chapter workflow and may be tracked with the chapter.
