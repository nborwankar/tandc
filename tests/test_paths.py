from datetime import date
from pathlib import Path

import pytest

from tandc.core.paths import (
    cache_dir,
    cache_path_for_key,
    report_dir,
    sha256_of,
    slug_for_url,
)


class TestSlugForUrl:
    def test_extracts_host_and_path(self):
        assert (
            slug_for_url("https://openai.com/policies/terms-of-use/")
            == "openai.com-terms-of-use"
        )

    def test_lowercases(self):
        assert slug_for_url("https://EXAMPLE.com/Terms") == "example.com-terms"

    def test_replaces_non_alnum(self):
        assert (
            slug_for_url("https://example.com/legal/tos_v2.html")
            == "example.com-tos-v2-html"
        )

    def test_handles_no_path(self):
        assert slug_for_url("https://example.com/") == "example.com"

    def test_truncates_to_64_chars(self):
        url = "https://example.com/" + "a" * 200
        assert len(slug_for_url(url)) <= 64


class TestSha256:
    def test_stable(self):
        assert sha256_of("hello") == sha256_of("hello")

    def test_different_for_different_inputs(self):
        assert sha256_of("hello") != sha256_of("world")

    def test_hex_64_chars(self):
        digest = sha256_of("hello")
        assert len(digest) == 64
        int(digest, 16)  # raises if not hex


class TestReportDir:
    def test_layout(self, tmp_path):
        d = report_dir(tmp_path, slug="example.com-terms", on_date=date(2026, 5, 20))
        assert d == tmp_path / "reports" / "example.com-terms-2026-05-20"
        assert d.exists()

    def test_collision_appends_suffix(self, tmp_path):
        first = report_dir(tmp_path, slug="x", on_date=date(2026, 5, 20))
        second = report_dir(tmp_path, slug="x", on_date=date(2026, 5, 20))
        assert first.name == "x-2026-05-20"
        assert second.name == "x-2026-05-20-2"
        third = report_dir(tmp_path, slug="x", on_date=date(2026, 5, 20))
        assert third.name == "x-2026-05-20-3"


class TestCacheDir:
    def test_default_under_home(self, monkeypatch, tmp_path):
        monkeypatch.setenv("HOME", str(tmp_path))
        assert cache_dir() == tmp_path / ".tandc" / "cache"

    def test_override_via_env(self, monkeypatch, tmp_path):
        monkeypatch.setenv("TANDC_CACHE_DIR", str(tmp_path / "elsewhere"))
        assert cache_dir() == tmp_path / "elsewhere"

    def test_cache_path_for_key(self, monkeypatch, tmp_path):
        monkeypatch.setenv("HOME", str(tmp_path))
        p = cache_path_for_key("abc123")
        assert p == tmp_path / ".tandc" / "cache" / "abc123.json"
