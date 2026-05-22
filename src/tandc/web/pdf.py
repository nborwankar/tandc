"""PDF text extraction for the web layer's file-upload mode."""

from __future__ import annotations

import io
import logging

from pypdf import PdfReader
from pypdf.errors import PdfReadError

from tandc.core.extract import _normalise_text
from tandc.errors import TandcExtractionError

log = logging.getLogger(__name__)


def extract_pdf(blob: bytes) -> str:
    """Extract text from a PDF blob.

    Output is run through core.extract._normalise_text so the verbatim-quote
    contract from the analyzer continues to hold.

    Raises TandcExtractionError on empty input, parse failure, or no extractable text.
    """
    raw_bytes = len(blob)
    if not blob:
        raise TandcExtractionError(url=None, raw_bytes=0, extracted_chars=0)
    try:
        reader = PdfReader(io.BytesIO(blob))
        chunks = [page.extract_text() or "" for page in reader.pages]
    except PdfReadError as e:
        raise TandcExtractionError(
            url=None, raw_bytes=raw_bytes, extracted_chars=0
        ) from e
    except Exception as e:
        # pypdf may raise other exceptions (zlib, unicode, etc.) on malformed PDFs;
        # treat all as extraction failures. We log so the cause isn't lost.
        log.warning("pypdf failed to parse PDF blob: %s", e)
        raise TandcExtractionError(
            url=None, raw_bytes=raw_bytes, extracted_chars=0
        ) from e
    text = _normalise_text("\n".join(chunks))
    if not text.strip():
        raise TandcExtractionError(url=None, raw_bytes=raw_bytes, extracted_chars=0)
    return text
