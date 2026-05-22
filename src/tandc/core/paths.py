"""Path, slug, and hash helpers. No I/O beyond mkdir / env lookups."""

from __future__ import annotations

import hashlib
import os
import re
from datetime import date
from pathlib import Path
from urllib.parse import urlparse

_SLUG_NON_ALNUM = re.compile(r"[^a-z0-9]+")
_SLUG_MAX_LEN = 64


def slug_for_url(url: str) -> str:
    """Turn a URL into a filesystem-safe slug: host + last meaningful path segment."""
    parsed = urlparse(url)
    host = (parsed.hostname or "unknown").lower()
    segments = [s for s in parsed.path.split("/") if s]
    if segments:
        last = _SLUG_NON_ALNUM.sub("-", segments[-1].lower()).strip("-")
        slug = f"{host}-{last}" if last else host
    else:
        slug = host
    return slug[:_SLUG_MAX_LEN]


def sha256_of(text: str) -> str:
    """Hex SHA-256 digest of UTF-8-encoded text."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def report_dir(base: Path, slug: str, on_date: date) -> Path:
    """Create and return ./reports/<slug>-<YYYY-MM-DD>/, suffixing -2, -3 on collision."""
    reports = base / "reports"
    reports.mkdir(parents=True, exist_ok=True)
    stem = f"{slug}-{on_date.isoformat()}"
    candidate = reports / stem
    n = 2
    while candidate.exists():
        candidate = reports / f"{stem}-{n}"
        n += 1
    candidate.mkdir()
    return candidate


def cache_dir() -> Path:
    """Return the cache directory: $TANDC_CACHE_DIR or ~/.tandc/cache."""
    override = os.environ.get("TANDC_CACHE_DIR")
    if override:
        return Path(override)
    return Path(os.environ["HOME"]) / ".tandc" / "cache"


def cache_path_for_key(key: str) -> Path:
    """Path to the cache JSON file for a given cache key."""
    return cache_dir() / f"{key}.json"
