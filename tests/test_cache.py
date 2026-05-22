import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from tandc.core.cache import cache_key, load_from_cache, store_in_cache
from tandc.core.schema import SCHEMA_VERSION, TAXONOMY_VERSION, AnalysisReport
from tests.test_schema import _valid_report_dict


@pytest.fixture
def tmp_cache(monkeypatch, tmp_path):
    monkeypatch.setenv("TANDC_CACHE_DIR", str(tmp_path / "cache"))
    return tmp_path / "cache"


def _report():
    return AnalysisReport(**_valid_report_dict())


class TestCacheKey:
    def test_stable_for_same_inputs(self):
        a = cache_key("hello", "claude-sonnet-4-6")
        b = cache_key("hello", "claude-sonnet-4-6")
        assert a == b

    def test_changes_with_text(self):
        a = cache_key("hello", "claude-sonnet-4-6")
        b = cache_key("world", "claude-sonnet-4-6")
        assert a != b

    def test_changes_with_model(self):
        a = cache_key("hello", "claude-sonnet-4-6")
        b = cache_key("hello", "claude-opus-4-7")
        assert a != b

    def test_includes_taxonomy_and_schema_version(self):
        """If we bump TAXONOMY_VERSION later, the same text must produce a different key."""
        a = cache_key("hello", "claude-sonnet-4-6")
        expected_pieces = [
            "hello",
            "claude-sonnet-4-6",
            TAXONOMY_VERSION,
            SCHEMA_VERSION,
        ]
        # Sanity: the key should differ if any piece changes
        import hashlib

        recomputed = hashlib.sha256("|".join(expected_pieces).encode()).hexdigest()
        assert a == recomputed


class TestStoreAndLoad:
    def test_round_trip(self, tmp_cache):
        report = _report()
        key = "abc123"
        store_in_cache(key, report)
        loaded = load_from_cache(key)
        assert loaded == report

    def test_miss_returns_none(self, tmp_cache):
        assert load_from_cache("nonexistent") is None

    def test_creates_cache_dir(self, tmp_cache):
        assert not tmp_cache.exists()
        store_in_cache("xyz", _report())
        assert tmp_cache.exists()

    def test_malformed_file_returns_none_and_warns(self, tmp_cache, caplog):
        tmp_cache.mkdir(parents=True)
        (tmp_cache / "bad.json").write_text("{not json")
        import logging

        with caplog.at_level(logging.WARNING):
            assert load_from_cache("bad") is None
        assert "malformed cache" in caplog.text.lower()

    def test_write_failure_warns_but_does_not_raise(
        self, tmp_path, monkeypatch, caplog
    ):
        # Point cache at a path that cannot be created (a file, not a dir)
        blocker = tmp_path / "blocker"
        blocker.write_text("not a dir")
        monkeypatch.setenv("TANDC_CACHE_DIR", str(blocker / "cache"))
        import logging

        with caplog.at_level(logging.WARNING):
            store_in_cache("k", _report())  # must not raise
        assert "cache write failed" in caplog.text.lower()
