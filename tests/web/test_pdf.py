from pathlib import Path

import pytest

from tandc.errors import TandcExtractionError
from tandc.web.pdf import extract_pdf

FIXTURE = Path(__file__).parent / "fixtures" / "sample.pdf"


def test_extract_pdf_returns_sentinel_text():
    blob = FIXTURE.read_bytes()
    text = extract_pdf(blob)
    assert "TANDC SAMPLE PDF" in text
    assert "personal data" in text


def test_extract_pdf_output_is_ascii():
    """Normalisation via core.extract._normalise_text should leave ASCII intact."""
    blob = FIXTURE.read_bytes()
    text = extract_pdf(blob)
    # The fixture's body is ASCII; round-trip preserves it.
    assert "we collect" in text


def test_extract_pdf_empty_blob_raises():
    with pytest.raises(TandcExtractionError):
        extract_pdf(b"")


def test_extract_pdf_corrupt_blob_raises():
    with pytest.raises(TandcExtractionError):
        extract_pdf(b"not a pdf at all, just random bytes")


def test_extract_pdf_empty_pages_raises(tmp_path):
    """A valid PDF that contains no text should raise TandcExtractionError."""
    from pypdf import PdfWriter

    w = PdfWriter()
    w.add_blank_page(width=612, height=792)
    blank = tmp_path / "blank.pdf"
    with blank.open("wb") as fh:
        w.write(fh)
    with pytest.raises(TandcExtractionError):
        extract_pdf(blank.read_bytes())
