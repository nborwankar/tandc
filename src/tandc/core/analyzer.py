"""Claude API analyzer — one validation retry, then surface the failure."""

from __future__ import annotations

import json
import logging
import re
from datetime import datetime, timezone

from pydantic import ValidationError

from tandc.core.paths import sha256_of
from tandc.core.prompt import build_system_prompt, build_user_message
from tandc.core.schema import AnalysisReport, FetchMeta
from tandc.errors import TandcAnalysisError

log = logging.getLogger(__name__)

MODEL_SONNET = "claude-sonnet-4-6"
MODEL_OPUS = "claude-opus-4-7"
MAX_TOKENS = 4096

_FENCE_RE = re.compile(r"^```(?:json)?\s*|\s*```$", re.MULTILINE)


def _strip_fences(text: str) -> str:
    return _FENCE_RE.sub("", text).strip()


def _extract_text(response) -> str:
    for block in response.content:
        if getattr(block, "type", None) == "text":
            return block.text
    raise TandcAnalysisError("Claude response contained no text block")


def _build_messages(
    document_text: str, retry_with_error: str | None = None
) -> list[dict]:
    user_msg = build_user_message(document_text)
    if retry_with_error:
        user_msg = (
            f"Your previous response failed schema validation with this error:\n"
            f"{retry_with_error}\n\n"
            f"Please return valid JSON matching the schema. Document below.\n\n{user_msg}"
        )
    return [{"role": "user", "content": user_msg}]


def _call_claude(
    client, model: str, document_text: str, retry_error: str | None = None
) -> str:
    system = [
        {
            "type": "text",
            "text": build_system_prompt(),
            "cache_control": {"type": "ephemeral"},
        }
    ]
    response = client.messages.create(
        model=model,
        max_tokens=MAX_TOKENS,
        system=system,
        messages=_build_messages(document_text, retry_error),
    )
    return _extract_text(response)


def _parse_report(
    raw: str, fetch_meta: FetchMeta, text: str, model: str
) -> AnalysisReport:
    cleaned = _strip_fences(raw)
    data = json.loads(cleaned)
    # Fill in fields the model is not asked to set — we control them.
    data["model"] = model
    data["analyzed_at"] = datetime.now(timezone.utc).isoformat()
    data["input_hash"] = sha256_of(text)
    data["fetch_meta"] = fetch_meta.model_dump(mode="json")
    return AnalysisReport.model_validate(data)


def analyze_text(
    text: str,
    fetch_meta: FetchMeta,
    client,
    model: str = MODEL_SONNET,
) -> AnalysisReport:
    """Run Claude on `text` and return a validated AnalysisReport.

    One automatic retry on schema validation failure; raises TandcAnalysisError
    if the second attempt is also bad.
    """
    raw = _call_claude(client, model, text)
    try:
        return _parse_report(raw, fetch_meta, text, model)
    except (json.JSONDecodeError, ValidationError) as e:
        log.warning("first Claude response failed validation: %s — retrying once", e)
        raw2 = _call_claude(client, model, text, retry_error=str(e))
        try:
            return _parse_report(raw2, fetch_meta, text, model)
        except (json.JSONDecodeError, ValidationError) as e2:
            raise TandcAnalysisError(
                f"Claude returned malformed output twice. Last error: {e2}. "
                f"Last raw response (first 500 chars): {raw2[:500]}"
            ) from e2
