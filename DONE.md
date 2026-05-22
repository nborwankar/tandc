# DONE — tandc

## Stage 1 v1 — CLI

Shipped 2026-05-20. `tandc analyze <URL|->` produces a structured risk
report from any T&C / privacy policy via the Anthropic Claude API.
Flags: `--opus`, `--no-cache`, `--output-dir`, `--json`, `--debug`.
`tandc cache list / clear` for cache management.

- Engine: Claude Sonnet 4.6 (default) / Opus 4.7 (`--opus`),
  system-prompt caching enabled.
- Taxonomy v1: Core 4 categories (personal_data, pii_protection,
  continuity, liability_dispute) with severity + verbatim evidence
  quotes; Flag 4 (content_licensing, account_access,
  payment_subscription, jurisdictional) with presence + note.
- Inputs v1: URL (httpx + trafilatura) and stdin paste.
- Storage v1: content-hash file cache at `~/.tandc/cache/`; per-run
  artefacts at `./reports/<slug>-<date>/{input.txt, fetch_meta.json,
  report.json, report.md}`.
- Tests: 88 unit (mocked Claude) + 6-vendor live smoke (gated by
  `@pytest.mark.slow`).

## Stage 1 v2 — local web UI

Shipped 2026-05-21. `tandc serve` (default `127.0.0.1:8765`) exposes
a vanilla-JS form at `/` and a single `POST /analyze` JSON endpoint
backed by the same `tandc.core` library.

- Inputs: URL, paste, file upload (HTML / TXT / PDF via pypdf).
- Errors mapped to HTTP codes (400 extraction, 415 unsupported MIME,
  422 validation, 500 analysis, 502 fetch, 503 missing API key).
- CLI launcher: `./scripts/serve.sh` handles conda PATH + API-key
  pre-flight (exit 4 if missing, exit 5 if port in use).
- Same `./reports/<slug>-<date>/` bundle as the CLI.
- Tests: 126 unit total (88 v1 + 38 v2 web layer), all mocked Claude.

## Next

Stage 2 — Chrome extension. Decision pending: fresh extension that
calls `localhost:8765/analyze`, vs extending Claude for Chrome. The
v2 `POST /analyze` endpoint is the backend either way; no new
backend work is needed.
