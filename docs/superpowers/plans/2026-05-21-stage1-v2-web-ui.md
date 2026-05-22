# Stage 1 v2 — Local Web UI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship a local single-page web UI (`tandc serve`) that wraps the existing `tandc.core.analyze()` pipeline behind a FastAPI `POST /analyze` JSON endpoint, supporting three input modes (URL, paste, file upload incl. PDF).

**Architecture:** Add a thin `tandc.web.*` package: FastAPI app, single `POST /analyze` endpoint, vanilla-JS frontend, uvicorn launcher. Refactor `core.analyze()` to expose a `analyze_prepared(text, fetch_meta, slug, ...)` adapter so the web layer can bypass the URL/stdin loaders for paste/file modes while reusing the cache + Claude + artefact-write pipeline. `FetchMeta.source` gets two new literals (`"paste"`, `"file"`). No other changes to `tandc.core`.

**Tech Stack:** FastAPI, uvicorn[standard], pypdf, python-multipart (new); reuses existing Pydantic v2, httpx, trafilatura, Anthropic SDK, rich, typer.

**Conda env:** `tandc` (Python 3.11) at `/Users/nitin/anaconda3/envs/tandc/`. All shell commands assume `PATH=/Users/nitin/anaconda3/envs/tandc/bin:$PATH` prefix.

**Spec:** `docs/superpowers/specs/2026-05-21-stage1-v2-web-ui-design.md`

---

## File Map

| File | Action | Responsibility |
|------|--------|----------------|
| `pyproject.toml` | modify | Add fastapi/uvicorn/pypdf/python-multipart |
| `src/tandc/core/schema.py` | modify | Extend `FetchMeta.source` enum to include `paste`, `file` |
| `src/tandc/core/loader.py` | modify | Add `text_to_meta(text, source, source_url, filename)` builder |
| `src/tandc/core/__init__.py` | modify | Extract cache+analyze+write into `analyze_prepared()`; keep `analyze()` as a wrapper |
| `src/tandc/cli.py` | modify | Add `serve` subcommand |
| `src/tandc/web/__init__.py` | create | Package marker |
| `src/tandc/web/pdf.py` | create | `extract_pdf(blob: bytes) -> str` via pypdf |
| `src/tandc/web/api.py` | create | Pydantic request models, POST /analyze handler, dispatch, error mapping |
| `src/tandc/web/app.py` | create | FastAPI app factory, exception handlers, static mount |
| `src/tandc/web/serve.py` | create | uvicorn launcher (host/port/reload), API key pre-flight, port-in-use trap |
| `src/tandc/web/static/index.html` | create | Single-page form |
| `src/tandc/web/static/tandc.css` | create | Severity palette, ~80 LOC, no framework |
| `src/tandc/web/static/tandc.js` | create | Vanilla JS: submit form, fetch /analyze, render report |
| `tests/web/__init__.py` | create | Package marker |
| `tests/web/test_pdf.py` | create | pypdf extraction unit tests |
| `tests/web/test_api.py` | create | FastAPI TestClient: URL/paste/file modes, error mappings |
| `tests/web/test_serve.py` | create | API-key pre-flight + port-in-use behaviour (no real socket bind) |
| `tests/web/test_cli_serve.py` | create | CLI `serve` subcommand routes through to `web.serve.run()` |
| `tests/web/fixtures/sample.pdf` | create | Tiny PDF containing known sentinel text |
| `tests/test_schema.py` | modify | Cover paste/file source variants |
| `tests/test_loader.py` | modify | Cover `text_to_meta` builder |
| `tests/test_core_analyze.py` | modify | Cover `analyze_prepared()` path |
| `DONE.md` | modify | Add 2026-05-2x v2 ship entry |
| `PLAN.md` | modify | Mark v2 shipped |
| `CLAUDE.md` | modify | Update Shipped/Active |

---

## Task 1: Add web-layer dependencies

**Files:**
- Modify: `pyproject.toml`

- [ ] **Step 1: Edit `pyproject.toml` dependencies block**

Add to the existing `[project] dependencies` list:

```toml
dependencies = [
    "anthropic>=0.40.0",
    "typer>=0.12.0",
    "httpx>=0.27.0",
    "trafilatura>=1.12.0",
    "pydantic>=2.7.0",
    "rich>=13.7.0",
    "pyyaml>=6.0",
    "fastapi>=0.115.0",
    "uvicorn[standard]>=0.30.0",
    "pypdf>=4.3.0",
    "python-multipart>=0.0.9",
]
```

- [ ] **Step 2: Install into the conda env**

```bash
PATH=/Users/nitin/anaconda3/envs/tandc/bin:$PATH pip install -e ".[dev]"
```

Expected: installs fastapi, uvicorn, pypdf, python-multipart; pip reports `Successfully installed ...`.

- [ ] **Step 3: Smoke-verify imports**

```bash
PATH=/Users/nitin/anaconda3/envs/tandc/bin:$PATH python -c "import fastapi, uvicorn, pypdf, multipart; print('ok')"
```

Expected output: `ok`

- [ ] **Step 4: Commit**

```bash
git add pyproject.toml
git commit -m "deps: add fastapi/uvicorn/pypdf/python-multipart for web UI"
```

---

## Task 2: Extend `FetchMeta.source` to cover paste and file

**Files:**
- Modify: `src/tandc/core/schema.py:44`
- Modify: `tests/test_schema.py`

- [ ] **Step 1: Write failing test for new source variants**

Append to `tests/test_schema.py`:

```python
def test_fetch_meta_accepts_paste_source():
    from datetime import datetime, timezone
    from tandc.core.schema import FetchMeta
    m = FetchMeta(
        source="paste",
        url="https://example.com/terms",
        fetched_at=datetime.now(timezone.utc),
        http_status=None,
        content_type=None,
        content_type_was_plain=False,
        extractor=None,
        raw_bytes=10,
        extracted_chars=10,
    )
    assert m.source == "paste"


def test_fetch_meta_accepts_file_source():
    from datetime import datetime, timezone
    from tandc.core.schema import FetchMeta
    m = FetchMeta(
        source="file",
        url=None,
        fetched_at=datetime.now(timezone.utc),
        http_status=None,
        content_type="application/pdf",
        content_type_was_plain=False,
        extractor=None,
        raw_bytes=2048,
        extracted_chars=512,
    )
    assert m.source == "file"
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
PATH=/Users/nitin/anaconda3/envs/tandc/bin:$PATH pytest tests/test_schema.py::test_fetch_meta_accepts_paste_source tests/test_schema.py::test_fetch_meta_accepts_file_source -v
```

Expected: FAIL with pydantic validation error (`source` must be `'url' | 'stdin'`).

- [ ] **Step 3: Widen `FetchMeta.source` literal**

Edit `src/tandc/core/schema.py` line 44 inside `class FetchMeta(BaseModel):`:

```python
    source: Literal["url", "stdin", "paste", "file"]
```

- [ ] **Step 4: Re-run failing tests, plus the full schema suite**

```bash
PATH=/Users/nitin/anaconda3/envs/tandc/bin:$PATH pytest tests/test_schema.py -v
```

Expected: all tests pass (existing schema tests still pass, two new ones now pass).

- [ ] **Step 5: Commit**

```bash
git add src/tandc/core/schema.py tests/test_schema.py
git commit -m "schema: add paste/file FetchMeta.source variants for web UI"
```

---

## Task 3: Add `text_to_meta()` builder in loader

**Files:**
- Modify: `src/tandc/core/loader.py`
- Modify: `tests/test_loader.py`

- [ ] **Step 1: Write failing tests**

Append to `tests/test_loader.py`:

```python
import io as _io
import pytest as _pytest


def test_text_to_meta_paste_with_source_url():
    from tandc.core.loader import text_to_meta
    text, meta = text_to_meta(
        text="We collect your data.",
        source="paste",
        source_url="https://example.com/terms",
    )
    assert text == "We collect your data."
    assert meta.source == "paste"
    assert meta.url == "https://example.com/terms"
    assert meta.extracted_chars == len(text)
    assert meta.raw_bytes == len(text.encode("utf-8"))


def test_text_to_meta_paste_without_source_url():
    from tandc.core.loader import text_to_meta
    text, meta = text_to_meta(text="Hello world.", source="paste")
    assert meta.url is None
    assert meta.source == "paste"


def test_text_to_meta_file_records_content_type_and_filename():
    from tandc.core.loader import text_to_meta
    text, meta = text_to_meta(
        text="Policy body extracted from PDF.",
        source="file",
        filename="terms.pdf",
        content_type="application/pdf",
    )
    assert meta.source == "file"
    assert meta.content_type == "application/pdf"
    # filename is informational; we encode it into url field as filename:NAME so
    # the report's fetch_meta carries it forward without changing the schema.
    assert meta.url == "file:terms.pdf"


def test_text_to_meta_empty_text_raises():
    from tandc.core.loader import text_to_meta
    from tandc.errors import TandcExtractionError
    with _pytest.raises(TandcExtractionError):
        text_to_meta(text="   \n   ", source="paste")


def test_text_to_meta_normalises_unicode():
    from tandc.core.loader import text_to_meta
    text, meta = text_to_meta(text="We “may” share data.", source="paste")
    # smart quotes round-trip to ASCII via core.extract._normalise_text
    assert "“" not in text and "”" not in text
    assert '"may"' in text
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
PATH=/Users/nitin/anaconda3/envs/tandc/bin:$PATH pytest tests/test_loader.py -k text_to_meta -v
```

Expected: ImportError / AttributeError — `text_to_meta` does not exist yet.

- [ ] **Step 3: Implement `text_to_meta`**

Append to `src/tandc/core/loader.py`:

```python
from typing import Literal as _Literal

from tandc.core.extract import _normalise_text


def text_to_meta(
    text: str,
    source: _Literal["paste", "file"],
    source_url: str | None = None,
    filename: str | None = None,
    content_type: str | None = None,
) -> tuple[str, FetchMeta]:
    """Build (normalised_text, FetchMeta) for already-loaded text.

    Used by the web layer for paste mode and file-upload mode. URL/stdin loading
    stays in url_to_text / stdin_to_text.

    `source_url` is metadata only (no fetch). `filename` is encoded into
    FetchMeta.url as `file:<name>` so it round-trips without schema changes.
    """
    normalised = _normalise_text(text)
    raw_bytes = len(normalised.encode("utf-8"))
    if not normalised.strip():
        raise TandcExtractionError(url=source_url, raw_bytes=raw_bytes, extracted_chars=0)
    if source == "file":
        meta_url = f"file:{filename}" if filename else None
    else:
        meta_url = source_url
    meta = FetchMeta(
        source=source,
        url=meta_url,
        fetched_at=datetime.now(timezone.utc),
        http_status=None,
        content_type=content_type,
        content_type_was_plain=False,
        extractor=None,
        raw_bytes=raw_bytes,
        extracted_chars=len(normalised),
    )
    return normalised, meta
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
PATH=/Users/nitin/anaconda3/envs/tandc/bin:$PATH pytest tests/test_loader.py -v
```

Expected: all loader tests pass (existing + 5 new ones).

- [ ] **Step 5: Commit**

```bash
git add src/tandc/core/loader.py tests/test_loader.py
git commit -m "loader: add text_to_meta builder for paste/file inputs"
```

---

## Task 4: Extract `analyze_prepared()` from `core.analyze()`

The web layer needs to enter the pipeline post-loader (text + fetch_meta already in hand, with a caller-supplied slug). Extract the cache+analyze+write tail into a public helper, keep `analyze()` as a wrapper that calls it.

**Files:**
- Modify: `src/tandc/core/__init__.py`
- Modify: `tests/test_core_analyze.py`

- [ ] **Step 1: Write failing tests**

Append to `tests/test_core_analyze.py`:

```python
def test_analyze_prepared_writes_artefacts_with_supplied_slug(monkeypatch, tmp_path):
    """analyze_prepared bypasses the loader; uses provided text + slug verbatim."""
    from datetime import date, datetime, timezone
    from tandc.core import analyze_prepared
    from tandc.core.schema import FetchMeta
    from tests.test_core_analyze import _fake_client_returning  # reuse helper if present
    text = "These are pasted terms. We share data with third parties."
    fm = FetchMeta(
        source="paste",
        url="https://example.com/terms",
        fetched_at=datetime.now(timezone.utc),
        http_status=None,
        content_type=None,
        content_type_was_plain=False,
        extractor=None,
        raw_bytes=len(text.encode("utf-8")),
        extracted_chars=len(text),
    )
    monkeypatch.setenv("TANDC_CACHE_DIR", str(tmp_path / "cache"))
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    fake_client = _fake_client_returning(text=text, fetch_meta=fm)
    report, rdir = analyze_prepared(
        text=text,
        fetch_meta=fm,
        slug="example-com-terms",
        model="claude-sonnet-4-6",
        use_cache=True,
        output_base=tmp_path,
        client=fake_client,
        on_date=date(2026, 5, 21),
    )
    assert rdir is not None
    assert rdir.name == "example-com-terms-2026-05-21"
    assert (rdir / "input.txt").read_text(encoding="utf-8") == text
    assert (rdir / "report.json").exists()
    assert (rdir / "fetch_meta.json").exists()
    assert (rdir / "report.md").exists()


def test_analyze_prepared_skips_artefacts_when_output_base_none(monkeypatch, tmp_path):
    from datetime import datetime, timezone
    from tandc.core import analyze_prepared
    from tandc.core.schema import FetchMeta
    from tests.test_core_analyze import _fake_client_returning
    text = "Pasted policy text for JSON-only mode."
    fm = FetchMeta(
        source="paste",
        url=None,
        fetched_at=datetime.now(timezone.utc),
        http_status=None,
        content_type=None,
        content_type_was_plain=False,
        extractor=None,
        raw_bytes=len(text.encode("utf-8")),
        extracted_chars=len(text),
    )
    monkeypatch.setenv("TANDC_CACHE_DIR", str(tmp_path / "cache"))
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    report, rdir = analyze_prepared(
        text=text,
        fetch_meta=fm,
        slug="paste-abc12345",
        model="claude-sonnet-4-6",
        use_cache=True,
        output_base=None,
        client=_fake_client_returning(text=text, fetch_meta=fm),
    )
    assert rdir is None


def test_analyze_wrapper_still_works_with_url(monkeypatch, tmp_path):
    """Regression: existing analyze(url=...) callers keep working unchanged."""
    # This test exists already in this file for url mode; this is a placeholder
    # asserting we did not break it. If a url-mode test already exists, skip.
    pass
```

If a helper `_fake_client_returning(...)` doesn't exist, add it at the top of `tests/test_core_analyze.py`:

```python
def _fake_client_returning(text, fetch_meta):
    """Return a stand-in Anthropic client whose analyze_text() output is well-formed."""
    from datetime import datetime, timezone
    from unittest.mock import MagicMock
    from tandc.core.schema import (
        AnalysisReport,
        CoreFinding,
        Evidence,
        FlagFinding,
        CORE_CATEGORIES,
        FLAG_CATEGORIES,
    )
    # Build a valid AnalysisReport directly; tests at this layer don't exercise Claude.
    # Pick a substring of `text` for the evidence quote so it's verbatim-locatable.
    quote = text[: min(40, len(text))]
    report = AnalysisReport(
        model="claude-sonnet-4-6",
        analyzed_at=datetime.now(timezone.utc),
        input_hash="0" * 64,
        fetch_meta=fetch_meta,
        overall_risk="high",
        headline="Test report for analyze_prepared.",
        core_findings=[
            CoreFinding(
                category=cat,
                severity="high",
                summary="Stub summary for tests.",
                why_it_matters="Stub why-it-matters for tests.",
                evidence=[Evidence(quote=quote, char_start=0, char_end=len(quote))],
            )
            for cat in CORE_CATEGORIES
        ],
        flags=[
            FlagFinding(category=cat, presence="present", note="stub note")
            for cat in FLAG_CATEGORIES
        ],
        notes=[],
    )
    client = MagicMock()
    # tandc.core.analyzer.analyze_text() consumes the client; for this test we patch
    # analyze_text directly at call sites. Returning the report from a sentinel
    # attribute lets the test substitute it via monkeypatch where needed.
    client._stub_report = report
    return client
```

If `_fake_client_returning` is added, also patch `tandc.core.analyzer.analyze_text` in the new tests so they short-circuit Claude. Append the patch at the top of each new test, using `monkeypatch.setattr`:

```python
    import tandc.core as _core_mod
    monkeypatch.setattr(
        _core_mod, "analyze_text",
        lambda **kwargs: fake_client._stub_report,
    )
```

(Replace the body of `_fake_client_returning` usage above to make `monkeypatch.setattr` the actual injection point; the stub client only carries the report.)

- [ ] **Step 2: Run tests to verify they fail**

```bash
PATH=/Users/nitin/anaconda3/envs/tandc/bin:$PATH pytest tests/test_core_analyze.py -k analyze_prepared -v
```

Expected: ImportError — `analyze_prepared` not exported from `tandc.core`.

- [ ] **Step 3: Refactor `core/__init__.py` to extract `analyze_prepared()`**

Replace the body of `analyze` in `src/tandc/core/__init__.py` and add `analyze_prepared` alongside:

```python
"""tandc core library — pure analysis pipeline reusable by CLI / web UI / extension."""

from __future__ import annotations

import logging
import os
from datetime import date
from pathlib import Path
from typing import IO

from anthropic import Anthropic

from tandc.core.analyzer import MODEL_SONNET, analyze_text
from tandc.core.cache import cache_key, load_from_cache, store_in_cache
from tandc.core.loader import stdin_to_text, url_to_text
from tandc.core.paths import report_dir, slug_for_url
from tandc.core.render import to_markdown
from tandc.core.schema import AnalysisReport, FetchMeta
from tandc.errors import TandcConfigError

__all__ = [
    "analyze",
    "analyze_prepared",
    "AnalysisReport",
    "FetchMeta",
    "MODEL_SONNET",
]

log = logging.getLogger(__name__)


def analyze_prepared(
    *,
    text: str,
    fetch_meta: FetchMeta,
    slug: str,
    model: str = MODEL_SONNET,
    use_cache: bool = True,
    output_base: Path | None = None,
    client: Anthropic | None = None,
    on_date: date | None = None,
) -> tuple[AnalysisReport, Path | None]:
    """Run the cache + Claude + artefact-write stages on already-loaded text.

    Callers (web layer, future ingestors) are responsible for loading text and
    building a FetchMeta. `slug` is used verbatim for the report directory name.
    """
    key = cache_key(text, model)
    report = load_from_cache(key) if use_cache else None
    cache_hit = report is not None

    if report is None:
        if client is None:
            if not os.environ.get("ANTHROPIC_API_KEY"):
                raise TandcConfigError(
                    "ANTHROPIC_API_KEY is not set — export it before running tandc"
                )
            client = Anthropic()
        report = analyze_text(
            text=text, fetch_meta=fetch_meta, client=client, model=model
        )
        store_in_cache(key, report)
    else:
        log.info("cache hit for key=%s", key)

    if output_base is None:
        return report, None

    artefact_fetch_meta = report.fetch_meta if cache_hit else fetch_meta
    rdir = report_dir(output_base, slug=slug, on_date=on_date or date.today())
    (rdir / "input.txt").write_text(text, encoding="utf-8")
    (rdir / "fetch_meta.json").write_text(
        artefact_fetch_meta.model_dump_json(indent=2), encoding="utf-8"
    )
    (rdir / "report.json").write_text(
        report.model_dump_json(indent=2), encoding="utf-8"
    )
    (rdir / "report.md").write_text(to_markdown(report), encoding="utf-8")
    log.info("cache_hit=%s report_dir=%s", cache_hit, rdir)
    return report, rdir


def analyze(
    *,
    url: str | None = None,
    stdin: IO[str] | None = None,
    model: str = MODEL_SONNET,
    use_cache: bool = True,
    output_base: Path | None = None,
    client: Anthropic | None = None,
    on_date: date | None = None,
) -> tuple[AnalysisReport, Path | None]:
    """Run the full pipeline.

    Exactly one of `url` or `stdin` must be provided. Returns the
    AnalysisReport and the path to the report directory (None if
    `output_base` is None).
    """
    if (url is None) == (stdin is None):
        raise ValueError("exactly one of url= or stdin= is required")

    if url is not None:
        text, fetch_meta = url_to_text(url)
        key_for_slug = cache_key(text, model)
        slug = slug_for_url(url)
    else:
        text, fetch_meta = stdin_to_text(stdin)
        key_for_slug = cache_key(text, model)
        slug = f"stdin-{key_for_slug[:8]}"

    return analyze_prepared(
        text=text,
        fetch_meta=fetch_meta,
        slug=slug,
        model=model,
        use_cache=use_cache,
        output_base=output_base,
        client=client,
        on_date=on_date,
    )
```

- [ ] **Step 4: Run the full unit suite to verify no regression**

```bash
PATH=/Users/nitin/anaconda3/envs/tandc/bin:$PATH pytest tests/ -v -m "not slow"
```

Expected: all existing tests pass, three new `analyze_prepared` tests pass.

- [ ] **Step 5: Commit**

```bash
git add src/tandc/core/__init__.py tests/test_core_analyze.py
git commit -m "core: extract analyze_prepared() for web-layer reuse"
```

---

## Task 5: Create `tests/web/` scaffolding and a tiny sample PDF

**Files:**
- Create: `tests/web/__init__.py` (empty)
- Create: `tests/web/fixtures/sample.pdf`

- [ ] **Step 1: Create test package marker**

```bash
mkdir -p tests/web/fixtures
touch tests/web/__init__.py
```

- [ ] **Step 2: Generate sample.pdf containing a known sentinel string**

Run a one-shot Python script via pypdf to create a 1-page PDF with body text `"TANDC SAMPLE PDF — we collect personal data and use arbitration."`. Save as `scripts/_make_sample_pdf.py` so it's reproducible:

```python
"""Generate tests/web/fixtures/sample.pdf with a known sentinel string.

Re-run only when the sentinel changes.
"""
from pathlib import Path

from pypdf import PdfWriter
from pypdf.generic import RectangleObject

SENTINEL = "TANDC SAMPLE PDF - we collect personal data and use arbitration."

# pypdf doesn't write text content easily; use reportlab-free approach via
# a minimal raw PDF stream that pypdf can read back.
RAW_PDF = (
    b"%PDF-1.4\n"
    b"1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n"
    b"2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj\n"
    b"3 0 obj<</Type/Page/Parent 2 0 R/MediaBox[0 0 612 792]"
    b"/Contents 4 0 R/Resources<</Font<</F1 5 0 R>>>>>>endobj\n"
    b"4 0 obj<</Length 120>>stream\n"
    b"BT /F1 12 Tf 72 720 Td "
    b"(TANDC SAMPLE PDF - we collect personal data and use arbitration.) Tj ET\n"
    b"endstream endobj\n"
    b"5 0 obj<</Type/Font/Subtype/Type1/BaseFont/Helvetica>>endobj\n"
    b"xref\n0 6\n0000000000 65535 f \n"
    b"0000000010 00000 n \n0000000054 00000 n \n0000000095 00000 n \n"
    b"0000000180 00000 n \n0000000345 00000 n \n"
    b"trailer<</Size 6/Root 1 0 R>>\nstartxref\n410\n%%EOF\n"
)

target = Path("tests/web/fixtures/sample.pdf")
target.parent.mkdir(parents=True, exist_ok=True)
target.write_bytes(RAW_PDF)
print(f"wrote {target} ({target.stat().st_size} bytes)")
```

Run it:

```bash
mkdir -p scripts
# write the file above as scripts/_make_sample_pdf.py first
PATH=/Users/nitin/anaconda3/envs/tandc/bin:$PATH python scripts/_make_sample_pdf.py
```

Expected: `wrote tests/web/fixtures/sample.pdf (NNN bytes)`

- [ ] **Step 3: Verify pypdf can read it back**

```bash
PATH=/Users/nitin/anaconda3/envs/tandc/bin:$PATH python -c "
from pypdf import PdfReader
r = PdfReader('tests/web/fixtures/sample.pdf')
print(r.pages[0].extract_text())
"
```

Expected output: contains the substring `TANDC SAMPLE PDF`. If pypdf cannot read it (e.g., raw-PDF byte offsets wrong on this version), regenerate with reportlab instead:

```bash
PATH=/Users/nitin/anaconda3/envs/tandc/bin:$PATH pip install reportlab
PATH=/Users/nitin/anaconda3/envs/tandc/bin:$PATH python -c "
from reportlab.pdfgen import canvas
c = canvas.Canvas('tests/web/fixtures/sample.pdf')
c.drawString(72, 720, 'TANDC SAMPLE PDF - we collect personal data and use arbitration.')
c.save()
"
PATH=/Users/nitin/anaconda3/envs/tandc/bin:$PATH python -c "
from pypdf import PdfReader
print(PdfReader('tests/web/fixtures/sample.pdf').pages[0].extract_text())
"
```

(reportlab is a one-shot generator; do NOT add it to project dependencies.)

- [ ] **Step 4: Commit**

```bash
git add tests/web/__init__.py tests/web/fixtures/sample.pdf scripts/_make_sample_pdf.py
git commit -m "tests: add web/ scaffold + sample.pdf fixture for PDF extractor"
```

---

## Task 6: Implement `web/pdf.py` extractor

**Files:**
- Create: `src/tandc/web/__init__.py` (empty)
- Create: `src/tandc/web/pdf.py`
- Create: `tests/web/test_pdf.py`

- [ ] **Step 1: Write failing tests**

Create `tests/web/test_pdf.py`:

```python
from pathlib import Path

import pytest

from tandc.errors import TandcExtractionError
from tandc.web.pdf import extract_pdf

FIXTURE = Path(__file__).parent / "fixtures" / "sample.pdf"


def test_extract_pdf_returns_sentinel_text():
    blob = FIXTURE.read_bytes()
    text = extract_pdf(blob)
    assert "TANDC SAMPLE PDF" in text
    assert "personal data" in text


def test_extract_pdf_normalises_unicode():
    """Smart quotes in PDF text should be normalised to ASCII (verbatim contract)."""
    # We don't have a unicode-bearing fixture; assert _normalise_text is in the path
    # by checking that the extractor doesn't strip ASCII.
    blob = FIXTURE.read_bytes()
    text = extract_pdf(blob)
    # ASCII apostrophe round-trips
    assert "we collect" in text


def test_extract_pdf_empty_blob_raises():
    with pytest.raises(TandcExtractionError):
        extract_pdf(b"")


def test_extract_pdf_corrupt_blob_raises():
    with pytest.raises(TandcExtractionError):
        extract_pdf(b"not a pdf at all, just random bytes")


def test_extract_pdf_empty_pages_raises(tmp_path):
    """A valid PDF that contains no text should raise TandcExtractionError."""
    # Use pypdf to write a blank single-page PDF
    from pypdf import PdfWriter
    w = PdfWriter()
    w.add_blank_page(width=612, height=792)
    blank = tmp_path / "blank.pdf"
    with blank.open("wb") as fh:
        w.write(fh)
    with pytest.raises(TandcExtractionError):
        extract_pdf(blank.read_bytes())
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
PATH=/Users/nitin/anaconda3/envs/tandc/bin:$PATH pytest tests/web/test_pdf.py -v
```

Expected: ImportError — `tandc.web` does not exist yet.

- [ ] **Step 3: Implement `web/__init__.py` and `web/pdf.py`**

Create `src/tandc/web/__init__.py`:

```python
"""tandc web layer — FastAPI app wrapping tandc.core.analyze()."""
```

Create `src/tandc/web/pdf.py`:

```python
"""PDF text extraction for the web layer's file-upload mode."""

from __future__ import annotations

import io
import logging

from pypdf import PdfReader
from pypdf.errors import PdfReadError

from tandc.core.extract import _normalise_text
from tandc.errors import TandcExtractionError

log = logging.getLogger(__name__)


def extract_pdf(blob: bytes) -> str:
    """Extract text from a PDF blob. Raises TandcExtractionError if empty/corrupt.

    Output is run through core.extract._normalise_text so the verbatim-quote
    contract from the analyzer continues to hold.
    """
    raw_bytes = len(blob)
    if not blob:
        raise TandcExtractionError(url=None, raw_bytes=0, extracted_chars=0)
    try:
        reader = PdfReader(io.BytesIO(blob))
        chunks = [page.extract_text() or "" for page in reader.pages]
    except PdfReadError as e:
        raise TandcExtractionError(
            url=None, raw_bytes=raw_bytes, extracted_chars=0
        ) from e
    except Exception as e:
        # pypdf raises various exceptions for malformed PDFs; treat all as extraction failures.
        log.warning("pypdf failed to parse PDF blob: %s", e)
        raise TandcExtractionError(
            url=None, raw_bytes=raw_bytes, extracted_chars=0
        ) from e
    text = _normalise_text("\n".join(chunks))
    if not text.strip():
        raise TandcExtractionError(
            url=None, raw_bytes=raw_bytes, extracted_chars=0
        )
    return text
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
PATH=/Users/nitin/anaconda3/envs/tandc/bin:$PATH pytest tests/web/test_pdf.py -v
```

Expected: all 5 tests pass.

- [ ] **Step 5: Commit**

```bash
git add src/tandc/web/__init__.py src/tandc/web/pdf.py tests/web/test_pdf.py
git commit -m "web: add pdf extractor with normalised output"
```

---

## Task 7: Implement `web/api.py` — request models + POST /analyze

**Files:**
- Create: `src/tandc/web/api.py`
- Create: `tests/web/test_api.py`

- [ ] **Step 1: Write failing tests**

Create `tests/web/test_api.py`:

```python
"""FastAPI route tests. core.analyze* is mocked — no live Claude here."""

from __future__ import annotations

import io
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from tandc.core.schema import (
    AnalysisReport,
    CoreFinding,
    Evidence,
    FetchMeta,
    FlagFinding,
    CORE_CATEGORIES,
    FLAG_CATEGORIES,
)
from tandc.errors import (
    TandcAnalysisError,
    TandcConfigError,
    TandcExtractionError,
    TandcFetchError,
)
from tandc.web.app import create_app

FIXTURE_PDF = Path(__file__).parent / "fixtures" / "sample.pdf"


def _fake_report(text: str = "test body") -> AnalysisReport:
    fm = FetchMeta(
        source="paste",
        url="https://example.com/terms",
        fetched_at=datetime.now(timezone.utc),
        http_status=None,
        content_type=None,
        content_type_was_plain=False,
        extractor=None,
        raw_bytes=len(text.encode("utf-8")),
        extracted_chars=len(text),
    )
    quote = text[:20]
    return AnalysisReport(
        model="claude-sonnet-4-6",
        analyzed_at=datetime.now(timezone.utc),
        input_hash="a" * 64,
        fetch_meta=fm,
        overall_risk="high",
        headline="Stub headline.",
        core_findings=[
            CoreFinding(
                category=c,
                severity="high",
                summary="stub",
                why_it_matters="stub",
                evidence=[Evidence(quote=quote, char_start=0, char_end=len(quote))],
            )
            for c in CORE_CATEGORIES
        ],
        flags=[
            FlagFinding(category=c, presence="present", note="stub")
            for c in FLAG_CATEGORIES
        ],
        notes=[],
    )


@pytest.fixture()
def client():
    return TestClient(create_app())


def test_post_analyze_url_mode_calls_analyze_with_url(client, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    fake = _fake_report()
    with patch("tandc.web.api.analyze") as m_analyze:
        m_analyze.return_value = (fake, tmp_path / "reports" / "stub")
        r = client.post(
            "/analyze",
            json={"url": "https://example.com/terms", "model": "sonnet"},
        )
    assert r.status_code == 200
    body = r.json()
    assert body["report"]["headline"] == "Stub headline."
    assert "report_dir" in body
    assert body["cache_hit"] is False
    m_analyze.assert_called_once()
    _, kwargs = m_analyze.call_args
    assert kwargs["url"] == "https://example.com/terms"


def test_post_analyze_paste_mode_calls_analyze_prepared(client, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    fake = _fake_report("Pasted terms body.")
    with patch("tandc.web.api.analyze_prepared") as m_prep:
        m_prep.return_value = (fake, tmp_path / "reports" / "stub")
        r = client.post(
            "/analyze",
            json={
                "text": "Pasted terms body.",
                "source_url": "https://example.com/terms",
                "model": "sonnet",
            },
        )
    assert r.status_code == 200
    m_prep.assert_called_once()
    _, kwargs = m_prep.call_args
    assert kwargs["text"] == "Pasted terms body."
    assert kwargs["fetch_meta"].source == "paste"
    assert kwargs["fetch_meta"].url == "https://example.com/terms"


def test_post_analyze_file_html_mode(client, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    fake = _fake_report("policy body")
    html = b"<html><body><p>We collect data. We use arbitration.</p></body></html>"
    with patch("tandc.web.api.analyze_prepared") as m_prep:
        m_prep.return_value = (fake, tmp_path / "reports" / "stub")
        r = client.post(
            "/analyze",
            files={"file": ("terms.html", html, "text/html")},
            data={"model": "sonnet"},
        )
    assert r.status_code == 200
    _, kwargs = m_prep.call_args
    assert kwargs["fetch_meta"].source == "file"
    assert kwargs["fetch_meta"].content_type == "text/html"


def test_post_analyze_file_txt_mode(client, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    fake = _fake_report("policy body")
    txt = b"These are the terms. We share data."
    with patch("tandc.web.api.analyze_prepared") as m_prep:
        m_prep.return_value = (fake, tmp_path / "reports" / "stub")
        r = client.post(
            "/analyze",
            files={"file": ("terms.txt", txt, "text/plain")},
        )
    assert r.status_code == 200
    _, kwargs = m_prep.call_args
    assert kwargs["fetch_meta"].source == "file"
    assert "These are the terms" in kwargs["text"]


def test_post_analyze_file_pdf_mode(client, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    fake = _fake_report("policy body")
    pdf_bytes = FIXTURE_PDF.read_bytes()
    with patch("tandc.web.api.analyze_prepared") as m_prep:
        m_prep.return_value = (fake, tmp_path / "reports" / "stub")
        r = client.post(
            "/analyze",
            files={"file": ("sample.pdf", pdf_bytes, "application/pdf")},
        )
    assert r.status_code == 200
    _, kwargs = m_prep.call_args
    assert "TANDC SAMPLE PDF" in kwargs["text"]


def test_post_analyze_file_unsupported_mime_returns_415(client):
    r = client.post(
        "/analyze",
        files={"file": ("img.png", b"\x89PNG\r\n\x1a\n...", "image/png")},
    )
    assert r.status_code == 415
    body = r.json()
    assert body["error"] == "UnsupportedMediaType"


def test_post_analyze_both_url_and_text_returns_422(client):
    r = client.post(
        "/analyze",
        json={"url": "https://example.com/x", "text": "y"},
    )
    assert r.status_code == 422


def test_post_analyze_neither_url_nor_text_returns_422(client):
    r = client.post("/analyze", json={"model": "sonnet"})
    assert r.status_code == 422


def test_post_analyze_fetch_error_returns_502(client, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    with patch("tandc.web.api.analyze") as m_analyze:
        m_analyze.side_effect = TandcFetchError(
            url="https://nope.invalid", status=None, message="dns failure"
        )
        r = client.post("/analyze", json={"url": "https://nope.invalid"})
    assert r.status_code == 502
    body = r.json()
    assert body["error"] == "TandcFetchError"
    assert "dns failure" in body["message"]


def test_post_analyze_extraction_error_returns_400(client, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    with patch("tandc.web.api.analyze") as m_analyze:
        m_analyze.side_effect = TandcExtractionError(
            url="https://example.com", raw_bytes=10, extracted_chars=0
        )
        r = client.post("/analyze", json={"url": "https://example.com"})
    assert r.status_code == 400
    assert r.json()["error"] == "TandcExtractionError"


def test_post_analyze_config_error_returns_503(client, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    with patch("tandc.web.api.analyze") as m_analyze:
        m_analyze.side_effect = TandcConfigError("ANTHROPIC_API_KEY not set")
        r = client.post("/analyze", json={"url": "https://example.com"})
    assert r.status_code == 503
    assert r.json()["error"] == "TandcConfigError"


def test_post_analyze_analysis_error_returns_500(client, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    with patch("tandc.web.api.analyze") as m_analyze:
        m_analyze.side_effect = TandcAnalysisError("malformed output twice")
        r = client.post("/analyze", json={"url": "https://example.com"})
    assert r.status_code == 500
    assert r.json()["error"] == "TandcAnalysisError"


def test_post_analyze_opus_and_no_cache_thread_through(client, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    fake = _fake_report()
    with patch("tandc.web.api.analyze") as m_analyze:
        m_analyze.return_value = (fake, tmp_path / "reports" / "stub")
        r = client.post(
            "/analyze",
            json={"url": "https://example.com/x", "model": "opus", "use_cache": False},
        )
    assert r.status_code == 200
    from tandc.core.analyzer import MODEL_OPUS
    _, kwargs = m_analyze.call_args
    assert kwargs["model"] == MODEL_OPUS
    assert kwargs["use_cache"] is False


def test_get_root_returns_html_form(client):
    r = client.get("/")
    assert r.status_code == 200
    assert "text/html" in r.headers["content-type"]
    assert "tandc" in r.text.lower()
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
PATH=/Users/nitin/anaconda3/envs/tandc/bin:$PATH pytest tests/web/test_api.py -v
```

Expected: ImportError — `tandc.web.app` / `tandc.web.api` do not exist yet.

- [ ] **Step 3: Implement `web/api.py`**

Create `src/tandc/web/api.py`:

```python
"""POST /analyze: dispatch URL / paste / file inputs into core analyze pipeline."""

from __future__ import annotations

import logging
from pathlib import Path

from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile
from pydantic import BaseModel, Field, model_validator

from tandc.core import analyze, analyze_prepared
from tandc.core.analyzer import MODEL_OPUS, MODEL_SONNET
from tandc.core.loader import text_to_meta
from tandc.core.paths import cache_key, slug_for_url
from tandc.web.pdf import extract_pdf

log = logging.getLogger(__name__)

router = APIRouter()

ALLOWED_MIME = {"text/html", "text/plain", "application/pdf"}


class JsonBody(BaseModel):
    """Body for URL or paste mode. Exactly one of url/text must be set."""

    url: str | None = None
    text: str | None = None
    source_url: str | None = None
    model: str = Field(default="sonnet", pattern=r"^(sonnet|opus)$")
    use_cache: bool = True

    @model_validator(mode="after")
    def _exactly_one_of_url_text(self) -> "JsonBody":
        if (self.url is None) == (self.text is None):
            raise ValueError("exactly one of 'url' or 'text' must be provided")
        return self


def _model_id(name: str) -> str:
    return MODEL_OPUS if name == "opus" else MODEL_SONNET


def _serialize(report, rdir: Path | None, cache_hit: bool = False) -> dict:
    return {
        "report": report.model_dump(mode="json"),
        "report_dir": str(rdir.resolve()) if rdir else None,
        "cache_hit": cache_hit,
    }


@router.post("/analyze")
async def post_analyze(request: Request):
    content_type = (request.headers.get("content-type") or "").lower()

    if content_type.startswith("application/json"):
        raw = await request.json()
        body = JsonBody(**raw)
        return _dispatch_json(body)

    if content_type.startswith("multipart/form-data"):
        form = await request.form()
        return await _dispatch_multipart(form)

    raise HTTPException(
        status_code=415,
        detail={
            "error": "UnsupportedMediaType",
            "message": f"unsupported Content-Type: {content_type!r}",
        },
    )


def _dispatch_json(body: JsonBody) -> dict:
    model = _model_id(body.model)
    output_base = Path.cwd()
    if body.url is not None:
        report, rdir = analyze(
            url=body.url,
            model=model,
            use_cache=body.use_cache,
            output_base=output_base,
        )
        return _serialize(report, rdir)
    text, fetch_meta = text_to_meta(
        text=body.text or "",
        source="paste",
        source_url=body.source_url,
    )
    slug = _slug_for_paste(text, model, body.source_url)
    report, rdir = analyze_prepared(
        text=text,
        fetch_meta=fetch_meta,
        slug=slug,
        model=model,
        use_cache=body.use_cache,
        output_base=output_base,
    )
    return _serialize(report, rdir)


async def _dispatch_multipart(form) -> dict:
    upload: UploadFile | None = form.get("file")
    if upload is None:
        raise HTTPException(
            status_code=422,
            detail={"error": "ValidationError", "message": "'file' field is required"},
        )
    mime = (upload.content_type or "").lower()
    if mime not in ALLOWED_MIME:
        raise HTTPException(
            status_code=415,
            detail={
                "error": "UnsupportedMediaType",
                "message": (
                    f"file MIME {mime!r} not supported; "
                    f"allowed: {sorted(ALLOWED_MIME)}"
                ),
            },
        )

    blob = await upload.read()
    if mime == "application/pdf":
        text = extract_pdf(blob)
    elif mime == "text/html":
        from tandc.core.extract import extract_text
        extracted, _extractor = extract_text(blob.decode("utf-8", errors="replace"), mime)
        if extracted is None:
            from tandc.errors import TandcExtractionError
            raise TandcExtractionError(url=None, raw_bytes=len(blob), extracted_chars=0)
        text = extracted
    else:  # text/plain
        from tandc.core.extract import _normalise_text
        text = _normalise_text(blob.decode("utf-8", errors="replace"))

    _text, fetch_meta = text_to_meta(
        text=text,
        source="file",
        filename=upload.filename,
        content_type=mime,
    )

    model_name = form.get("model", "sonnet")
    use_cache_raw = form.get("use_cache", "true")
    use_cache = str(use_cache_raw).lower() not in {"false", "0", "no"}
    model = _model_id(model_name)

    slug = _slug_for_file(upload.filename, _text, model)
    report, rdir = analyze_prepared(
        text=_text,
        fetch_meta=fetch_meta,
        slug=slug,
        model=model,
        use_cache=use_cache,
        output_base=Path.cwd(),
    )
    return _serialize(report, rdir)


def _slug_for_paste(text: str, model: str, source_url: str | None) -> str:
    if source_url:
        try:
            return slug_for_url(source_url)
        except Exception:
            pass
    return f"paste-{cache_key(text, model)[:8]}"


def _slug_for_file(filename: str | None, text: str, model: str) -> str:
    import re
    if filename:
        stem = re.sub(r"[^a-z0-9]+", "-", filename.lower()).strip("-") or "file"
        return f"file-{stem[:48]}"
    return f"file-{cache_key(text, model)[:8]}"
```

- [ ] **Step 4: Note: tests reference `create_app` from `web.app`**

The tests use `from tandc.web.app import create_app`. That module is built in Task 8 — these tests will still fail until Task 8 is done. That is intentional (tests and impl arrive together as a unit). Do NOT run the tests at the end of this step; run them at the end of Task 8.

- [ ] **Step 5: Commit api.py alone**

```bash
git add src/tandc/web/api.py tests/web/test_api.py
git commit -m "web: add POST /analyze router with URL/paste/file dispatch (app.py pending)"
```

---

## Task 8: Implement `web/app.py` — FastAPI app factory + exception handlers + static mount

**Files:**
- Create: `src/tandc/web/app.py`

- [ ] **Step 1: Create the app factory**

Create `src/tandc/web/app.py`:

```python
"""FastAPI app factory: mounts api router, static files, exception handlers."""

from __future__ import annotations

import logging
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from tandc.errors import (
    TandcAnalysisError,
    TandcConfigError,
    TandcError,
    TandcExtractionError,
    TandcFetchError,
)
from tandc.web.api import router as analyze_router

log = logging.getLogger(__name__)

_STATIC_DIR = Path(__file__).parent / "static"


def create_app() -> FastAPI:
    app = FastAPI(
        title="tandc",
        description="Local UI for the Terms & Conditions risk analyzer.",
        version="0.1.0",
    )
    app.include_router(analyze_router)

    _register_exception_handlers(app)

    @app.get("/", include_in_schema=False)
    def root() -> FileResponse:
        return FileResponse(_STATIC_DIR / "index.html")

    app.mount(
        "/static",
        StaticFiles(directory=_STATIC_DIR),
        name="static",
    )
    return app


def _error_body(name: str, message: str, detail: dict | None = None) -> dict:
    body = {"error": name, "message": message}
    if detail is not None:
        body["detail"] = detail
    return body


def _register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(HTTPException)
    async def _http_exc(request: Request, exc: HTTPException):
        # If the detail is already a structured error dict, pass it through.
        if isinstance(exc.detail, dict) and "error" in exc.detail:
            return JSONResponse(status_code=exc.status_code, content=exc.detail)
        return JSONResponse(
            status_code=exc.status_code,
            content=_error_body("HTTPException", str(exc.detail)),
        )

    @app.exception_handler(TandcFetchError)
    async def _fetch(request: Request, exc: TandcFetchError):
        log.warning("fetch error: %s", exc)
        return JSONResponse(
            status_code=502,
            content=_error_body(
                "TandcFetchError",
                str(exc),
                {"url": exc.url, "status": exc.status},
            ),
        )

    @app.exception_handler(TandcExtractionError)
    async def _extract(request: Request, exc: TandcExtractionError):
        log.warning("extraction error: %s", exc)
        return JSONResponse(
            status_code=400,
            content=_error_body(
                "TandcExtractionError",
                str(exc),
                {
                    "url": exc.url,
                    "raw_bytes": exc.raw_bytes,
                    "extracted_chars": exc.extracted_chars,
                },
            ),
        )

    @app.exception_handler(TandcConfigError)
    async def _config(request: Request, exc: TandcConfigError):
        log.warning("config error: %s", exc)
        return JSONResponse(
            status_code=503,
            content=_error_body("TandcConfigError", str(exc)),
        )

    @app.exception_handler(TandcAnalysisError)
    async def _analysis(request: Request, exc: TandcAnalysisError):
        log.warning("analysis error: %s", exc)
        return JSONResponse(
            status_code=500,
            content=_error_body("TandcAnalysisError", str(exc)),
        )

    @app.exception_handler(TandcError)
    async def _catchall(request: Request, exc: TandcError):
        log.warning("tandc error (catch-all): %s", exc)
        return JSONResponse(
            status_code=500,
            content=_error_body("TandcError", str(exc)),
        )
```

- [ ] **Step 2: Provide a placeholder `static/index.html` so tests pass**

The static folder must exist with at least a placeholder so `StaticFiles(directory=...)` doesn't 500 and `GET /` returns *something* containing "tandc". Real frontend lands in Task 9.

```bash
mkdir -p src/tandc/web/static
```

Create `src/tandc/web/static/index.html`:

```html
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>tandc — placeholder</title>
</head>
<body>
  <h1>tandc</h1>
  <p>Frontend pending (Task 9 of plan).</p>
</body>
</html>
```

- [ ] **Step 3: Run the Task 7 tests (now satisfiable)**

```bash
PATH=/Users/nitin/anaconda3/envs/tandc/bin:$PATH pytest tests/web/test_api.py -v
```

Expected: all 14 tests pass.

- [ ] **Step 4: Run the full unit suite to ensure no regression**

```bash
PATH=/Users/nitin/anaconda3/envs/tandc/bin:$PATH pytest tests/ -v -m "not slow"
```

Expected: all tests pass (88 original + new web + new schema/loader/core tests).

- [ ] **Step 5: Commit**

```bash
git add src/tandc/web/app.py src/tandc/web/static/index.html
git commit -m "web: add FastAPI app factory + exception handlers + placeholder index"
```

---

## Task 9: Vanilla-JS frontend (index.html, tandc.css, tandc.js)

**Files:**
- Overwrite: `src/tandc/web/static/index.html`
- Create: `src/tandc/web/static/tandc.css`
- Create: `src/tandc/web/static/tandc.js`

- [ ] **Step 1: Replace index.html with the real form**

Overwrite `src/tandc/web/static/index.html`:

```html
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>tandc — T&amp;C risk analyzer</title>
  <link rel="stylesheet" href="/static/tandc.css">
</head>
<body>
  <header>
    <h1>tandc</h1>
    <p class="tagline">Terms &amp; Conditions risk analyzer</p>
  </header>

  <main>
    <form id="analyze-form">
      <fieldset>
        <legend>Input</legend>

        <div class="mode-row">
          <label><input type="radio" name="mode" value="url" checked> URL</label>
          <label><input type="radio" name="mode" value="paste"> Paste</label>
          <label><input type="radio" name="mode" value="file"> File</label>
        </div>

        <div class="mode-panel" data-panel="url">
          <input type="url" id="input-url" placeholder="https://example.com/terms">
        </div>

        <div class="mode-panel" data-panel="paste" hidden>
          <textarea id="input-paste" rows="10"
                    placeholder="Paste policy text here…"></textarea>
          <input type="url" id="input-source-url"
                 placeholder="(optional) source URL for metadata">
        </div>

        <div class="mode-panel" data-panel="file" hidden>
          <input type="file" id="input-file"
                 accept=".html,.htm,.txt,.pdf,text/html,text/plain,application/pdf">
        </div>
      </fieldset>

      <fieldset class="options">
        <label><input type="checkbox" id="use-cache" checked> use cache</label>
        <label>Model:
          <label><input type="radio" name="model" value="sonnet" checked> Sonnet</label>
          <label><input type="radio" name="model" value="opus"> Opus</label>
        </label>
      </fieldset>

      <button type="submit" id="submit-btn">Analyze</button>
    </form>

    <section id="status" aria-live="polite"></section>
    <section id="result"></section>
  </main>

  <script src="/static/tandc.js"></script>
</body>
</html>
```

- [ ] **Step 2: Add CSS**

Create `src/tandc/web/static/tandc.css`:

```css
:root {
  --bg: #fafafa;
  --fg: #111;
  --muted: #666;
  --border: #ddd;
  --accent: #1456b8;
  --sev-low: #2a7a2a;
  --sev-medium: #b8860b;
  --sev-high: #c0392b;
  --sev-critical: #7a0000;
  --flag-present: #c0392b;
  --flag-absent: #2a7a2a;
  --flag-unclear: #666;
  --error-bg: #fdecea;
  --error-fg: #7a0000;
}

* { box-sizing: border-box; }

body {
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
  background: var(--bg);
  color: var(--fg);
  max-width: 900px;
  margin: 2rem auto;
  padding: 0 1rem;
  line-height: 1.5;
}

header h1 { margin-bottom: 0; }
.tagline { color: var(--muted); margin-top: 0.25rem; }

fieldset { border: 1px solid var(--border); margin: 1rem 0; padding: 1rem; }
legend { padding: 0 0.5rem; color: var(--muted); }

.mode-row { display: flex; gap: 1.5rem; margin-bottom: 1rem; }
.mode-panel { display: flex; flex-direction: column; gap: 0.5rem; }
.mode-panel input[type=url], .mode-panel textarea {
  width: 100%; padding: 0.5rem; font-size: 1rem;
  border: 1px solid var(--border); border-radius: 4px;
}
.options { display: flex; gap: 1.5rem; align-items: center; }

button#submit-btn {
  background: var(--accent); color: white; border: 0;
  padding: 0.75rem 2rem; font-size: 1rem; border-radius: 4px;
  cursor: pointer;
}
button#submit-btn:disabled { opacity: 0.5; cursor: wait; }

#status { margin: 1rem 0; color: var(--muted); }
#status.error { color: var(--error-fg); background: var(--error-bg);
                padding: 0.75rem; border-radius: 4px; }

.headline { font-size: 1.25rem; font-weight: 600; margin: 1rem 0 0.5rem; }
.meta { color: var(--muted); font-size: 0.9rem; }
.meta a { color: var(--accent); }

.sev-low      { color: var(--sev-low);      font-weight: 600; }
.sev-medium   { color: var(--sev-medium);   font-weight: 600; }
.sev-high     { color: var(--sev-high);     font-weight: 600; }
.sev-critical { color: var(--sev-critical); font-weight: 700; }

table.core { width: 100%; border-collapse: collapse; margin: 1rem 0; }
table.core th, table.core td {
  border: 1px solid var(--border); padding: 0.5rem; text-align: left;
  vertical-align: top;
}
table.core th { background: #f0f0f0; }

details.evidence { margin-top: 0.5rem; }
details.evidence blockquote {
  border-left: 3px solid var(--border); margin: 0.5rem 0;
  padding-left: 0.75rem; color: #333;
}

.flags { display: flex; flex-wrap: wrap; gap: 0.5rem; margin: 1rem 0; }
.flag-chip {
  border: 1px solid var(--border); padding: 0.25rem 0.75rem;
  border-radius: 999px; font-size: 0.9rem;
}
.flag-present { border-color: var(--flag-present); color: var(--flag-present); }
.flag-absent  { border-color: var(--flag-absent);  color: var(--flag-absent); }
.flag-unclear { border-color: var(--flag-unclear); color: var(--flag-unclear); }
```

- [ ] **Step 3: Add JS**

Create `src/tandc/web/static/tandc.js`:

```javascript
"use strict";

const form = document.getElementById("analyze-form");
const status = document.getElementById("status");
const result = document.getElementById("result");
const submitBtn = document.getElementById("submit-btn");
const panels = document.querySelectorAll(".mode-panel");

document.querySelectorAll('input[name="mode"]').forEach((radio) => {
  radio.addEventListener("change", () => {
    panels.forEach((p) => {
      p.hidden = p.dataset.panel !== radio.value;
    });
  });
});

form.addEventListener("submit", async (e) => {
  e.preventDefault();
  status.className = "";
  status.textContent = "Analyzing… (~30 s for first run)";
  result.innerHTML = "";
  submitBtn.disabled = true;

  const mode = document.querySelector('input[name="mode"]:checked').value;
  const model = document.querySelector('input[name="model"]:checked').value;
  const useCache = document.getElementById("use-cache").checked;

  try {
    let response;
    if (mode === "url") {
      const url = document.getElementById("input-url").value.trim();
      response = await fetch("/analyze", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ url, model, use_cache: useCache }),
      });
    } else if (mode === "paste") {
      const text = document.getElementById("input-paste").value;
      const sourceUrl = document.getElementById("input-source-url").value.trim();
      const body = { text, model, use_cache: useCache };
      if (sourceUrl) body.source_url = sourceUrl;
      response = await fetch("/analyze", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
    } else {
      const fileInput = document.getElementById("input-file");
      if (!fileInput.files[0]) {
        throw new Error("Select a file to upload.");
      }
      const fd = new FormData();
      fd.append("file", fileInput.files[0]);
      fd.append("model", model);
      fd.append("use_cache", useCache ? "true" : "false");
      response = await fetch("/analyze", { method: "POST", body: fd });
    }

    const data = await response.json();
    if (!response.ok) {
      renderError(data);
    } else {
      renderReport(data);
    }
  } catch (err) {
    renderError({ error: "ClientError", message: err.message });
  } finally {
    submitBtn.disabled = false;
    status.textContent = "";
  }
});

function escapeHtml(s) {
  return String(s ?? "")
    .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;").replace(/'/g, "&#39;");
}

function sevClass(s) { return `sev-${s}`; }

function renderError(body) {
  status.className = "error";
  status.textContent = `${body.error || "Error"}: ${body.message || "(no message)"}`;
}

function renderReport(data) {
  const r = data.report;
  const dir = data.report_dir;

  const parts = [];
  parts.push(`<div class="headline">${escapeHtml(r.headline)}</div>`);
  parts.push(
    `<div class="meta">Overall risk: <span class="${sevClass(r.overall_risk)}">` +
    `${escapeHtml(r.overall_risk.toUpperCase())}</span> &nbsp; Model: ${escapeHtml(r.model)}` +
    ` &nbsp; Taxonomy: ${escapeHtml(r.taxonomy_version)}</div>`
  );
  if (dir) {
    parts.push(
      `<div class="meta">Wrote: <a href="file://${escapeHtml(dir)}">${escapeHtml(dir)}</a>` +
      (data.cache_hit ? " <em>(cache hit)</em>" : "") + "</div>"
    );
  }

  parts.push("<h2>Core findings</h2>");
  parts.push("<table class='core'><thead><tr><th>Category</th><th>Severity</th>" +
             "<th>Summary &amp; why it matters</th></tr></thead><tbody>");
  for (const f of r.core_findings) {
    const evList = (f.evidence || [])
      .map((e) => `<blockquote>${escapeHtml(e.quote)}</blockquote>`).join("");
    parts.push(
      `<tr><td>${escapeHtml(f.category)}</td>` +
      `<td class="${sevClass(f.severity)}">${escapeHtml(f.severity.toUpperCase())}</td>` +
      `<td><strong>${escapeHtml(f.summary)}</strong><br>` +
      `<span class="meta">${escapeHtml(f.why_it_matters)}</span>` +
      `<details class="evidence"><summary>Evidence</summary>${evList}</details></td></tr>`
    );
  }
  parts.push("</tbody></table>");

  parts.push("<h2>Flags</h2><div class='flags'>");
  for (const f of r.flags) {
    parts.push(
      `<span class="flag-chip flag-${f.presence}" title="${escapeHtml(f.note)}">` +
      `${escapeHtml(f.category)}: ${escapeHtml(f.presence)}</span>`
    );
  }
  parts.push("</div>");

  if (r.notes && r.notes.length) {
    parts.push("<h2>Notes</h2><ul>");
    for (const n of r.notes) parts.push(`<li>${escapeHtml(n)}</li>`);
    parts.push("</ul>");
  }

  result.innerHTML = parts.join("\n");
}
```

- [ ] **Step 4: Sanity-check static files via TestClient**

```bash
PATH=/Users/nitin/anaconda3/envs/tandc/bin:$PATH python -c "
from fastapi.testclient import TestClient
from tandc.web.app import create_app
c = TestClient(create_app())
r1 = c.get('/')
assert r1.status_code == 200, r1.status_code
assert 'analyze-form' in r1.text, 'form id missing'
r2 = c.get('/static/tandc.css')
assert r2.status_code == 200, r2.status_code
r3 = c.get('/static/tandc.js')
assert r3.status_code == 200, r3.status_code
print('static ok')
"
```

Expected: `static ok`

- [ ] **Step 5: Commit**

```bash
git add src/tandc/web/static/index.html src/tandc/web/static/tandc.css src/tandc/web/static/tandc.js
git commit -m "web: vanilla-JS frontend (URL/paste/file form + result render)"
```

---

## Task 10: Implement `web/serve.py` — uvicorn launcher + pre-flight

**Files:**
- Create: `src/tandc/web/serve.py`
- Create: `tests/web/test_serve.py`

- [ ] **Step 1: Write failing tests**

Create `tests/web/test_serve.py`:

```python
"""Behavioural tests for the uvicorn launcher wrapper (no real socket bind)."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from tandc.errors import TandcConfigError
from tandc.web import serve as serve_mod


def test_run_raises_config_error_without_api_key(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    with pytest.raises(TandcConfigError):
        serve_mod.run(host="127.0.0.1", port=8765, reload=False)


def test_run_invokes_uvicorn_with_args(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "x")
    with patch.object(serve_mod, "uvicorn") as mock_uv:
        serve_mod.run(host="127.0.0.1", port=9999, reload=False)
    mock_uv.run.assert_called_once()
    _, kwargs = mock_uv.run.call_args
    assert kwargs["host"] == "127.0.0.1"
    assert kwargs["port"] == 9999
    assert kwargs["reload"] is False


def test_run_reload_uses_import_string(monkeypatch):
    """uvicorn requires the app target as an import string when reload=True."""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "x")
    with patch.object(serve_mod, "uvicorn") as mock_uv:
        serve_mod.run(host="127.0.0.1", port=8765, reload=True)
    args, _ = mock_uv.run.call_args
    # First positional arg is the app target
    assert args[0] == "tandc.web.serve:app"


def test_run_translates_oserror_to_exit_5(monkeypatch):
    """Port-in-use surfaces as TandcServerError with the exit-5 hint."""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "x")

    def _raise(*a, **kw):
        raise OSError(48, "Address already in use")

    with patch.object(serve_mod, "uvicorn") as mock_uv:
        mock_uv.run.side_effect = _raise
        with pytest.raises(serve_mod.TandcServerPortInUse):
            serve_mod.run(host="127.0.0.1", port=8765, reload=False)
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
PATH=/Users/nitin/anaconda3/envs/tandc/bin:$PATH pytest tests/web/test_serve.py -v
```

Expected: ImportError — `tandc.web.serve` does not exist yet.

- [ ] **Step 3: Implement `web/serve.py`**

Create `src/tandc/web/serve.py`:

```python
"""uvicorn launcher for `tandc serve`. Translates env/socket failures into TandcErrors."""

from __future__ import annotations

import logging
import os

import uvicorn

from tandc.errors import TandcConfigError, TandcError
from tandc.web.app import create_app

log = logging.getLogger(__name__)


class TandcServerPortInUse(TandcError):
    """The port we asked uvicorn to bind to is already in use."""


# Module-level app for uvicorn --reload, which requires an import string.
app = create_app()


def run(*, host: str, port: int, reload: bool) -> None:
    """Pre-flight + launch uvicorn. Raises TandcConfigError if no API key.

    Translates OSError(EADDRINUSE) into TandcServerPortInUse so the CLI can
    exit 5 cleanly.
    """
    if not os.environ.get("ANTHROPIC_API_KEY"):
        raise TandcConfigError(
            "ANTHROPIC_API_KEY is not set — export it before running `tandc serve`"
        )

    target = "tandc.web.serve:app" if reload else app
    log.info("tandc serve listening on http://%s:%d", host, port)
    try:
        uvicorn.run(target, host=host, port=port, reload=reload)
    except OSError as e:
        if e.errno in (48, 98):  # EADDRINUSE on darwin / linux
            raise TandcServerPortInUse(
                f"port {port} is already in use on {host}; pick another with --port"
            ) from e
        raise
```

- [ ] **Step 4: Run serve tests + full unit suite**

```bash
PATH=/Users/nitin/anaconda3/envs/tandc/bin:$PATH pytest tests/web/test_serve.py -v
PATH=/Users/nitin/anaconda3/envs/tandc/bin:$PATH pytest tests/ -m "not slow"
```

Expected: serve tests pass; full suite still green.

- [ ] **Step 5: Commit**

```bash
git add src/tandc/web/serve.py tests/web/test_serve.py
git commit -m "web: add uvicorn launcher with API-key pre-flight + port-in-use trap"
```

---

## Task 11: Add `tandc serve` CLI subcommand

**Files:**
- Modify: `src/tandc/cli.py`
- Create: `tests/web/test_cli_serve.py`

- [ ] **Step 1: Write failing tests**

Create `tests/web/test_cli_serve.py`:

```python
from unittest.mock import patch

from typer.testing import CliRunner

from tandc.cli import app


runner = CliRunner()


def test_serve_command_invokes_web_run_with_defaults(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "x")
    with patch("tandc.cli._serve_run") as m_run:
        result = runner.invoke(app, ["serve"])
    assert result.exit_code == 0, result.output
    m_run.assert_called_once_with(host="127.0.0.1", port=8765, reload=False)


def test_serve_command_passes_host_port_reload(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "x")
    with patch("tandc.cli._serve_run") as m_run:
        result = runner.invoke(
            app, ["serve", "--host", "0.0.0.0", "--port", "9000", "--reload"]
        )
    assert result.exit_code == 0, result.output
    m_run.assert_called_once_with(host="0.0.0.0", port=9000, reload=True)


def test_serve_command_exits_4_on_missing_api_key(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    from tandc.errors import TandcConfigError
    with patch("tandc.cli._serve_run") as m_run:
        m_run.side_effect = TandcConfigError("ANTHROPIC_API_KEY is not set")
        result = runner.invoke(app, ["serve"])
    assert result.exit_code == 4, result.output
    assert "config error" in result.output.lower()


def test_serve_command_exits_5_on_port_in_use(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "x")
    from tandc.web.serve import TandcServerPortInUse
    with patch("tandc.cli._serve_run") as m_run:
        m_run.side_effect = TandcServerPortInUse("port 8765 already in use")
        result = runner.invoke(app, ["serve"])
    assert result.exit_code == 5, result.output
    assert "port" in result.output.lower()
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
PATH=/Users/nitin/anaconda3/envs/tandc/bin:$PATH pytest tests/web/test_cli_serve.py -v
```

Expected: `No such command 'serve'`.

- [ ] **Step 3: Add `serve` subcommand to `cli.py`**

Append to `src/tandc/cli.py`:

```python
# --- web serve subcommand -----------------------------------------------------

def _serve_run(*, host: str, port: int, reload: bool) -> None:
    """Indirection so tests can patch the entry point without touching uvicorn."""
    from tandc.web.serve import run as _run
    _run(host=host, port=port, reload=reload)


@app.command()
def serve(
    host: str = typer.Option("127.0.0.1", "--host", help="Bind address"),
    port: int = typer.Option(8765, "--port", help="Listen port"),
    reload: bool = typer.Option(False, "--reload", help="uvicorn auto-reload"),
    debug: bool = typer.Option(False, "--debug", help="Enable DEBUG logging"),
) -> None:
    """Launch the local web UI at http://host:port."""
    _setup_logging(debug)
    try:
        _serve_run(host=host, port=port, reload=reload)
    except TandcConfigError as e:
        err_console.print(f"[red]config error:[/red] {e}")
        raise typer.Exit(code=4)
    except Exception as e:
        # TandcServerPortInUse and any other TandcError live here. We import lazily
        # so cli import doesn't pull in uvicorn unnecessarily.
        from tandc.web.serve import TandcServerPortInUse
        if isinstance(e, TandcServerPortInUse):
            err_console.print(f"[red]port error:[/red] {e}")
            raise typer.Exit(code=5)
        if isinstance(e, TandcError):
            err_console.print(f"[red]error:[/red] {e}")
            raise typer.Exit(code=1)
        raise
```

- [ ] **Step 4: Run cli tests + full unit suite**

```bash
PATH=/Users/nitin/anaconda3/envs/tandc/bin:$PATH pytest tests/web/test_cli_serve.py -v
PATH=/Users/nitin/anaconda3/envs/tandc/bin:$PATH pytest tests/ -m "not slow"
```

Expected: all green.

- [ ] **Step 5: Commit**

```bash
git add src/tandc/cli.py tests/web/test_cli_serve.py
git commit -m "cli: add 'tandc serve' subcommand with exit codes 4/5"
```

---

## Task 12: Manual end-to-end smoke (browser + curl)

This is a one-shot manual verification. Capture the output under `docs/test_runs/` per the standing test-log rule.

**Files:**
- Append: `docs/TEST_LOG.md`
- Create: `docs/test_runs/2026-05-2x_v2_e2e_<short>.txt` (one file per run)

- [ ] **Step 1: Start the server in the background**

```bash
PATH=/Users/nitin/anaconda3/envs/tandc/bin:$PATH ANTHROPIC_API_KEY="$ANTHROPIC_API_KEY" \
  tandc serve --port 8765 2>&1 | tee docs/test_runs/2026-05-2x_v2_serve_start.txt &
SERVE_PID=$!
sleep 2
```

Expected: log shows `tandc serve listening on http://127.0.0.1:8765`.

- [ ] **Step 2: curl `GET /` and `GET /docs`**

```bash
curl -sS http://127.0.0.1:8765/ | head -5
curl -sS http://127.0.0.1:8765/docs | head -5
```

Expected: index HTML containing `analyze-form`; `/docs` returns the FastAPI OpenAPI UI HTML.

- [ ] **Step 3: curl URL mode (uses cache hit if available)**

```bash
curl -sS -X POST http://127.0.0.1:8765/analyze \
  -H 'Content-Type: application/json' \
  -d '{"url":"https://www.anthropic.com/legal/consumer-terms","use_cache":true}' \
  | python -m json.tool | head -40 \
  | tee docs/test_runs/2026-05-2x_v2_curl_url.txt
```

Expected: JSON with `report.headline`, `report.core_findings[]`, `report_dir`, `cache_hit`.

- [ ] **Step 4: curl paste mode**

```bash
curl -sS -X POST http://127.0.0.1:8765/analyze \
  -H 'Content-Type: application/json' \
  -d '{"text":"These terms grant us a perpetual worldwide license to your content. Disputes shall be resolved by binding arbitration; class actions are waived.","source_url":"https://example.com/synthetic"}' \
  | python -m json.tool | head -40 \
  | tee docs/test_runs/2026-05-2x_v2_curl_paste.txt
```

Expected: JSON 200 with non-empty report; `content_licensing` flag `present`.

- [ ] **Step 5: curl file upload (PDF)**

```bash
curl -sS -X POST http://127.0.0.1:8765/analyze \
  -F "file=@tests/web/fixtures/sample.pdf;type=application/pdf" \
  | python -m json.tool | head -40 \
  | tee docs/test_runs/2026-05-2x_v2_curl_pdf.txt
```

Expected: JSON 200 with report; `fetch_meta.source == "file"` in the cached report.

- [ ] **Step 6: Browser smoke**

Open `http://127.0.0.1:8765/` in a browser. Submit:
1. URL: `https://www.anthropic.com/legal/consumer-terms` → rendered table appears within ~30 s (or <1 s if cache hit). Severity colours visible.
2. Paste: arbitrary T&C clause → rendered report.
3. File: select `tests/web/fixtures/sample.pdf` → rendered report.
4. Force an error: submit a URL like `https://nope.invalid.example/` → red error banner with `TandcFetchError`.

Take a screenshot of the rendered report (any) and save as `docs/test_runs/2026-05-2x_v2_browser_screenshot.png` (optional).

- [ ] **Step 7: Stop the server**

```bash
kill $SERVE_PID || true
wait $SERVE_PID 2>/dev/null || true
```

- [ ] **Step 8: Append summary row to `docs/TEST_LOG.md`**

```
| 2026-05-2x HH:MM | tandc | s1v2 | t12 | manual e2e (curl + browser) | n/a | 0 | 0 | 0 | NN | curl: url/paste/pdf 200; browser: 3 modes ok, error banner ok | <commit> | docs/test_runs/2026-05-2x_v2_curl_*.txt |
```

- [ ] **Step 9: Commit the run logs**

```bash
git add docs/TEST_LOG.md docs/test_runs/2026-05-2x_v2_*.txt
git commit -m "test: stage 1 v2 manual e2e — 3 input modes + error mapping verified"
```

---

## Task 13: Update tracking files and mark v2 shipped

**Files:**
- Modify: `DONE.md`
- Modify: `PLAN.md`
- Modify: `CLAUDE.md`

- [ ] **Step 1: Append a v2 ship entry to `DONE.md`**

Insert after the existing `2026-05-21 — Stage 1 v2 design approved` section:

```markdown
## 2026-05-2x — Stage 1 v2 shipped

Implemented the local web UI end-to-end:

- `tandc serve [--host 127.0.0.1] [--port 8765] [--reload]`
- FastAPI app at `tandc.web.app:create_app`; single `POST /analyze`
  endpoint dispatching three input modes (URL / paste / file upload)
- File upload accepts `text/html`, `text/plain`, `application/pdf`;
  PDF extraction via pypdf
- Vanilla-JS frontend at `/`; FastAPI-generated OpenAPI at `/docs`
- Errors mapped to documented HTTP codes (400/415/422/500/502/503)
  via FastAPI exception handlers
- Pre-flight refuses to start without `ANTHROPIC_API_KEY` (exit 4);
  port-in-use traps to exit 5
- Core change: `core.analyze()` refactored to a thin wrapper over a
  new `core.analyze_prepared(text, fetch_meta, slug, ...)` so the
  web layer reuses the cache + Claude + artefact-write pipeline
  without re-running the loader stage
- `FetchMeta.source` extended with `"paste"` and `"file"` variants
- Test suite: <NN> unit tests (FastAPI TestClient, mocked Claude) +
  manual e2e (curl + browser) for all three input modes
```

(Replace `<NN>` after running the final test count.)

- [ ] **Step 2: Update `PLAN.md` Current Status**

In `PLAN.md`, replace the "Stage 1 v2 (local web UI) — design approved" line with:

```markdown
**Stage 1 v2 (local web UI) — shipped 2026-05-2x.** Merged at
`<commit>`. <NN> unit tests + manual e2e green. Spec:
`docs/superpowers/specs/2026-05-21-stage1-v2-web-ui-design.md`.
Plan: `docs/superpowers/plans/2026-05-21-stage1-v2-web-ui.md`.
```

Also update the Stage 1 heading from "v2 (local web UI): design approved, implementation pending" to "v2 (local web UI): shipped 2026-05-2x."

- [ ] **Step 3: Update `CLAUDE.md`**

Edit the **Shipped** and **Active** blocks at the bottom:

```markdown
**Shipped**:
- Stage 1 v1 (CLI) — 2026-05-20, merged to `main` at `e2cd027`.
- Stage 1 v2 (local web UI) — 2026-05-2x, merged at `<commit>`.

**Active**:
- Stage 2 brainstorm — fresh Chrome extension vs extend Claude for Chrome.
```

(Add an implementation plan reference under "Reference docs (historical)" for the v2 plan path.)

- [ ] **Step 4: Get current test count for the placeholder**

```bash
PATH=/Users/nitin/anaconda3/envs/tandc/bin:$PATH pytest tests/ -m "not slow" --collect-only -q | tail -3
```

Use the count to fill in `<NN>` in DONE.md / PLAN.md.

- [ ] **Step 5: Commit tracking updates**

```bash
git add DONE.md PLAN.md CLAUDE.md
git commit -m "docs: mark Stage 1 v2 shipped + Stage 2 brainstorm pinned active"
```

---

## Task 14: Final test sweep + merge to main

This is the ship gate. Same shape as v1's t14.

- [ ] **Step 1: Full unit suite**

```bash
PATH=/Users/nitin/anaconda3/envs/tandc/bin:$PATH pytest tests/ -v -m "not slow" 2>&1 \
  | tee docs/test_runs/2026-05-2x_v2_final_unit.txt
```

Expected: all green; record pass count.

- [ ] **Step 2: Slow smoke (regression check, should be unchanged from v1)**

```bash
PATH=/Users/nitin/anaconda3/envs/tandc/bin:$PATH pytest tests/ -v -m slow 2>&1 \
  | tee docs/test_runs/2026-05-2x_v2_final_slow.txt
```

Expected: 6/6 vendors pass; ~$0.06 cost. If anything regresses, fix before merging.

- [ ] **Step 3: Append both runs to `docs/TEST_LOG.md`**

```
| 2026-05-2x HH:MM | tandc | s1v2 | t14 | pytest tests/ -m "not slow" | <P> | 0 | 0 | 0 | <T> | full unit suite | <commit> | docs/test_runs/2026-05-2x_v2_final_unit.txt |
| 2026-05-2x HH:MM | tandc | s1v2 | t14 | pytest tests/ -m slow | 6 | 0 | 0 | 0 | <T> | smoke regression | <commit> | docs/test_runs/2026-05-2x_v2_final_slow.txt |
```

- [ ] **Step 4: Verify clean working tree**

```bash
git status
```

Expected: clean (only the docs/test_runs/ commit pending).

- [ ] **Step 5: Final commit + back-fill commit SHA in tracking**

```bash
git add docs/TEST_LOG.md docs/test_runs/2026-05-2x_v2_final_*.txt
git commit -m "test: stage 1 v2 final sweep — unit + slow smoke green"
SHA=$(git rev-parse --short HEAD)
echo "v2 ship commit: $SHA"
```

Then edit `DONE.md` / `PLAN.md` / `CLAUDE.md` to replace `<commit>` placeholders with `$SHA`, and commit again:

```bash
git add DONE.md PLAN.md CLAUDE.md
git commit -m "docs: back-fill v2 ship commit SHA"
```

- [ ] **Step 6: Verify `main` is current branch and commits are stacked correctly**

```bash
git log --oneline -15
```

Expected: a clean linear history from `a068f8a spec: Stage 1 v2 ...` up through the v2 ship commits.

- [ ] **Step 7: Stop here. Do NOT push.**

Per standing rule (local commits only). User decides when/if to push.

---

## Self-Review

**Spec coverage:**
- §1 Goal: covered by Tasks 7–11.
- §2 Non-goals: not implementing remote / auth / history / streaming / framework / build step — confirmed absent from plan.
- §3 Architecture: covered (web/app.py app factory, web/api.py router, static frontend, reuse of core.analyze).
- §4 Components: every file in the components table appears in the file map.
- §5 API contract — URL/paste/file/error mapping: covered by Tasks 7+8.
- §6 Frontend: covered by Task 9.
- §7 CLI surface: covered by Task 11; exit codes 0/4/5 covered by Tasks 10+11.
- §8 Error handling: covered by Task 8.
- §9 Testing: unit tests in Tasks 4/6/7/10/11; manual e2e in Task 12.
- §10 Tech stack: Task 1.
- §11 Project layout: file map matches.
- §12 Open questions (CSS palette, `<details>` defaults, metadata visibility): Task 9 picks reasonable defaults (centralised CSS custom properties, `<details>` collapsed by default, taxonomy/model shown as dim meta line).
- §13 Success criteria: all 7 items map to Tasks 11/12.

**Placeholder scan:** No `TBD` / `implement later` / "add appropriate handling" / "similar to Task N" found. Date placeholders `2026-05-2x` and `<commit>` / `<NN>` are intentional — filled at execution time when the actual date and SHA are known.

**Type consistency:** `analyze_prepared()` signature is identical across Task 4 definition, Task 7 calls, and Task 11 (n/a). `text_to_meta()` signature consistent across Tasks 3 and 7. `create_app()` referenced from Task 8 definition and Tasks 7/10 imports. `TandcServerPortInUse` defined in Task 10, referenced in Task 11.

**Note on small core touches:** The spec says "`tandc.core` is untouched", but the implementation requires (a) extending `FetchMeta.source` Literal by two variants and (b) extracting `analyze_prepared()` from `analyze()`. Both are additive and preserve the existing public API. The plan flags these explicitly (Tasks 2 and 4) so a reviewer can see the divergence.
