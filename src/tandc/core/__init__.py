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
) -> tuple[AnalysisReport, Path | None, bool]:
    """Run cache + Claude + artefact-write on already-loaded text.

    Callers are responsible for loading text and building a FetchMeta. `slug`
    is used verbatim for the report directory name. Returns
    (report, rdir, cache_hit); rdir is None when output_base is None, and
    cache_hit is True iff the report came from the on-disk cache.
    """
    key = cache_key(text, model)
    report = load_from_cache(key) if use_cache else None
    cache_hit = report is not None

    if report is None:
        if client is None:
            # SDK defers auth until request time, so pre-check here to give a
            # clean TandcConfigError instead of a late TypeError from inside
            # the request stack.
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
        return report, None, cache_hit

    # On a cache hit, fetch_meta from the current (re)fetch contradicts the
    # report's embedded fetch_meta from the original analysis. Persist the
    # report's own fetch_meta so the artefacts in this directory agree about
    # which fetch was actually analyzed.
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
    return report, rdir, cache_hit


def analyze(
    *,
    url: str | None = None,
    stdin: IO[str] | None = None,
    model: str = MODEL_SONNET,
    use_cache: bool = True,
    output_base: Path | None = None,
    client: Anthropic | None = None,
    on_date: date | None = None,
) -> tuple[AnalysisReport, Path | None, bool]:
    """Run the full pipeline.

    Exactly one of `url` or `stdin` must be provided. Returns
    (report, rdir, cache_hit). `rdir` is None if `output_base` is None
    (used by `--json` mode that streams to stdout without writing
    artefacts). `cache_hit` is True iff the report came from the on-disk
    cache rather than a fresh Claude call.
    """
    if (url is None) == (stdin is None):
        raise ValueError("exactly one of url= or stdin= is required")

    if url is not None:
        text, fetch_meta = url_to_text(url)
        slug = slug_for_url(url)
    else:
        text, fetch_meta = stdin_to_text(stdin)
        slug = f"stdin-{cache_key(text, model)[:8]}"

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
