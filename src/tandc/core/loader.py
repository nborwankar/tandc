"""Input loaders: URL fetch (httpx + extract) and stdin reader."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import IO, Literal

import httpx

from tandc.core.extract import _normalise_text, extract_text, is_plain_text_content_type
from tandc.core.schema import FetchMeta
from tandc.errors import TandcExtractionError, TandcFetchError

log = logging.getLogger(__name__)

_USER_AGENT = "tandc/0.1 (+https://github.com/nborwankar/tandc)"
_TIMEOUT = httpx.Timeout(30.0, connect=10.0)


def url_to_text(url: str) -> tuple[str, FetchMeta]:
    """Fetch `url` via httpx, extract readable text, return (text, FetchMeta).

    Raises TandcFetchError on network / HTTP errors, TandcExtractionError on
    empty extraction.
    """
    try:
        response = httpx.get(
            url,
            headers={"User-Agent": _USER_AGENT, "Accept": "text/html, text/plain, */*"},
            timeout=_TIMEOUT,
            follow_redirects=True,
        )
    except httpx.HTTPError as e:
        raise TandcFetchError(url=url, status=None, message=str(e)) from e

    if response.status_code >= 400:
        raise TandcFetchError(
            url=url, status=response.status_code, message=f"HTTP {response.status_code}"
        )

    content_type = response.headers.get("content-type")
    body = response.text
    raw_bytes = len(response.content)

    text, extractor = extract_text(body, content_type)
    if text is None:
        raise TandcExtractionError(url=url, raw_bytes=raw_bytes, extracted_chars=0)

    meta = FetchMeta(
        source="url",
        url=url,
        fetched_at=datetime.now(timezone.utc),
        http_status=response.status_code,
        content_type=content_type,
        content_type_was_plain=is_plain_text_content_type(content_type),
        extractor=extractor,
        raw_bytes=raw_bytes,
        extracted_chars=len(text),
    )
    return text, meta


def stdin_to_text(stream: IO[str]) -> tuple[str, FetchMeta]:
    """Read pasted text from a stream. Raises TandcExtractionError if empty."""
    text = stream.read()
    raw_bytes = len(text.encode("utf-8"))
    if not text.strip():
        raise TandcExtractionError(url=None, raw_bytes=raw_bytes, extracted_chars=0)
    meta = FetchMeta(
        source="stdin",
        url=None,
        fetched_at=datetime.now(timezone.utc),
        http_status=None,
        content_type=None,
        content_type_was_plain=False,
        extractor=None,
        raw_bytes=raw_bytes,
        extracted_chars=len(text),
    )
    return text, meta


def text_to_meta(
    text: str,
    source: Literal["paste", "file"],
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
        raise TandcExtractionError(
            url=source_url, raw_bytes=raw_bytes, extracted_chars=0
        )
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
