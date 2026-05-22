from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from tandc.core.schema import (
    AnalysisReport,
    CoreFinding,
    Evidence,
    FetchMeta,
    FlagFinding,
    CORE_CATEGORIES,
    FLAG_CATEGORIES,
    SCHEMA_VERSION,
)


def _valid_fetch_meta_dict():
    return {
        "source": "url",
        "url": "https://example.com/terms",
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "http_status": 200,
        "content_type": "text/html; charset=utf-8",
        "content_type_was_plain": False,
        "extractor": "trafilatura",
        "raw_bytes": 84000,
        "extracted_chars": 12000,
    }


def _valid_core_finding(category: str):
    return {
        "category": category,
        "severity": "medium",
        "summary": "We collect your data and share it with partners.",
        "why_it_matters": "Your personal data leaves the service.",
        "evidence": [{"quote": "we share your data", "char_start": 0, "char_end": 19}],
    }


def _valid_flag_finding(category: str):
    return {
        "category": category,
        "presence": "absent",
        "note": "No mention of this topic in the document.",
    }


def _valid_report_dict():
    return {
        "schema_version": SCHEMA_VERSION,
        "taxonomy_version": "v1",
        "model": "claude-sonnet-4-6",
        "analyzed_at": datetime.now(timezone.utc).isoformat(),
        "input_hash": "a" * 64,
        "fetch_meta": _valid_fetch_meta_dict(),
        "overall_risk": "medium",
        "headline": "Service collects data and uses arbitration.",
        "core_findings": [_valid_core_finding(c) for c in CORE_CATEGORIES],
        "flags": [_valid_flag_finding(c) for c in FLAG_CATEGORIES],
        "notes": [],
    }


class TestFetchMeta:
    def test_content_type_plain_flag(self):
        m = FetchMeta(**_valid_fetch_meta_dict())
        assert m.content_type_was_plain is False

    def test_stdin_source_no_url(self):
        d = _valid_fetch_meta_dict()
        d["source"] = "stdin"
        d["url"] = None
        d["http_status"] = None
        d["content_type"] = None
        d["extractor"] = None
        m = FetchMeta(**d)
        assert m.url is None


class TestAnalysisReport:
    def test_valid_round_trip(self):
        r = AnalysisReport(**_valid_report_dict())
        assert r.schema_version == SCHEMA_VERSION
        assert len(r.core_findings) == 4
        assert len(r.flags) == 4

    def test_rejects_missing_core_category(self):
        d = _valid_report_dict()
        d["core_findings"] = d["core_findings"][:3]  # drop one
        with pytest.raises(ValidationError):
            AnalysisReport(**d)

    def test_rejects_duplicate_core_category(self):
        d = _valid_report_dict()
        d["core_findings"][1] = _valid_core_finding("personal_data")  # duplicate
        with pytest.raises(ValidationError):
            AnalysisReport(**d)

    def test_rejects_missing_flag_category(self):
        d = _valid_report_dict()
        d["flags"] = d["flags"][:3]
        with pytest.raises(ValidationError):
            AnalysisReport(**d)

    def test_rejects_invalid_severity(self):
        d = _valid_report_dict()
        d["core_findings"][0]["severity"] = "catastrophic"
        with pytest.raises(ValidationError):
            AnalysisReport(**d)

    def test_evidence_requires_at_least_one_quote(self):
        d = _valid_report_dict()
        d["core_findings"][0]["evidence"] = []
        with pytest.raises(ValidationError):
            AnalysisReport(**d)


def test_constants():
    assert set(CORE_CATEGORIES) == {
        "personal_data",
        "pii_protection",
        "continuity",
        "liability_dispute",
    }
    assert set(FLAG_CATEGORIES) == {
        "content_licensing",
        "account_access",
        "payment_subscription",
        "jurisdictional",
    }
    assert SCHEMA_VERSION == "1"


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
