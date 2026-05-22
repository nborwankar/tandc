import io
from datetime import datetime, timezone

import httpx
import pytest
import respx

from tandc.core.loader import stdin_to_text, text_to_meta, url_to_text
from tandc.errors import TandcExtractionError, TandcFetchError


HTML_BODY = """
<html><body><main>
<h1>Terms</h1>
<p>We collect your data and may share it with partners. Lorem ipsum dolor
sit amet, consectetur adipiscing elit, sed do eiusmod tempor incididunt
ut labore et dolore magna aliqua. Sufficient text for extraction.</p>
</main></body></html>
"""


@respx.mock
def test_url_to_text_success_html():
    url = "https://example.com/terms"
    respx.get(url).mock(
        return_value=httpx.Response(
            200,
            text=HTML_BODY,
            headers={"Content-Type": "text/html; charset=utf-8"},
        )
    )
    text, meta = url_to_text(url)
    assert "collect" in text.lower()  # trafilatura extracted the main body
    assert meta.source == "url"
    assert meta.url == url
    assert meta.http_status == 200
    assert meta.content_type == "text/html; charset=utf-8"
    assert meta.content_type_was_plain is False
    assert meta.extractor == "trafilatura"
    assert meta.raw_bytes == len(HTML_BODY.encode("utf-8"))
    assert meta.extracted_chars == len(text)


@respx.mock
def test_url_to_text_plain_text_content_type():
    url = "https://example.com/terms.txt"
    body = "These are the terms of service. We collect personal data."
    respx.get(url).mock(
        return_value=httpx.Response(
            200,
            text=body,
            headers={"Content-Type": "text/plain"},
        )
    )
    text, meta = url_to_text(url)
    assert text == body
    assert meta.content_type_was_plain is True
    assert meta.extractor == "raw"


@respx.mock
def test_url_to_text_http_error_raises():
    url = "https://example.com/nope"
    respx.get(url).mock(return_value=httpx.Response(404, text="not found"))
    with pytest.raises(TandcFetchError) as exc:
        url_to_text(url)
    assert exc.value.status == 404
    assert exc.value.url == url


@respx.mock
def test_url_to_text_network_error_raises():
    url = "https://example.com/timeout"
    respx.get(url).mock(side_effect=httpx.ConnectTimeout("timeout"))
    with pytest.raises(TandcFetchError) as exc:
        url_to_text(url)
    assert exc.value.url == url
    assert exc.value.status is None


@respx.mock
def test_url_to_text_empty_extraction_raises():
    url = "https://example.com/empty"
    respx.get(url).mock(
        return_value=httpx.Response(
            200,
            text="<html></html>",
            headers={"Content-Type": "text/html"},
        )
    )
    with pytest.raises(TandcExtractionError):
        url_to_text(url)


def test_stdin_to_text_success():
    src = io.StringIO(
        "These are pasted terms. We collect data and share with partners."
    )
    text, meta = stdin_to_text(src)
    assert text.startswith("These are pasted terms.")
    assert meta.source == "stdin"
    assert meta.url is None
    assert meta.extractor is None
    assert meta.content_type_was_plain is False
    assert meta.extracted_chars == len(text)


def test_stdin_to_text_empty_raises():
    src = io.StringIO("")
    with pytest.raises(TandcExtractionError):
        stdin_to_text(src)


def test_text_to_meta_paste_with_source_url():
    text, meta = text_to_meta(
        text="We collect your data.",
        source="paste",
        source_url="https://example.com/terms",
    )
    assert text == "We collect your data."
    assert meta.source == "paste"
    assert meta.url == "https://example.com/terms"
    assert meta.extracted_chars == len(text)
    assert meta.raw_bytes == len(text.encode("utf-8"))


def test_text_to_meta_paste_without_source_url():
    text, meta = text_to_meta(text="Hello world.", source="paste")
    assert meta.url is None
    assert meta.source == "paste"


def test_text_to_meta_file_records_content_type_and_filename():
    text, meta = text_to_meta(
        text="Policy body extracted from PDF.",
        source="file",
        filename="terms.pdf",
        content_type="application/pdf",
    )
    assert meta.source == "file"
    assert meta.content_type == "application/pdf"
    # filename is informational; we encode it into url field as filename:NAME so
    # the report's fetch_meta carries it forward without changing the schema.
    assert meta.url == "file:terms.pdf"


def test_text_to_meta_empty_text_raises():
    with pytest.raises(TandcExtractionError):
        text_to_meta(text="   \n   ", source="paste")


def test_text_to_meta_normalises_unicode():
    text, meta = text_to_meta(text="We “may” share data.", source="paste")
    # smart quotes round-trip to ASCII via core.extract._normalise_text
    assert "“" not in text and "”" not in text
    assert '"may"' in text
