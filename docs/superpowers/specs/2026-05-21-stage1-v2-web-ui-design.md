# Stage 1 v2 — Local Web UI (`tandc serve`) Design Spec

**Project**: `tandc` — Terms & Conditions Risk Analyzer
**Stage**: 1 (Paste-and-Analyze)
**Surface variant**: v2 — local web UI (adds to v1 CLI)
**Engine variant**: v1 — Anthropic Claude API (unchanged)
**Taxonomy variant**: v1 — Core 4 + Flag 4 (unchanged)
**Inputs variant**: web-only, ahead of CLI — URL + paste + file upload (HTML / TXT / PDF)
**Store variant**: v1 — file cache + per-run report dir (unchanged)
**Date**: 2026-05-21
**Status**: Design — awaiting user review
**Precedes**: Stage 2 — Chrome extension (which consumes the same JSON API)

---

## 1. Goal

Wrap the existing `tandc.core.analyze()` pipeline in a local single-page
web UI so a user can:

1. Open `http://localhost:8765/` in a browser
2. Submit a URL, pasted text, or an uploaded file (HTML, TXT, PDF)
3. See the same risk report the CLI produces, rendered inline as
   HTML with severity colours and expandable evidence quotes

The same `POST /analyze` endpoint is the backend the Stage 2 Chrome
extension will call. Building v2 also unblocks Stage 2's analysis
needs; Stage 2 becomes a Chrome UI on top of this JSON contract.

## 2. Non-goals (out of scope for Stage 1 v2)

- Remote / multi-user deployment. `tandc serve` binds to `127.0.0.1`
  by default; running on a public interface is opt-in via `--host`.
- Authentication. Localhost-only means trust-by-default.
- History / library / cross-doc comparison (Stage 3).
- Batch / multi-doc dashboard (Stage 4).
- WebSocket / streaming. Analysis is a single request → single
  response, ~10–30 s end-to-end.
- A real frontend framework (React, Vue, etc.). Vanilla JS only.
- A build step (Webpack, Vite). Static files served as-is.
- Per-user accounts or settings.

## 3. Architecture

```
              ┌─────────────────────────────────────┐
              │  browser tab @ 127.0.0.1:8765       │
              │  ┌─────────────────────────────┐    │
              │  │ GET / → static HTML + JS    │    │
              │  │ form: URL / paste / file    │    │
              │  └──────────────┬──────────────┘    │
              └─────────────────┼───────────────────┘
                                │ fetch()
                                ▼ POST /analyze
              ┌─────────────────────────────────────┐
              │  FastAPI  (tandc.web.app)           │
              │                                     │
              │  POST /analyze  (api.py)            │
              │  GET  /         (static index.html) │
              │  GET  /static/* (css/js)            │
              │  GET  /docs     (OpenAPI auto)      │
              └─────────────────┬───────────────────┘
                                │
              ┌─────────────────▼───────────────────┐
              │  tandc.core.analyze()  (unchanged)  │
              │  loader → cache → analyzer → render │
              └─────────────────────────────────────┘

(Stage 2 Chrome extension reuses POST /analyze with
 {"text": "...", "source_url": "..."} bodies.)
```

`tandc.core` is untouched. v2 only adds the `tandc.web.*` package
and a `tandc serve` CLI subcommand. The web layer is a thin
adapter: parse the request → call `analyze()` → return the
`AnalysisReport` as JSON.

The web mode writes the same `./reports/<slug>-<date>/` bundle the
CLI does. Localhost-only means the server's CWD is the user's CWD;
the bundle lands where the user expects. The UI surfaces a
clickable `file://` link to the directory.

## 4. Components

```
src/tandc/
├── core/                       # unchanged
├── cli.py                      # add `serve` subcommand
└── web/                        # NEW package
    ├── __init__.py
    ├── app.py                  # FastAPI app + route mounts + lifespan
    ├── api.py                  # POST /analyze + Pydantic request models
    ├── pdf.py                  # PDF → text via pypdf
    ├── serve.py                # uvicorn launcher (called from cli.serve)
    └── static/
        ├── index.html          # the single form page
        ├── tandc.css           # ~80 lines, no framework
        └── tandc.js            # vanilla JS: fetch() + render
tests/web/
├── test_api.py                 # FastAPI TestClient against POST /analyze
├── test_pdf.py                 # PDF extraction unit test
└── fixtures/sample.pdf         # tiny PDF for the PDF path
```

| Module | Responsibility | Depends on |
|--------|----------------|------------|
| `cli.py` (mod) | Add `serve` command, hand off to `web.serve` | `web.serve` |
| `web/app.py` | Create FastAPI app, mount static, mount api router | `fastapi`, `web.api` |
| `web/api.py` | Parse request → dispatch to `core.analyze()` → return JSON; map errors to HTTP codes | `core`, `web.pdf`, `errors` |
| `web/pdf.py` | `extract_pdf(bytes) -> str` using pypdf, with normalisation via `core.extract._normalise_text` | `pypdf`, `core.extract` |
| `web/serve.py` | Wrap uvicorn launch; resolve host/port/reload | `uvicorn`, `web.app` |
| `web/static/index.html` | Single page: form + result container | — |
| `web/static/tandc.css` | Severity colour scheme matching terminal renderer | — |
| `web/static/tandc.js` | Form submit → fetch → render result; vanilla, ~120 LOC | — |

## 5. API contract

### `POST /analyze`

Accepts three input shapes via the same endpoint. FastAPI dispatches
on `Content-Type`.

**URL mode** — `Content-Type: application/json`:

```json
{
  "url": "https://example.com/terms",
  "model": "sonnet",
  "use_cache": true
}
```

**Paste / Chrome-extension mode** — `Content-Type: application/json`:

```json
{
  "text": "<pasted policy text>",
  "source_url": "https://example.com/terms",
  "model": "sonnet",
  "use_cache": true
}
```

`source_url` is optional metadata only; it does not trigger a fetch.

**File upload mode** — `Content-Type: multipart/form-data`:

```
file=<binary>; filename="terms.pdf"
model=sonnet
use_cache=true
```

File MIME type drives the extractor:
- `text/html` → trafilatura via `core.extract.extract_text`
- `text/plain` → as-is, normalised via `core.extract._normalise_text`
- `application/pdf` → `web.pdf.extract_pdf`

All other MIME types → `415 Unsupported Media Type`.

### Request validation

`model` ∈ `{"sonnet", "opus"}`, default `"sonnet"`. Maps to
`MODEL_SONNET` / `MODEL_OPUS` from `core.analyzer`.

`use_cache` ∈ `{true, false}`, default `true`.

Exactly one of `url`, `text`, or `file` must be provided. Pydantic
discriminates by which field is set; FastAPI uses a request-model
validator that returns `422` with a clear error if zero or two+ are
present.

### Response

`200 OK`:

```json
{
  "report": { /* full AnalysisReport, same as core/schema.py */ },
  "report_dir": "/Users/nitin/Projects/dirs/github/tandc/reports/openai-com-terms-2026-05-21",
  "cache_hit": false
}
```

`report_dir` is the absolute path to the written `./reports/<slug>-<date>/`
directory (same artefacts the CLI writes: input.txt, fetch_meta.json,
report.json, report.md). The UI renders this as a clickable
`file://` link.

### Error responses

All errors return JSON:

```json
{
  "error": "TandcFetchError",
  "message": "fetch failed for https://... (status=404): HTTP 404",
  "detail": {"url": "https://...", "status": 404}
}
```

| Exception | HTTP code | When |
|-----------|-----------|------|
| `TandcExtractionError` | 400 | input could not be extracted (empty body, stdin empty, PDF text empty) |
| pydantic ValidationError on request | 422 | request body missing required field, wrong type, mutually exclusive fields both set |
| Unsupported file MIME | 415 | file upload not HTML / TXT / PDF |
| `TandcConfigError` | 503 | `ANTHROPIC_API_KEY` not set on the server |
| `TandcAnalysisError` | 500 | Claude returned malformed output twice |
| `TandcFetchError` | 502 | upstream URL fetch failed (DNS, timeout, 4xx, 5xx) |
| Catch-all `TandcError` | 500 | future error subclass — JSON error body, no stack trace |

## 6. Frontend layout

Single page, ~100 LOC HTML + ~80 LOC CSS + ~120 LOC vanilla JS.

```
┌─────────────────────────────────────────────────────────┐
│  tandc — Terms & Conditions risk analyzer               │
├─────────────────────────────────────────────────────────┤
│  Input:                                                 │
│   ( ) URL    [ https://example.com/terms          ]     │
│   ( ) Paste  [ textarea                          ]      │
│   ( ) File   [ Choose file: terms.pdf ]                 │
│                                                         │
│   [x] use cache    Model: ( ) Sonnet  ( ) Opus          │
│                                                         │
│                              [  Analyze  ]              │
├─────────────────────────────────────────────────────────┤
│  ── result (after submit) ──                            │
│                                                         │
│  HEADLINE: Service uses arbitration and trains on...    │
│  Overall risk: HIGH    Model: claude-sonnet-4-6         │
│  Wrote: file:///.../reports/openai-com-terms-2026-05-21 │
│                                                         │
│  Core findings                                          │
│  ┌──────────────────┬──────────┬───────────────────┐    │
│  │ personal_data    │ HIGH     │ summary + why     │    │
│  │ pii_protection   │ MEDIUM   │ ...               │    │
│  │ continuity       │ HIGH     │ ...               │    │
│  │ liability_dispute│ CRITICAL │ ...               │    │
│  └──────────────────┴──────────┴───────────────────┘    │
│  Each row expandable → shows verbatim evidence quotes   │
│                                                         │
│  Flags (4 chips)  [content_licensing: present] ...      │
└─────────────────────────────────────────────────────────┘
```

### JS behaviour

- Listen to form submit, prevent default.
- Read selected input mode (radio buttons).
- For URL / paste: build JSON body, `fetch('/analyze', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(...)})`.
- For file: build `FormData`, POST without explicit `Content-Type` (browser sets multipart).
- While waiting: show "Analyzing… (~30 s)" placeholder; disable submit button.
- On 200: render the AnalysisReport into the result container.
- On non-200: parse JSON error body, show red banner with `error` and `message`.
- Severity colours match the terminal renderer: green / yellow / red / bold red.

### CSS

No framework. Severity colours via CSS custom properties so the
palette is centralised. Mobile not optimised (out of scope —
localhost on laptop).

### Accessibility

- All form controls have associated `<label>`.
- Result rendering uses semantic HTML (`<table>`, `<details>` for
  expandable evidence).
- Severity is conveyed by both colour AND text (`HIGH`), not colour
  alone.

## 7. CLI surface additions

```
tandc serve [--host 127.0.0.1] [--port 8765] [--reload]
```

| Flag | Default | Meaning |
|------|---------|---------|
| `--host` | `127.0.0.1` | Bind address. Explicit opt-in for `0.0.0.0`. |
| `--port` | `8765` | Listen port. |
| `--reload` | `False` | Uvicorn auto-reload (development). |

Prints `tandc serve listening on http://127.0.0.1:8765` and then
runs until SIGINT.

Pre-flight check: refuse to start if `ANTHROPIC_API_KEY` is not set,
with exit code 4 (matches CLI's `TandcConfigError` mapping). Avoids
the bad UX of "form submits, you wait 30 s, get a 503".

Exit codes:

| Code | Meaning |
|------|---------|
| `0` | Clean shutdown |
| `4` | `ANTHROPIC_API_KEY` missing |
| `5` | Port already in use |

## 8. Error handling

Standing "no silent exception swallowing" rule still applies inside
`web.api` and `web.pdf`. The HTTP layer wraps `Tandc*` exceptions
into JSON error bodies via a FastAPI exception handler (one handler
per class, plus a catch-all for `TandcError`). The exception
handler logs the full exception at WARNING; the response body
contains the message but not the full traceback.

PDF parse failures (`pypdf.errors.PdfReadError` and friends) map to
`TandcExtractionError` so they get the same 400 treatment.

## 9. Testing

### Unit tests (fast, mock Claude)

- `tests/web/test_api.py` — FastAPI `TestClient`:
  - URL mode: mocks `core.analyze`, asserts response.json contains
    `report`, `report_dir`, `cache_hit`.
  - Paste mode: same.
  - File upload: HTML, TXT, PDF (uses fixture PDF) → correct
    extraction, correct call to `core.analyze` with extracted text.
  - All five error mappings → correct HTTP status + JSON body.
  - Mutually exclusive input fields → 422.
  - Unsupported MIME → 415.
  - `model=opus`, `use_cache=false` query / body params thread through.
- `tests/web/test_pdf.py` — `extract_pdf(bytes)` extracts known
  text from `tests/web/fixtures/sample.pdf`; raises
  `TandcExtractionError` on empty / corrupt PDF.

### No browser / Playwright tests

Vanilla JS, ~120 LOC. API tests give us confidence the server is
right; manual smoke during T14-equivalent verifies the JS renders.
Add Playwright later if the JS surface grows.

### No new slow tests

Smoke suite stays at the analyzer layer (mocked HTTP, real Claude).
Web layer is HTTP plumbing; mocked-`core.analyze` tests are enough.

## 10. Tech stack additions

| Package | Why |
|---------|-----|
| `fastapi` | Pydantic v2-native, auto OpenAPI at `/docs`, async-ready |
| `uvicorn[standard]` | ASGI server with websockets / httptools / uvloop |
| `pypdf` | PDF extraction, pure-Python, MIT |
| `python-multipart` | required by FastAPI for `multipart/form-data` |
| `httpx` | (already installed) used by FastAPI's `TestClient` |

## 11. Project layout changes

```
tandc/
├── ... (unchanged)
├── src/tandc/
│   ├── ... (unchanged)
│   ├── cli.py             # MODIFIED: + serve command
│   └── web/               # NEW
│       ├── __init__.py
│       ├── app.py
│       ├── api.py
│       ├── pdf.py
│       ├── serve.py
│       └── static/
│           ├── index.html
│           ├── tandc.css
│           └── tandc.js
└── tests/
    ├── ... (unchanged)
    └── web/               # NEW
        ├── __init__.py
        ├── test_api.py
        ├── test_pdf.py
        └── fixtures/
            └── sample.pdf
```

## 12. Open questions deferred to implementation

These are intentionally not pinned in the spec because they don't
affect architecture:

- Exact CSS palette (greens/yellows/reds — pick on first render).
- Whether the result section uses `<details>` for evidence
  collapsibles or always-visible — try collapsed default.
- Whether to show `analyzed_at` and `taxonomy_version` in the UI
  (probably yes, as small dimmed metadata).

## 13. Success criteria for Stage 1 v2

1. `tandc serve` starts on default port; refuses if no API key.
2. `GET /` returns the form page; `GET /docs` shows the
   FastAPI-generated API docs.
3. `POST /analyze` with each of the three modes (URL, paste, file)
   returns an `AnalysisReport` JSON and writes
   `./reports/<slug>-<date>/` exactly as the CLI does.
4. PDF upload of a fixture PDF produces a non-empty extraction and
   a valid AnalysisReport (via Claude — verified in slow test or
   manual e2e).
5. All five `Tandc*` errors map to the documented HTTP codes with a
   JSON body.
6. Browser form submission for URL + paste paths produces a
   rendered report inline within ~30 s (live Claude); cache-hit
   second submission renders in < 1 s.
7. Unit tests pass with no live API calls; slow smoke test
   unchanged.

Once these seven are green, Stage 1 v2 is done.

---

## Appendix A — Roadmap dimensions

| Dimension | v1 (shipped) | v2 (this spec) | v3 (later) |
|-----------|--------------|----------------|------------|
| Product stage | Paste-and-analyze CLI | + local web UI | Stage 2: Chrome extension |
| Engine | Claude API | Claude API | Hybrid (rules + Claude) |
| Surface | CLI | + web UI on localhost | + Chrome extension |
| Taxonomy | Core 4 + Flag 4 | Core 4 + Flag 4 | Comprehensive (all 8 full) |
| Inputs | URL + stdin | + file upload (HTML/TXT/PDF) — web only | CLI also gets file |
| Store | File cache + report dir | unchanged | SQLite at `~/.tandc/tandc.db` |

The Inputs row shows web getting ahead of CLI on file support. This
divergence is acknowledged; if it proves annoying, the CLI's
Inputs v2 can land next.

## Appendix B — Stage 2 link

Stage 2 (Chrome extension) is unblocked by this spec because the
`POST /analyze` endpoint already accepts `{"text": "...",
"source_url": "..."}` — exactly what the extension will send after
it scrapes the policy text from the DOM. Stage 2's scope reduces
to: Chrome UI, content script that finds policy text, popup that
renders the response. No new backend code.

This is also why option (a) for the Stage 2 question "build fresh
or extend Claude for Chrome" matters less — either way the backend
is this `POST /analyze`.
