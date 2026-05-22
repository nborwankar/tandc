# CLAUDE.md — tandc

**Conda env**: `tandc` (Python 3.11). Activate with
`PATH=/Users/nitin/anaconda3/envs/tandc/bin:$PATH ...`.

**Project**: Terms & Conditions risk analyzer. Pure library
(`tandc.core`) wrapped by a `typer` CLI (`tandc.cli`). Pydantic v2
owns data shape. Anthropic Claude is the analysis engine.

**Layout**: `src/tandc/` package, `tests/`, `docs/superpowers/{specs,plans}/`.
Runtime artefacts go to `./reports/` and `~/.tandc/cache/` (both
gitignored).

**Test runs**: every pytest invocation is logged per standing rule:
- Raw output → `docs/test_runs/YYYY-MM-DD_<desc>.txt` (gitignored — local only)
- Summary row → `docs/TEST_LOG.md` (tracked — counts/durations only, no stdout)

## ⚠️ CRITICAL: SECRETS-IN-LOGS DEFENSE (incident 2026-05-21)

**This project leaked the real `ANTHROPIC_API_KEY` into committed test-run logs via a pytest fixture.** Caught pre-publish; key rotated in Anthropic Console; entire `.git` deleted and the repo rebuilt from scratch without the leaked content (no public push ever occurred). **Two layers of defense are in place and must stay in place:**

1. **`tests/conftest.py`** — the `_captured_real_key` fixture wraps the key in a `_RealKey` object whose `__repr__` returns `"<REDACTED>"`. Pytest -v cannot leak it. Consumers call `.value` to get the actual string. **Do not change the fixture to return a raw string.**
2. **`.gitignore`** — `docs/test_runs/` is gitignored. Test-run raw output stays local. Only `docs/TEST_LOG.md` (counts/durations) is tracked. **Do not commit files under `docs/test_runs/` without an explicit reason and a manual `grep -i 'sk-ant\|sk-\|AKIA'` first.**

A third layer (`gitleaks` pre-commit hook) was evaluated and dropped — the default ruleset didn't reliably catch Anthropic-format keys in our verification, and an unreliable hook gives a false sense of security. If you want a secret-scanning hook, install one separately (e.g. `pre-commit` with a custom regex, or `gitleaks` with a tuned `.gitleaks.toml`) and verify it actually blocks a test commit before relying on it.

If you ever modify the conftest fixture or the `.gitignore` `test_runs/` rule: re-read the global rule at `~/.claude/CLAUDE.md` → "⚠️ CRITICAL: NEVER Let Secrets Leak Into Test Logs".

## CI (GitHub Actions)

`.github/workflows/test.yml` runs the 126 mocked-Claude unit tests (`pytest -m "not slow"`) on Ubuntu / Python 3.11. The `-m slow` 6-vendor live-Claude smoke suite never runs in CI (needs a real API key + costs ~$0.06 per run) — it stays local-only.

**Currently the workflow is manual-only** — its trigger block is just:

```yaml
on:
  workflow_dispatch: {}
```

That means pushes and PRs do NOT auto-run tests. To re-enable auto-triggers, replace the `on:` block with one or both of these:

```yaml
# Auto-run on every push to main:
on:
  push:
    branches: [main]
  workflow_dispatch: {}

# Or auto-run on PRs to main (best when others may contribute):
on:
  pull_request:
    branches: [main]
  workflow_dispatch: {}

# Or both:
on:
  push:
    branches: [main]
  pull_request:
    branches: [main]
  workflow_dispatch: {}
```

Public-repo Actions minutes are free; cost concern is zero. The reason it's manual-only is solo-dev ceremony reduction — the operator (you) runs `pytest -m "not slow"` locally before each push, so auto-CI is redundant signal.

**Roadmap**: see `PLAN.md`.

**Shipped**:
- Stage 1 v1 (CLI) — 2026-05-20, merged to `main` at `e2cd027`.
- Stage 1 v2 (local web UI) — 2026-05-21, merged to `main` at
  `99c7710`. `tandc serve` → `http://127.0.0.1:8765`. Single
  `POST /analyze` JSON endpoint serves both the web form and the
  future Stage 2 Chrome extension. Recommended launcher:
  `./scripts/serve.sh` (handles conda PATH + API-key precheck).

**Active**:
- Stage 2 brainstorm — fresh Chrome extension vs extend Claude for
  Chrome. Backend already done (v2 `POST /analyze`).

**Reference docs (historical)**:
- v1 spec: `docs/superpowers/specs/2026-05-18-stage1-paste-and-analyze-design.md`
- v1 plan: `docs/superpowers/plans/2026-05-20-stage1-paste-and-analyze.md`
- v2 spec: `docs/superpowers/specs/2026-05-21-stage1-v2-web-ui-design.md`
- v2 plan: `docs/superpowers/plans/2026-05-21-stage1-v2-web-ui.md`
