import pytest

from tandc.core.extract import extract_text, is_plain_text_content_type


class TestIsPlainTextContentType:
    def test_plain(self):
        assert is_plain_text_content_type("text/plain") is True
        assert is_plain_text_content_type("text/plain; charset=utf-8") is True

    def test_html(self):
        assert is_plain_text_content_type("text/html") is False
        assert is_plain_text_content_type("text/html; charset=utf-8") is False

    def test_none(self):
        assert is_plain_text_content_type(None) is False

    def test_other(self):
        assert is_plain_text_content_type("application/json") is False


class TestExtractText:
    def test_html_extraction(self):
        html = """
        <html><body>
            <nav>nav junk</nav>
            <main>
              <h1>Terms of Service</h1>
              <p>We collect your personal data and may share it with partners.</p>
              <p>This is a sufficiently long paragraph to satisfy the extraction
                 threshold for trafilatura's main-content heuristics. Lorem ipsum
                 dolor sit amet, consectetur adipiscing elit, sed do eiusmod
                 tempor incididunt ut labore et dolore magna aliqua.</p>
            </main>
            <footer>cookie banner stuff</footer>
        </body></html>
        """
        text, extractor = extract_text(html, content_type="text/html")
        assert extractor == "trafilatura"
        assert "personal data" in text
        assert "nav junk" not in text
        assert "cookie banner" not in text

    def test_plain_text_returned_as_is(self):
        body = "These are the terms. We collect data."
        text, extractor = extract_text(body, content_type="text/plain")
        assert text == body
        assert extractor == "raw"

    def test_returns_none_on_empty_extraction(self):
        text, extractor = extract_text("<html></html>", content_type="text/html")
        assert text is None
        assert extractor == "trafilatura"

    def test_normalises_smart_quotes_in_plain_text(self):
        """LLMs return ASCII quotes; we normalise at extraction so 'verbatim
        substring' evidence checks pass downstream."""
        body = "We won’t share “your data” — see section–3."
        text, _ = extract_text(body, content_type="text/plain")
        assert "’" not in text and "“" not in text and "”" not in text
        assert "–" not in text and "—" not in text
        assert text == 'We won\'t share "your data" - see section-3.'

    def test_normalises_smart_quotes_in_extracted_html(self):
        html = (
            "<html><body><main><p>"
            "We won’t share your data. Per “Section 4,” we may. "
            "Lorem ipsum dolor sit amet, consectetur adipiscing elit, sed do "
            "eiusmod tempor incididunt ut labore et dolore magna aliqua."
            "</p></main></body></html>"
        )
        text, _ = extract_text(html, content_type="text/html")
        assert text is not None
        assert "’" not in text
        assert "“" not in text
        assert "won't share" in text
        assert '"Section 4,"' in text
