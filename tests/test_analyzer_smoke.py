"""Live Claude API tests, gated by @pytest.mark.slow.

Run only with: pytest -m slow
Costs roughly 1¢ per fixture (~6¢ for the full sweep).
Requires ANTHROPIC_API_KEY in the environment.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest
import yaml
from anthropic import Anthropic

from tandc.core.analyzer import MODEL_SONNET, analyze_text
from tandc.core.schema import (
    CORE_CATEGORIES,
    FLAG_CATEGORIES,
    AnalysisReport,
    FetchMeta,
)

FIXTURES = Path(__file__).parent / "fixtures"
SEVERITY_RANK = {"low": 1, "medium": 2, "high": 3, "critical": 4}

_VENDORS = sorted(
    d.name
    for d in FIXTURES.iterdir()
    if d.is_dir() and (d / "extracted.txt").exists() and not d.name.startswith("_")
)


def _meta_from_fixture(vendor: str) -> FetchMeta:
    data = json.loads((FIXTURES / vendor / "fetch_meta.json").read_text())
    return FetchMeta.model_validate(data)


def _expected(vendor: str) -> dict:
    return yaml.safe_load((FIXTURES / vendor / "expected_findings.yaml").read_text())


@pytest.mark.slow
@pytest.mark.parametrize("vendor", _VENDORS)
def test_live_analysis_against_fixture(vendor, real_anthropic_key):
    text = (FIXTURES / vendor / "extracted.txt").read_text()
    assert len(text) > 1000, f"fixture {vendor} extracted text too short"

    # real_anthropic_key is a _RealKey wrapper (redacted in pytest -v). Call .value
    # to get the actual string. See tests/conftest.py for why.
    client = Anthropic(api_key=real_anthropic_key.value)
    report = analyze_text(
        text=text,
        fetch_meta=_meta_from_fixture(vendor),
        client=client,
        model=MODEL_SONNET,
    )

    # 1. Schema invariants
    assert isinstance(report, AnalysisReport)
    assert {f.category for f in report.core_findings} == set(CORE_CATEGORIES)
    assert {f.category for f in report.flags} == set(FLAG_CATEGORIES)

    # 2. Every evidence quote is a substring of the input under a loose
    # comparison that collapses (a) case, (b) any whitespace run, and (c) the
    # markdown list-marker prefix `- ` into a single space. Claude routinely
    # lowercases sentence-initial letters when stitching a quote and stitches
    # across bulleted lists into flowing prose. Both are known LLM behaviours
    # that don't change the quote's meaning or its locatability for a human
    # reader. Smart-quote / dash drift is already neutralised by
    # extract._normalise_text() before the document reaches Claude.
    import re

    def _loose(s: str) -> str:
        # Drop list-marker prefix on lines, then collapse all whitespace,
        # then lowercase. Order matters: strip bullets before collapsing space.
        s = re.sub(r"(?m)^\s*-\s+", " ", s)
        s = re.sub(r"\s+", " ", s)
        return s.lower().strip()

    text_loose = _loose(text)
    for f in report.core_findings:
        for ev in f.evidence:
            assert _loose(ev.quote) in text_loose, (
                f"{vendor}/{f.category}: evidence quote not found in input "
                f"(loose match): {ev.quote[:80]!r}"
            )

    # 3. Match against curated expectations
    expected = _expected(vendor)
    assert (
        SEVERITY_RANK[report.overall_risk]
        >= SEVERITY_RANK[expected["overall_risk_min"]]
    ), f"{vendor}: overall_risk {report.overall_risk} below min {expected['overall_risk_min']}"
    for cat, criteria in expected["core"].items():
        finding = next(f for f in report.core_findings if f.category == cat)
        sev_min = criteria.get("severity_min", "low")
        assert (
            SEVERITY_RANK[finding.severity] >= SEVERITY_RANK[sev_min]
        ), f"{vendor}/{cat}: severity {finding.severity} below min {sev_min}"
        for needle in criteria.get("must_mention", []):
            haystack = (finding.summary + " " + finding.why_it_matters).lower()
            assert (
                needle.lower() in haystack
            ), f"{vendor}/{cat}: expected mention of {needle!r} in summary/why"
    for cat, criteria in expected["flags"].items():
        flag = next(f for f in report.flags if f.category == cat)
        want = criteria.get("presence", "any")
        if want != "any":
            assert (
                flag.presence == want
            ), f"{vendor}/{cat}: presence {flag.presence}, expected {want}"
