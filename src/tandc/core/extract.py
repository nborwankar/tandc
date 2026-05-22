"""HTML → readable text extraction with Content-Type tracking."""

from __future__ import annotations

from typing import Literal

import trafilatura

Extractor = Literal["trafilatura", "raw"]

# Unicode characters that LLMs routinely normalise to ASCII in their output,
# breaking the "Evidence.quote is a verbatim substring" contract. We normalise
# at extraction so Claude sees ASCII text and returns ASCII quotes that ARE
# substrings of what's on disk in input.txt.
_NORMALISE_MAP = str.maketrans(
    {
        "‘": "'",  # left single quotation mark
        "’": "'",  # right single quotation mark / apostrophe
        "‚": "'",  # single low-9 quotation mark
        "‛": "'",  # single high-reversed-9 quotation mark
        "“": '"',  # left double quotation mark
        "”": '"',  # right double quotation mark
        "„": '"',  # double low-9 quotation mark
        "–": "-",  # en dash
        "—": "-",  # em dash
        "…": "...",  # horizontal ellipsis
        " ": " ",  # non-breaking space
        "\r": "",  # CR (CRLF → LF after this map)
    }
)


def _normalise_text(s: str) -> str:
    """Replace common Unicode lookalikes with ASCII equivalents."""
    return s.translate(_NORMALISE_MAP)


def is_plain_text_content_type(content_type: str | None) -> bool:
    """True iff the response's Content-Type is text/plain (with or without params)."""
    if not content_type:
        return False
    primary = content_type.split(";", 1)[0].strip().lower()
    return primary == "text/plain"


def extract_text(body: str, content_type: str | None) -> tuple[str | None, Extractor]:
    """Extract readable text from a fetched body.

    Returns (text_or_none, extractor_used). `text` is None if extraction yielded
    nothing usable; the caller decides whether to error.
    """
    if is_plain_text_content_type(content_type):
        return _normalise_text(body), "raw"
    extracted = trafilatura.extract(body, include_comments=False, include_tables=False)
    if extracted is None or not extracted.strip():
        return None, "trafilatura"
    return _normalise_text(extracted), "trafilatura"
