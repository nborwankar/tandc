# CLAUDE.md — tandc

**Conda env**: `tandc` (Python 3.11). Activate with
`PATH=/Users/nitin/anaconda3/envs/tandc/bin:$PATH ...`.

**Project**: Terms & Conditions risk analyzer. Pure library
(`tandc.core`) wrapped by a `typer` CLI (`tandc.cli`) and a FastAPI
local web UI (`tandc.web`). Pydantic v2 owns data shape. Anthropic
Claude is the analysis engine.

**Layout**: `src/tandc/` package, `tests/`, `docs/superpowers/{specs,plans}/`.
Runtime artefacts go to `./reports/` and `~/.tandc/cache/` (both
gitignored).

**Test runs**: every pytest invocation is logged per standing rule:
- Raw output → `docs/test_runs/YYYY-MM-DD_<desc>.txt` (gitignored — local only)
- Summary row → `docs/TEST_LOG.md` (tracked — counts/durations only, no stdout)

## ⚠️ CRITICAL: SECRETS-IN-LOGS DEFENSE

**Two layers of defense are in place. Do not weaken either.**

1. **`tests/conftest.py`** — the `_captured_real_key` fixture wraps the
   key in a `_RealKey` object whose `__repr__` returns `"<REDACTED>"`.
   Pytest `-v` cannot leak it. Consumers call `.value` to get the actual
   string. **Do not change the fixture to return a raw string.**
2. **`.gitignore`** — `docs/test_runs/*` is gitignored. Test-run raw
   output stays local. Only `docs/TEST_LOG.md` (counts/durations) is
   tracked. **Do not commit files under `docs/test_runs/` without an
   explicit reason and a manual `grep -iE 'sk-ant|sk-|AKIA|ghp_'` first.**

A `gitleaks` pre-commit hook was evaluated and dropped — the default
ruleset did not reliably catch Anthropic-format keys, and an unreliable
hook gives a false sense of security. If you want one, install and
verify it actually blocks a test commit before relying on it.

For the full rationale and a checklist applicable to any future Python
project, see `~/.claude/CLAUDE.md` → "⚠️ CRITICAL: NEVER Let Secrets
Leak Into Test Logs".

## CI (GitHub Actions)

`.github/workflows/test.yml` runs the 126 mocked-Claude unit tests
(`pytest -m "not slow"`) on Ubuntu / Python 3.11. The `-m slow`
6-vendor live-Claude smoke suite never runs in CI (needs a real API
key + costs ~$0.06 per run) — it stays local-only.

**Currently the workflow is manual-only.** Its trigger block is:

```yaml
on:
  workflow_dispatch: {}
```

To re-enable auto-triggers, replace the `on:` block with one or both:

```yaml
on:
  push:
    branches: [main]
  pull_request:
    branches: [main]
  workflow_dispatch: {}
```

Public-repo Actions minutes are free; cost concern is zero. The reason
it's manual-only is solo-dev ceremony reduction — `pytest -m "not slow"`
runs locally before each push, so auto-CI is redundant signal.

## Roadmap

See `PLAN.md`. Stage 1 v1 + v2 shipped; Stage 2 (Chrome extension)
brainstorm pending.

## Reference docs

- v1 spec: `docs/superpowers/specs/2026-05-18-stage1-paste-and-analyze-design.md`
- v1 plan: `docs/superpowers/plans/2026-05-20-stage1-paste-and-analyze.md`
- v2 spec: `docs/superpowers/specs/2026-05-21-stage1-v2-web-ui-design.md`
- v2 plan: `docs/superpowers/plans/2026-05-21-stage1-v2-web-ui.md`
