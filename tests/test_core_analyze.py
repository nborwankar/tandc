"""Integration tests for tandc.core.analyze() — the public wiring entry point."""

import io
import json
from datetime import date
from unittest.mock import MagicMock

import pytest

from tandc.core import analyze
from tandc.core.cache import cache_key, store_in_cache
from tandc.core.schema import AnalysisReport, FetchMeta
from tandc.errors import TandcConfigError
from tests.test_analyzer import _claude_response_with
from tests.test_schema import _valid_report_dict


@pytest.fixture
def tmp_cache(monkeypatch, tmp_path):
    monkeypatch.setenv("TANDC_CACHE_DIR", str(tmp_path / "cache"))
    return tmp_path / "cache"


def _report():
    return AnalysisReport(**_valid_report_dict())


class TestXorGuard:
    def test_both_none_raises(self):
        with pytest.raises(ValueError):
            analyze(url=None, stdin=None)

    def test_both_provided_raises(self):
        with pytest.raises(ValueError):
            analyze(url="https://x.example/", stdin=io.StringIO("text"))


class TestStdinPath:
    def test_writes_all_four_artefacts(self, tmp_cache, tmp_path):
        client = MagicMock()
        client.messages.create.return_value = _claude_response_with(
            _valid_report_dict()
        )
        report, rdir, cache_hit = analyze(
            stdin=io.StringIO("Sample pasted terms. We collect data."),
            client=client,
            output_base=tmp_path,
            on_date=date(2026, 5, 20),
        )
        assert isinstance(report, AnalysisReport)
        assert rdir is not None
        assert cache_hit is False
        for fname in ("input.txt", "fetch_meta.json", "report.json", "report.md"):
            assert (rdir / fname).exists(), f"missing {fname}"
        # report.json round-trips
        loaded = json.loads((rdir / "report.json").read_text())
        assert loaded["headline"] == report.headline

    def test_output_base_none_returns_no_dir(self, tmp_cache):
        client = MagicMock()
        client.messages.create.return_value = _claude_response_with(
            _valid_report_dict()
        )
        report, rdir, cache_hit = analyze(
            stdin=io.StringIO("Sample text"),
            client=client,
            output_base=None,
        )
        assert isinstance(report, AnalysisReport)
        assert rdir is None
        assert cache_hit is False


class TestCacheHitArtefactConsistency:
    """Regression: cache-hit fetch_meta.json must match the report's embedded fetch_meta."""

    def test_cache_hit_writes_stored_fetch_meta(self, tmp_cache, tmp_path):
        # 1. Pre-populate the cache so the next analyze() is a hit
        text = "Sample pasted terms. We collect data."
        # Stdin path: build the same cache key the loader would
        from tandc.core.analyzer import MODEL_SONNET

        cached_report = _report()
        store_in_cache(cache_key(text, MODEL_SONNET), cached_report)

        # 2. Run analyze() — client must never be called on a hit
        client = MagicMock()
        report, rdir, cache_hit = analyze(
            stdin=io.StringIO(text),
            client=client,
            output_base=tmp_path,
            on_date=date(2026, 5, 20),
        )

        assert client.messages.create.call_count == 0  # cache hit
        assert cache_hit is True
        assert rdir is not None

        # 3. The on-disk fetch_meta.json must be the report's own fetch_meta,
        #    not the freshly-computed stdin one.
        fm_on_disk = json.loads((rdir / "fetch_meta.json").read_text())
        assert fm_on_disk == cached_report.fetch_meta.model_dump(mode="json")

        # 4. And it must equal what's embedded in report.json (no divergence)
        report_on_disk = json.loads((rdir / "report.json").read_text())
        assert report_on_disk["fetch_meta"] == fm_on_disk


class TestConfigError:
    def test_missing_api_key_raises_tandc_config_error(self, monkeypatch, tmp_cache):
        # conftest sets a fake key; clear it so Anthropic() construction fails
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        with pytest.raises(TandcConfigError):
            analyze(stdin=io.StringIO("Sample text"))


class TestAnalyzePrepared:
    """analyze_prepared() runs the cache+claude+write tail with caller-supplied text/meta/slug."""

    def _paste_fm(self, text: str) -> FetchMeta:
        from datetime import datetime, timezone
        from tandc.core.schema import FetchMeta as _FM

        return _FM(
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

    def test_writes_artefacts_with_supplied_slug(self, tmp_cache, tmp_path):
        from tandc.core import analyze_prepared

        text = "These are pasted terms. We share data with third parties."
        fm = self._paste_fm(text)
        client = MagicMock()
        client.messages.create.return_value = _claude_response_with(
            _valid_report_dict()
        )
        report, rdir, cache_hit = analyze_prepared(
            text=text,
            fetch_meta=fm,
            slug="example-com-terms",
            output_base=tmp_path,
            client=client,
            on_date=date(2026, 5, 21),
        )
        assert rdir is not None
        assert cache_hit is False
        assert rdir.name == "example-com-terms-2026-05-21"
        for fname in ("input.txt", "fetch_meta.json", "report.json", "report.md"):
            assert (rdir / fname).exists(), f"missing {fname}"
        assert (rdir / "input.txt").read_text(encoding="utf-8") == text

    def test_returns_none_dir_when_output_base_none(self, tmp_cache):
        from tandc.core import analyze_prepared

        text = "Pasted policy text for JSON-only mode."
        fm = self._paste_fm(text)
        client = MagicMock()
        client.messages.create.return_value = _claude_response_with(
            _valid_report_dict()
        )
        report, rdir, cache_hit = analyze_prepared(
            text=text,
            fetch_meta=fm,
            slug="paste-abc12345",
            output_base=None,
            client=client,
        )
        assert isinstance(report, AnalysisReport)
        assert rdir is None
        assert cache_hit is False

    def test_cache_hit_uses_stored_fetch_meta_on_disk(self, tmp_cache, tmp_path):
        """Same regression contract analyze() has: on cache hit, fetch_meta.json comes from stored report."""
        from tandc.core import analyze_prepared
        from tandc.core.analyzer import MODEL_SONNET as _M

        text = "Cached paste body for fetch_meta divergence check."
        fm_now = self._paste_fm(text)
        cached_report = _report()
        # Pre-populate cache so this call is a hit
        store_in_cache(cache_key(text, _M), cached_report)
        client = MagicMock()
        report, rdir, cache_hit = analyze_prepared(
            text=text,
            fetch_meta=fm_now,  # this should NOT be persisted on a cache hit
            slug="paste-cached",
            output_base=tmp_path,
            client=client,
            on_date=date(2026, 5, 21),
        )
        assert client.messages.create.call_count == 0
        assert cache_hit is True
        assert rdir is not None
        fm_on_disk = json.loads((rdir / "fetch_meta.json").read_text())
        assert fm_on_disk == cached_report.fetch_meta.model_dump(mode="json")
