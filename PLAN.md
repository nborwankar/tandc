# tandc — Terms & Conditions Risk Analyzer

**Goal**: Take a website or software Terms & Conditions / Privacy Policy
document and surface risks for the user — especially around personal
data use, lack of PII protections, no guarantees of continuity of
promises, unilateral-change clauses, arbitration / class-action
waivers, license overreach, and similar hazards.

## Four-Stage Roadmap

The product is built in four stages, in this order. Each stage builds
on the previous and is independently usable.

### Stage 1 — Paste-and-Analyze CLI / Web Tool
**v1 (CLI): shipped 2026-05-20. v2 (local web UI): shipped 2026-05-21.**
See `docs/superpowers/specs/2026-05-21-stage1-v2-web-ui-design.md` (spec)
and `docs/superpowers/plans/2026-05-21-stage1-v2-web-ui.md` (plan).

- Input: a T&C document (pasted text, URL, or file path).
- Output: a structured risk report (categories, severity, evidence
  quotes, plain-English summary).
- One-shot, on demand. The simplest end-to-end product.
- Sets the analysis engine, risk taxonomy, and report format that
  later stages reuse.

### Stage 2 — Browser Extension on Click-to-Accept *(next after v2 ships)*
Two open paths to decide at Stage 2 brainstorm time:
(a) fresh Chrome extension calling `localhost:8765/analyze` (the v2 API);
(b) extend the official Claude for Chrome extension if it exposes a
plug-in surface (unverified — needs research at the time).
Either way, the Stage 1 v2 web UI's `POST /analyze` endpoint is the backend.

- When a site shows a T&C / privacy popup or links to its policies,
  surface the Stage 1 analysis inline before the user clicks Accept.
- Most contextual delivery, but biggest engineering lift (extension
  packaging, DOM detection, cross-browser).
- Reuses the Stage 1 analysis backend as a service.

### Stage 3 — Library of Analyzed Docs
- Persist analyzed T&Cs in a personal / shared database, keyed by
  company / product / version / fetch-date.
- Queryable: "what does Notion say about training on my data?",
  comparable across providers, re-checkable when the doc changes
  (diff alerts).

### Stage 4 — Batch Audit Tool
- Point at a list of services (e.g. all the SaaS a company uses) and
  produce a comparative risk dashboard.
- Built on top of the Stage 3 library; mostly orchestration + a
  comparison/reporting layer.

## Analysis Engine Roadmap

The analysis engine evolves in two phases, orthogonal to the product
stages above:

1. **Engine v1 — Anthropic Claude API**. Used from Stage 1 onward.
   Best reasoning over long legal text, can quote/cite evidence,
   prompt caching keeps repeat cost low. Default to Sonnet, escalate
   to Opus for ambiguous documents.
2. **Engine v2 — Hybrid: rules + small local + Claude**. Regex /
   pattern detectors catch the well-known risky clauses (arbitration,
   perpetual license, unilateral changes, etc.) for free and
   instantly. Ambiguous or novel clauses escalate to the Claude API.
   Cheapest at scale and most explainable. Introduced after Stage 1
   is proven.

## Stage 1 Surface Roadmap

1. **Surface v1 — CLI.** `tandc analyze <url|file|->` prints a
   structured risk report to the terminal and writes JSON + Markdown
   artefacts to disk. The analysis core is a pure library.
2. **Surface v2 — local web UI.** `tandc serve` exposes a single-page
   form (paste / URL / file upload) that renders the same report in
   the browser. Reuses the v1 library; also becomes the local HTTP
   endpoint the Stage 2 browser extension calls.

## Risk Taxonomy Roadmap

**Taxonomy v1 — "Core 4 + flags".** Four categories get full
treatment (evidence quotes, severity, plain-English summary):

1. Personal-data collection & use
2. PII protection gaps
3. Continuity / promise stability
4. Liability & dispute resolution

Four further categories get a single-line `present / not present /
unclear` flag with a one-sentence note:

5. Content licensing & IP
6. Account / access risks
7. Payment & subscription traps
8. Jurisdictional & compliance posture

**Taxonomy v2 — comprehensive.** All eight categories get full
treatment. Introduced once v1 is solid and Engine v2 (hybrid) is in
place to keep token cost manageable.

## Input Modes Roadmap

1. **Inputs v1 — URL + paste.** `tandc analyze https://...` fetches
   the page and extracts policy text (trafilatura / readability).
   `cat policy.txt | tandc analyze -` accepts pasted text on stdin.
   Quickest happy path; avoids the PDF / file-format rabbit hole at
   first.
2. **Inputs v2 — add file & PDF.** `tandc analyze ./policy.{html,txt,pdf}`
   reads from disk, with a PDF text extractor (pdfminer / pypdf).

## Cache & Storage Roadmap

1. **Store v1 — file cache + per-run report dir.** Content-hash
   cache at `~/.tandc/cache/` keyed by SHA-256(input) + model +
   taxonomy-version. Each run also writes
   `./reports/<host-or-slug>-<YYYY-MM-DD>/{input.txt, report.json,
   report.md}`. `--no-cache` forces re-analysis.
2. **Store v2 — SQLite at `~/.tandc/tandc.db`.** Promoted after v1
   has been exercised against several real T&Cs. Becomes the
   foundation of Stage 3 (library of analyzed docs). Includes a
   one-shot importer that reads all existing
   `~/.tandc/cache/` + `./reports/` artefacts and loads them into the
   DB so no analysis is lost in the migration.

## Current Status

**Stage 1 v1 (CLI) — shipped 2026-05-20.** Merged to `main` at
commit `e2cd027`. 88 unit tests + 6/6 live smoke. See `DONE.md`.

**Stage 1 v2 (local web UI) — shipped 2026-05-21 at `99c7710`.**
126 unit tests + 6/6 live regression smoke + live e2e (3 input
modes + 4 error mappings + cache hit) all green. Recommended
launcher: `./scripts/serve.sh` (conda PATH + API-key precheck).
Spec: `docs/superpowers/specs/2026-05-21-stage1-v2-web-ui-design.md`.
Plan: `docs/superpowers/plans/2026-05-21-stage1-v2-web-ui.md`.

**Stage 2 (Chrome extension) — brainstorm pending.** Decision: fresh
extension calling `localhost:8765/analyze` vs extending Claude for
Chrome. The v2 `POST /analyze` endpoint is the backend either way.

**Active variant pin**:
- Engine v1 (Claude API)
- Surface v2 (CLI + local web UI)
- Taxonomy v1 (Core 4 + Flag 4)
- Inputs v1 on CLI, web v2 ahead (URL + paste + file upload: HTML/TXT/PDF)
- Store v1 (file cache + per-run report dir)
