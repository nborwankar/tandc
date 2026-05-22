# Stage 1 — Paste-and-Analyze CLI (Design Spec)

**Project**: `tandc` — Terms & Conditions Risk Analyzer
**Stage**: 1 (Paste-and-Analyze CLI)
**Engine variant**: v1 — Anthropic Claude API
**Surface variant**: v1 — CLI
**Taxonomy variant**: v1 — Core 4 + Flag 4
**Inputs variant**: v1 — URL + stdin
**Store variant**: v1 — file cache + per-run report dir
**Date**: 2026-05-18
**Status**: Design — awaiting user review

---

## 1. Goal

Take a website or software Terms & Conditions / Privacy Policy
document and produce a structured **risk report** that surfaces what
matters to an ordinary user: how their personal data is used, what
PII protections are absent, whether the service can change terms
under them, and how disputes are forced into arbitration / class-
action waivers.

The report is consumed two ways:

1. By a human, in the terminal — pretty, scannable, with severity
   colours and verbatim evidence quotes from the source document.
2. By later stages of `tandc` (browser extension, library DB, batch
   audit), as a stable JSON object on disk.

## 2. Non-goals (explicitly out of scope for Stage 1 v1)

- Browser extension UI (Stage 2).
- Persistent SQLite library (Store v2 / Stage 3).
- Batch / multi-doc comparison (Stage 4).
- Hybrid rules + LLM engine (Engine v2).
- File-based input (PDF, local HTML / TXT) — Inputs v2.
- All eight taxonomy categories with full treatment — Taxonomy v2.
- Local LLM fallback. Claude API only.
- Legal advice. The report is informational; it surfaces patterns,
  not legal opinions.

## 3. Architecture

```
              ┌─────────────────────────────────────┐
              │  tandc CLI  (typer)                 │
              │  `tandc analyze <url|->`            │
              └────────────────┬────────────────────┘
                               │
                ┌──────────────▼──────────────┐
                │  input loader               │
                │  url → fetch + extract      │  httpx + trafilatura
                │  stdin/- → read             │
                └──────────────┬──────────────┘
                               │ raw_text + FetchMeta
                ┌──────────────▼──────────────┐
                │  cache lookup               │  ~/.tandc/cache/<key>.json
                │  key = sha256(text) +       │
                │        model + tax_ver +    │
                │        schema_ver           │
                └──────┬───────────────┬──────┘
                  hit  │           miss│
                       │               ▼
                       │     ┌────────────────────┐
                       │     │  analyzer          │  anthropic SDK
                       │     │  prompt + JSON     │  Sonnet 4.6 default
                       │     │  → AnalysisReport  │  Opus 4.7 via --opus
                       │     └─────────┬──────────┘
                       │               │
                       └───────┬───────┘
                               │ AnalysisReport (pydantic)
                ┌──────────────▼──────────────┐
                │  renderer                   │
                │  → terminal (rich)          │
                │  → reports/<slug>-<date>/   │
                │     {input.txt, report.json,│
                │      report.md, fetch_meta} │
                └─────────────────────────────┘
```

The analysis core (`tandc.core`) is a pure library; the CLI is a
thin wrapper. Stage 2's local web UI and the browser extension will
import the same library — there is no CLI-coupled state.

## 4. Components

```
tandc/
├── __init__.py
├── cli.py                # typer app: analyze, cache, version
├── core/
│   ├── __init__.py       # re-exports: analyze(text|url) -> AnalysisReport
│   ├── loader.py         # url_to_text(), stdin_to_text(); records FetchMeta
│   ├── extract.py        # trafilatura wrapper + content-type capture
│   ├── analyzer.py       # Claude call: prompt, JSON-mode parse, retry
│   ├── prompt.py         # versioned prompt (TAXONOMY_VERSION = "v1")
│   ├── schema.py         # pydantic models: AnalysisReport et al.
│   ├── cache.py          # ~/.tandc/cache/ lookup + store
│   ├── render.py         # to_terminal(), to_markdown()
│   └── paths.py          # slug, report dir, hash helpers
└── tests/
    ├── fixtures/         # 4–6 real saved policies
    ├── test_loader.py
    ├── test_cache.py
    ├── test_render.py
    └── test_analyzer_smoke.py   # live Claude, gated by --runslow
```

**Module responsibilities — one purpose each:**

| Module | Does | Depends on |
|--------|------|------------|
| `cli.py` | Argument parsing, call `core.analyze`, hand off to renderer, exit codes | `core`, `render`, `typer` |
| `loader.py` | Resolve input source → text + `FetchMeta` | `httpx`, `extract` |
| `extract.py` | HTML → readable text; capture `Content-Type` header | `trafilatura` |
| `analyzer.py` | Prompt assembly, Claude call, JSON parse, one validation retry | `anthropic`, `schema`, `prompt` |
| `prompt.py` | System prompt + per-call user prompt; carries `TAXONOMY_VERSION` | — |
| `schema.py` | Pydantic v2 models, `schema_version` constant | `pydantic` |
| `cache.py` | Compute cache key, read/write `~/.tandc/cache/<key>.json` | `schema` |
| `render.py` | `AnalysisReport` → terminal (rich) or markdown | `rich`, `schema` |
| `paths.py` | URL → slug, report dir layout, sha256 helpers | — |

## 5. Data shape

All shapes use **pydantic v2** models. JSON serialisation is
`model.model_dump_json(indent=2)`.

```python
from datetime import datetime
from typing import Literal
from pydantic import BaseModel


class FetchMeta(BaseModel):
    source: Literal["url", "stdin"]
    url: str | None = None
    fetched_at: datetime
    http_status: int | None = None
    content_type: str | None = None
    content_type_was_plain: bool = False   # True iff "text/plain" served
    extractor: Literal["trafilatura", "raw"] | None = None
    raw_bytes: int
    extracted_chars: int


class Evidence(BaseModel):
    quote: str                # verbatim snippet from the document
    char_start: int           # offset into extracted text
    char_end: int


class CoreFinding(BaseModel):
    category: Literal[
        "personal_data",
        "pii_protection",
        "continuity",
        "liability_dispute",
    ]
    severity: Literal["low", "medium", "high", "critical"]
    summary: str              # 1–3 sentences, plain English
    why_it_matters: str       # 1–2 sentences on user impact
    evidence: list[Evidence]  # ≥1 quote per finding


class FlagFinding(BaseModel):
    category: Literal[
        "content_licensing",
        "account_access",
        "payment_subscription",
        "jurisdictional",
    ]
    presence: Literal["present", "absent", "unclear"]
    note: str                 # one sentence


class AnalysisReport(BaseModel):
    schema_version: str = "1"
    taxonomy_version: str = "v1"
    model: str                # e.g. "claude-sonnet-4-6"
    analyzed_at: datetime
    input_hash: str           # sha256 of extracted text
    fetch_meta: FetchMeta
    overall_risk: Literal["low", "medium", "high", "critical"]
    headline: str             # 1-sentence TL;DR
    core_findings: list[CoreFinding]   # exactly one per Core 4 category
    flags: list[FlagFinding]           # exactly one per Flag 4 category
    notes: list[str]                   # caveats, ambiguities, doc gaps
```

### Why `content_type_was_plain` is a first-class field

T&Cs are sometimes served as `text/plain` when requested politely
(some sites honour an `Accept: text/plain` header or expose a
`*.txt` variant). The hypothesis worth measuring is **how often**
that happens in practice. The boolean is stored alongside the raw
`content_type` so later analysis can compute the rate across all
analyzed docs once Stage 3's DB exists.

The CLI's terminal output surfaces one line per run, e.g.:

```
Fetched: openai.com/policies/terms-of-use (Content-Type: text/html; plain=False, 84 KiB)
```

### Cache key

```
key = sha256(
    extracted_text || "|" ||
    model || "|" ||
    taxonomy_version || "|" ||
    schema_version
).hexdigest()
```

This means a taxonomy bump (`v1` → `v2`) automatically invalidates
all old cache entries — no migration code needed.

### Report directory layout

For invocation `tandc analyze https://openai.com/policies/terms-of-use/`
on 2026-05-18, written under CWD:

```
reports/
└── openai.com-terms-of-use-2026-05-18/
    ├── input.txt              # extracted policy body
    ├── fetch_meta.json        # FetchMeta as JSON
    ├── report.json            # full AnalysisReport
    └── report.md              # rendered markdown report
```

Slug rules: host + last meaningful path segment, lowercased, non-
alphanumerics → `-`, truncated to 64 chars. If the slug collides
with an existing dir on the same date, append `-2`, `-3`, etc.

## 6. CLI surface

```
tandc analyze <url|-> [--opus] [--no-cache] [--output-dir DIR] [--json]
tandc cache list [--limit N]
tandc cache clear [--yes]
tandc version
```

- `tandc analyze https://example.com/terms` — fetch + analyze.
- `cat policy.txt | tandc analyze -` — read text from stdin.
- `--opus` — use `claude-opus-4-7` instead of the Sonnet default.
- `--no-cache` — bypass cache for this call (still writes the new
  cache entry).
- `--output-dir DIR` — override CWD `./reports/`.
- `--json` — write `report.json` only (no `report.md`) and emit
  the JSON payload to stdout instead of the rich terminal report
  (useful for piping).
- `tandc cache list` — show `key | model | taxonomy_ver | host |
  date` for entries in `~/.tandc/cache/`.
- `tandc cache clear` — prompts for confirmation (no `--yes` means
  it refuses, per the standing "ASK before deleting" rule).

Exit codes:

| Code | Meaning |
|------|---------|
| `0` | Analysis completed (cache hit or fresh). |
| `2` | Input error (URL fetch failed, extraction empty, stdin empty). |
| `3` | Analysis error (Claude call failed twice or schema invalid twice). |
| `4` | Configuration error (no `ANTHROPIC_API_KEY`, etc.). |

## 7. Error handling

Strict no-silent-swallow per the standing rule. Every failure
either raises with full context or is logged at WARNING with a
named consequence; nothing is `except: pass`.

| Failure | Behaviour |
|---------|-----------|
| URL fetch — DNS / 4xx / 5xx / timeout | Raise `TandcFetchError(url, status)`. CLI prints message + suggests `--stdin` paste fallback. Exit 2. |
| Extraction returns empty / <200 chars | Raise `TandcExtractionError(url, raw_bytes)`. Same message + fallback hint. Exit 2. |
| `ANTHROPIC_API_KEY` missing | Raise `TandcConfigError`. Print setup hint. Exit 4. |
| Claude API error (network, 429, 5xx) | Bubble up the SDK exception with context. No silent retry, no model fallback. Exit 3. |
| Claude returned malformed JSON | One automatic retry with a "your previous response failed validation: <pydantic error>" message. If still bad, raise `TandcAnalysisError` and write `raw_response.txt` into the report dir for inspection. Exit 3. |
| Cache write fails (permissions / disk full) | Log WARNING with the path and the underlying error; return the report anyway. Cache is an optimisation, not a requirement. |
| Cache read returns malformed JSON | Log WARNING, treat as a miss, re-analyze. Do not crash. |
| Slug collision on output dir | Append `-2`, `-3`, …; never overwrite. |

Logging: `logging.basicConfig(level=INFO)` by default; `--debug`
flag elevates to DEBUG and enables HTTP debug for `httpx` and
`anthropic` per the standing logging rule.

## 8. Prompt design

A single system prompt carries:

1. Role + objective ("You analyze T&C / privacy docs and surface
   user risks. You are not giving legal advice.").
2. The taxonomy (Core 4 + Flag 4) with one-sentence definitions
   each.
3. The output JSON schema (rendered from `AnalysisReport.model_json_schema()`).
4. Hard rules: evidence quotes must be verbatim substrings of the
   input; offsets are character indices into the input; one
   `CoreFinding` per Core category even if `severity="low"`; one
   `FlagFinding` per Flag category even if `presence="absent"`.

The user message is the extracted policy text, prefixed with
`<DOCUMENT>` / suffixed with `</DOCUMENT>` to make injection of
prompt-like text inside the policy harmless.

**Prompt caching**: the system prompt + schema are marked
`cache_control={"type": "ephemeral"}` so re-runs against different
documents on the same model amortise to near-zero system-prompt
tokens.

`TAXONOMY_VERSION = "v1"` lives in `prompt.py` and participates in
the cache key — bumping it on prompt changes auto-invalidates old
cache entries.

## 9. Testing

Following standing rules: no mocked DBs in integration; no silent
exception swallowing in test code; every test run goes to
`docs/test_runs/` and a row in `docs/TEST_LOG.md`.

### Unit tests (fast, mock Claude)

- `test_loader.py` — `responses`-mocked HTTP; verifies trafilatura
  invocation, `Content-Type` capture, `content_type_was_plain`
  truthiness for `text/plain` vs `text/html`, empty-extraction error
  path, stdin path.
- `test_cache.py` — key derivation includes all four components;
  hit and miss paths; `--no-cache` bypass writes a new entry;
  malformed cache file treated as miss with WARNING; missing
  `~/.tandc/cache/` is created on first write.
- `test_render.py` — snapshot tests of terminal output and markdown
  render against a hand-crafted `AnalysisReport`.
- `test_schema.py` — well-formed and malformed payloads; verifies
  every Core 4 category appears exactly once; same for Flag 4.

### Smoke test (live Claude, gated)

- `test_analyzer_smoke.py @pytest.mark.slow` — feeds one fixture
  policy to Claude, asserts `AnalysisReport` parses, all four core
  findings present, evidence quotes are verifiable substrings of
  the input. Run with `pytest -m slow`. Costs roughly 1¢ per
  invocation.

### Fixtures

`tests/fixtures/` holds 4–6 real policies, each as:

```
<vendor>/
├── input.html             # original HTML
├── extracted.txt          # trafilatura output (committed for stability)
├── fetch_meta.json        # captured Content-Type, etc.
└── expected_findings.yaml # human-curated: which categories *should* fire, severity range
```

`expected_findings.yaml` is a tolerance file, not a fixture for
exact matching — Claude output varies. Smoke tests assert
*category coverage* + *severity range*, not exact prose.

Initial fixture vendors (to be fetched as part of implementation):
OpenAI, Anthropic, Notion, GitHub, Slack, Discord.

## 10. Tech stack

| Concern | Choice |
|---------|--------|
| Language | Python 3.11 |
| Env mgmt | conda env `tandc` (recorded in project CLAUDE.md per standing rule) |
| CLI | `typer` |
| HTTP | `httpx` |
| HTML extraction | `trafilatura` |
| LLM | `anthropic` SDK (Sonnet 4.6 default, Opus 4.7 escalation) |
| Schemas | `pydantic` v2 |
| Terminal UI | `rich` |
| Tests | `pytest` + `responses` + `pyyaml` (fixture expectations) |
| Lint / fmt | `ruff` |
| Device | CPU-only for v1 (forward-compat MPS block stubbed in `__init__.py` for v2) |

## 11. Project layout

```
tandc/
├── CLAUDE.md              # project-level instructions (incl. conda env name)
├── DONE.md
├── README.md
├── PLAN.md                # multi-stage roadmap (already created)
├── pyproject.toml
├── environment.yml        # conda env definition
├── .gitignore             # reports/, .tandc/, *.pyc, etc.
├── docs/
│   ├── superpowers/specs/2026-05-18-stage1-paste-and-analyze-design.md  (this doc)
│   ├── test_runs/         # raw pytest output, per the standing rule
│   └── TEST_LOG.md
├── src/tandc/             # package (see Components above)
└── tests/                 # see Testing above
```

Conda env name: **`tandc`**. To be recorded in CLAUDE.md on
project init.

## 12. Open questions deferred to implementation

These are intentionally not pinned in the spec because they're
small enough to decide while coding without architectural impact:

- Exact rich layout for terminal report (table vs. nested panels).
- Whether to use `anthropic`'s `tool_use` mode or plain JSON-mode
  for the structured output. (Default: try `tool_use` first; fall
  back to JSON-mode if pydantic compatibility is awkward.)
- Whether `tandc cache list` paginates or just truncates with
  `--limit`.

## 13. Success criteria for Stage 1 v1

1. `tandc analyze <url>` for any of the six fixture vendors
   produces a valid `AnalysisReport` end-to-end.
2. All four Core findings present in every report; all four Flag
   entries present.
3. Every `Evidence.quote` is a verifiable substring of the
   extracted input text.
4. Second run on the same URL returns the cached report in <100 ms
   with no Claude call.
5. `content_type_was_plain` accurately reflects the response header
   across all fixtures (manual spot-check vs. saved
   `fetch_meta.json`).
6. Unit tests pass with no live API calls; smoke test passes with
   `-m slow`.

Once these six are green, Stage 1 v1 is done and we move to
Surface v2 (local web UI) or directly to Stage 2 (browser
extension) — to be decided then.

---

## Appendix A — Roadmap dimensions and current pin

| Dimension | v1 (this spec) | v2 (next) |
|-----------|----------------|-----------|
| Product stage | Paste-and-analyze CLI | Browser extension on click-to-accept |
| Engine | Claude API (Sonnet → Opus) | Hybrid: rules + Claude |
| Surface | CLI | + local web UI |
| Taxonomy | Core 4 + Flag 4 | Comprehensive (all 8 full treatment) |
| Inputs | URL + stdin | + file (HTML, TXT, PDF) |
| Store | File cache + per-run report dir | SQLite at `~/.tandc/tandc.db` + import existing |

Every v2 upgrade is independently sequenceable; ordering will be
decided after v1 is in hand.
