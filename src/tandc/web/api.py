"""POST /analyze: dispatch URL / paste / file inputs into core analyze pipeline."""

from __future__ import annotations

import logging
import re
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request
from starlette.datastructures import UploadFile
from pydantic import BaseModel, Field, model_validator

from tandc.core import analyze, analyze_prepared
from tandc.core.analyzer import MODEL_OPUS, MODEL_SONNET
from tandc.core.cache import cache_key
from tandc.core.extract import _normalise_text, extract_text
from tandc.core.loader import text_to_meta
from tandc.core.paths import slug_for_url
from tandc.errors import TandcExtractionError
from tandc.web.pdf import extract_pdf

log = logging.getLogger(__name__)

router = APIRouter()

ALLOWED_MIME = {"text/html", "text/plain", "application/pdf"}


class JsonBody(BaseModel):
    """Body for URL or paste mode. Exactly one of url / text must be set."""

    url: str | None = None
    text: str | None = None
    source_url: str | None = None
    model: str = Field(default="sonnet", pattern=r"^(sonnet|opus)$")
    use_cache: bool = True

    @model_validator(mode="after")
    def _exactly_one_of_url_text(self) -> "JsonBody":
        if (self.url is None) == (self.text is None):
            raise ValueError("exactly one of 'url' or 'text' must be provided")
        return self


def _model_id(name: str) -> str:
    return MODEL_OPUS if name == "opus" else MODEL_SONNET


def _serialize(report, rdir: Path | None, cache_hit: bool = False) -> dict:
    return {
        "report": report.model_dump(mode="json"),
        "report_dir": str(rdir.resolve()) if rdir else None,
        "cache_hit": cache_hit,
    }


@router.post("/analyze")
async def post_analyze(request: Request):
    content_type = (request.headers.get("content-type") or "").lower()

    if content_type.startswith("application/json"):
        raw = await request.json()
        try:
            body = JsonBody(**raw)
        except Exception as e:
            # Convert pydantic validation failures (including our model_validator
            # 'exactly one of url/text' rule) to HTTP 422. Re-raise via `from e`
            # so the original cause is preserved in logs — no silent swallow.
            raise HTTPException(
                status_code=422,
                detail={"error": "ValidationError", "message": str(e)},
            ) from e
        return _dispatch_json(body)

    if content_type.startswith("multipart/form-data"):
        form = await request.form()
        return await _dispatch_multipart(form)

    raise HTTPException(
        status_code=415,
        detail={
            "error": "UnsupportedMediaType",
            "message": f"unsupported Content-Type: {content_type!r}",
        },
    )


def _dispatch_json(body: JsonBody) -> dict:
    model = _model_id(body.model)
    output_base = Path.cwd()
    if body.url is not None:
        report, rdir, cache_hit = analyze(
            url=body.url,
            model=model,
            use_cache=body.use_cache,
            output_base=output_base,
        )
        return _serialize(report, rdir, cache_hit)

    text, fetch_meta = text_to_meta(
        text=body.text or "",
        source="paste",
        source_url=body.source_url,
    )
    slug = _slug_for_paste(text, model, body.source_url)
    report, rdir, cache_hit = analyze_prepared(
        text=text,
        fetch_meta=fetch_meta,
        slug=slug,
        model=model,
        use_cache=body.use_cache,
        output_base=output_base,
    )
    return _serialize(report, rdir, cache_hit)


async def _dispatch_multipart(form) -> dict:
    upload = form.get("file")
    if not isinstance(upload, UploadFile):
        raise HTTPException(
            status_code=422,
            detail={"error": "ValidationError", "message": "'file' field is required"},
        )
    mime = (upload.content_type or "").lower()
    if mime not in ALLOWED_MIME:
        raise HTTPException(
            status_code=415,
            detail={
                "error": "UnsupportedMediaType",
                "message": (
                    f"file MIME {mime!r} not supported; "
                    f"allowed: {sorted(ALLOWED_MIME)}"
                ),
            },
        )

    blob = await upload.read()
    if mime == "application/pdf":
        text = extract_pdf(blob)
    elif mime == "text/html":
        extracted, _ext = extract_text(blob.decode("utf-8", errors="replace"), mime)
        if extracted is None:
            raise TandcExtractionError(url=None, raw_bytes=len(blob), extracted_chars=0)
        text = extracted
    else:  # text/plain
        text = _normalise_text(blob.decode("utf-8", errors="replace"))

    _text, fetch_meta = text_to_meta(
        text=text,
        source="file",
        filename=upload.filename,
        content_type=mime,
    )

    model_name = form.get("model", "sonnet")
    use_cache_raw = form.get("use_cache", "true")
    use_cache = str(use_cache_raw).lower() not in {"false", "0", "no"}
    model = _model_id(model_name)

    slug = _slug_for_file(upload.filename, _text, model)
    report, rdir, cache_hit = analyze_prepared(
        text=_text,
        fetch_meta=fetch_meta,
        slug=slug,
        model=model,
        use_cache=use_cache,
        output_base=Path.cwd(),
    )
    return _serialize(report, rdir, cache_hit)


def _slug_for_paste(text: str, model: str, source_url: str | None) -> str:
    if source_url:
        slug = slug_for_url(source_url)
        if slug and slug != "unknown":
            return slug
    return f"paste-{cache_key(text, model)[:8]}"


def _slug_for_file(filename: str | None, text: str, model: str) -> str:
    if filename:
        stem = re.sub(r"[^a-z0-9]+", "-", filename.lower()).strip("-")
        if stem:
            return f"file-{stem[:48]}"
    return f"file-{cache_key(text, model)[:8]}"
