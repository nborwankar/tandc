"""FastAPI route tests. core.analyze* is mocked — no live Claude here."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from tandc.core.schema import (
    CORE_CATEGORIES,
    FLAG_CATEGORIES,
    AnalysisReport,
    CoreFinding,
    Evidence,
    FetchMeta,
    FlagFinding,
)
from tandc.errors import (
    TandcAnalysisError,
    TandcConfigError,
    TandcExtractionError,
    TandcFetchError,
)
from tandc.web.app import create_app

FIXTURE_PDF = Path(__file__).parent / "fixtures" / "sample.pdf"


def _fake_report(text: str = "test body for fake report") -> AnalysisReport:
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
        m_analyze.return_value = (fake, tmp_path / "reports" / "stub", False)
        r = client.post(
            "/analyze",
            json={"url": "https://example.com/terms", "model": "sonnet"},
        )
    assert r.status_code == 200, r.text
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
        m_prep.return_value = (fake, tmp_path / "reports" / "stub", False)
        r = client.post(
            "/analyze",
            json={
                "text": "Pasted terms body.",
                "source_url": "https://example.com/terms",
                "model": "sonnet",
            },
        )
    assert r.status_code == 200, r.text
    m_prep.assert_called_once()
    _, kwargs = m_prep.call_args
    assert kwargs["text"] == "Pasted terms body."
    assert kwargs["fetch_meta"].source == "paste"
    assert kwargs["fetch_meta"].url == "https://example.com/terms"


def test_post_analyze_file_html_mode(client, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    fake = _fake_report("policy body")
    html = (
        b"<html><body>"
        b"<p>We collect data from users in many ways. We use binding arbitration "
        b"to resolve disputes and waive class action rights. By using this service "
        b"you grant us a perpetual worldwide license to your content.</p>"
        b"</body></html>"
    )
    with patch("tandc.web.api.analyze_prepared") as m_prep:
        m_prep.return_value = (fake, tmp_path / "reports" / "stub", False)
        r = client.post(
            "/analyze",
            files={"file": ("terms.html", html, "text/html")},
            data={"model": "sonnet"},
        )
    assert r.status_code == 200, r.text
    _, kwargs = m_prep.call_args
    assert kwargs["fetch_meta"].source == "file"
    assert kwargs["fetch_meta"].content_type == "text/html"


def test_post_analyze_file_txt_mode(client, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    fake = _fake_report("policy body")
    txt = b"These are the terms. We share data."
    with patch("tandc.web.api.analyze_prepared") as m_prep:
        m_prep.return_value = (fake, tmp_path / "reports" / "stub", False)
        r = client.post(
            "/analyze",
            files={"file": ("terms.txt", txt, "text/plain")},
        )
    assert r.status_code == 200, r.text
    _, kwargs = m_prep.call_args
    assert kwargs["fetch_meta"].source == "file"
    assert "These are the terms" in kwargs["text"]


def test_post_analyze_file_pdf_mode(client, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    fake = _fake_report("policy body")
    pdf_bytes = FIXTURE_PDF.read_bytes()
    with patch("tandc.web.api.analyze_prepared") as m_prep:
        m_prep.return_value = (fake, tmp_path / "reports" / "stub", False)
        r = client.post(
            "/analyze",
            files={"file": ("sample.pdf", pdf_bytes, "application/pdf")},
        )
    assert r.status_code == 200, r.text
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
        m_analyze.return_value = (fake, tmp_path / "reports" / "stub", False)
        r = client.post(
            "/analyze",
            json={"url": "https://example.com/x", "model": "opus", "use_cache": False},
        )
    assert r.status_code == 200, r.text
    from tandc.core.analyzer import MODEL_OPUS

    _, kwargs = m_analyze.call_args
    assert kwargs["model"] == MODEL_OPUS
    assert kwargs["use_cache"] is False


def test_post_analyze_cache_hit_flows_through_to_response(
    client, tmp_path, monkeypatch
):
    """Regression: cache_hit=True from analyze() must reach the JSON response body."""
    monkeypatch.chdir(tmp_path)
    fake = _fake_report()
    with patch("tandc.web.api.analyze") as m_analyze:
        m_analyze.return_value = (fake, tmp_path / "reports" / "stub", True)
        r = client.post(
            "/analyze",
            json={"url": "https://example.com/terms", "model": "sonnet"},
        )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["cache_hit"] is True


def test_get_root_returns_html_form(client):
    r = client.get("/")
    assert r.status_code == 200
    assert "text/html" in r.headers["content-type"]
    assert "tandc" in r.text.lower()
