"""Content-hash file cache for AnalysisReport.

Cache is an optimisation: write failures log a warning but do not propagate.
Read failures (missing file, malformed JSON) are treated as misses.
"""

from __future__ import annotations

import hashlib
import json
import logging

from tandc.core.paths import cache_dir, cache_path_for_key
from tandc.core.schema import SCHEMA_VERSION, TAXONOMY_VERSION, AnalysisReport

log = logging.getLogger(__name__)


def cache_key(text: str, model: str) -> str:
    """SHA-256 of text || model || taxonomy_version || schema_version, joined by '|'."""
    pieces = [text, model, TAXONOMY_VERSION, SCHEMA_VERSION]
    return hashlib.sha256("|".join(pieces).encode("utf-8")).hexdigest()


def load_from_cache(key: str) -> AnalysisReport | None:
    path = cache_path_for_key(key)
    if not path.exists():
        return None
    try:
        raw = path.read_text(encoding="utf-8")
        data = json.loads(raw)
        return AnalysisReport.model_validate(data)
    except (json.JSONDecodeError, ValueError) as e:
        log.warning("malformed cache entry at %s: %s — treating as miss", path, e)
        return None


def store_in_cache(key: str, report: AnalysisReport) -> None:
    path = cache_path_for_key(key)
    try:
        cache_dir().mkdir(parents=True, exist_ok=True)
        path.write_text(report.model_dump_json(indent=2), encoding="utf-8")
    except OSError as e:
        log.warning("cache write failed for %s: %s — continuing without cache", path, e)
