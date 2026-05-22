"""Exception types for tandc. All silent failures are forbidden by project policy."""


class TandcError(Exception):
    """Base class for all tandc errors."""


class TandcConfigError(TandcError):
    """Missing or invalid configuration (e.g. ANTHROPIC_API_KEY)."""


class TandcFetchError(TandcError):
    """URL fetch failed (DNS, timeout, 4xx, 5xx)."""

    def __init__(self, url: str, status: int | None, message: str):
        self.url = url
        self.status = status
        super().__init__(f"fetch failed for {url} (status={status}): {message}")


class TandcExtractionError(TandcError):
    """HTML extraction produced empty or unusably-short text."""

    def __init__(self, url: str | None, raw_bytes: int, extracted_chars: int):
        self.url = url
        self.raw_bytes = raw_bytes
        self.extracted_chars = extracted_chars
        super().__init__(
            f"extraction produced only {extracted_chars} chars from {raw_bytes} raw bytes "
            f"(url={url}); paste the text via stdin instead"
        )


class TandcAnalysisError(TandcError):
    """Claude returned malformed output twice in a row, or a non-recoverable API error."""
