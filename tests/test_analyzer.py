import json
from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest

from tandc.core.analyzer import MODEL_OPUS, MODEL_SONNET, analyze_text
from tandc.core.schema import AnalysisReport, FetchMeta
from tandc.errors import TandcAnalysisError
from tests.test_schema import _valid_report_dict


def _stub_fetch_meta() -> FetchMeta:
    return FetchMeta(
        source="stdin",
        url=None,
        fetched_at=datetime.now(timezone.utc),
        http_status=None,
        content_type=None,
        content_type_was_plain=False,
        extractor=None,
        raw_bytes=100,
        extracted_chars=50,
    )


def _claude_response_with(payload: dict):
    """Return a mock matching anthropic SDK response shape: content[0].text holds JSON."""
    msg = MagicMock()
    block = MagicMock()
    block.type = "text"
    block.text = json.dumps(payload)
    msg.content = [block]
    return msg


def _stub_claude_client(*responses):
    """Mock anthropic.Anthropic() whose .messages.create returns each response in sequence."""
    client = MagicMock()
    client.messages.create.side_effect = list(responses)
    return client


def test_analyze_text_happy_path():
    payload = _valid_report_dict()
    client = _stub_claude_client(_claude_response_with(payload))
    report = analyze_text(
        text="Sample policy text",
        fetch_meta=_stub_fetch_meta(),
        client=client,
        model=MODEL_SONNET,
    )
    assert isinstance(report, AnalysisReport)
    assert report.model == MODEL_SONNET
    assert client.messages.create.call_count == 1


def test_analyze_text_invalid_first_then_valid_retries_once():
    bad = {"not": "a valid report"}
    good = _valid_report_dict()
    client = _stub_claude_client(
        _claude_response_with(bad),
        _claude_response_with(good),
    )
    report = analyze_text(
        text="Sample",
        fetch_meta=_stub_fetch_meta(),
        client=client,
        model=MODEL_SONNET,
    )
    assert isinstance(report, AnalysisReport)
    assert client.messages.create.call_count == 2


def test_analyze_text_two_failures_raises():
    bad1 = {"not": "valid"}
    bad2 = {"still": "not valid"}
    client = _stub_claude_client(
        _claude_response_with(bad1),
        _claude_response_with(bad2),
    )
    with pytest.raises(TandcAnalysisError):
        analyze_text(
            text="Sample",
            fetch_meta=_stub_fetch_meta(),
            client=client,
            model=MODEL_SONNET,
        )
    assert client.messages.create.call_count == 2


def test_analyze_text_uses_opus_when_requested():
    payload = _valid_report_dict()
    client = _stub_claude_client(_claude_response_with(payload))
    analyze_text(
        text="Sample",
        fetch_meta=_stub_fetch_meta(),
        client=client,
        model=MODEL_OPUS,
    )
    call_kwargs = client.messages.create.call_args.kwargs
    assert call_kwargs["model"] == MODEL_OPUS


def test_analyze_text_sets_input_hash_from_text():
    import hashlib

    payload = _valid_report_dict()
    client = _stub_claude_client(_claude_response_with(payload))
    report = analyze_text(
        text="exact text",
        fetch_meta=_stub_fetch_meta(),
        client=client,
        model=MODEL_SONNET,
    )
    expected = hashlib.sha256("exact text".encode("utf-8")).hexdigest()
    assert report.input_hash == expected


def test_analyze_text_strips_markdown_code_fences():
    """Claude sometimes wraps JSON in ```json ... ``` even when asked not to."""
    payload = _valid_report_dict()
    msg = MagicMock()
    block = MagicMock()
    block.type = "text"
    block.text = f"```json\n{json.dumps(payload)}\n```"
    msg.content = [block]
    client = MagicMock()
    client.messages.create.return_value = msg
    report = analyze_text(
        text="x",
        fetch_meta=_stub_fetch_meta(),
        client=client,
        model=MODEL_SONNET,
    )
    assert isinstance(report, AnalysisReport)
