"""FastAPI app factory: mounts api router, static files, exception handlers."""

from __future__ import annotations

import logging
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from tandc.errors import (
    TandcAnalysisError,
    TandcConfigError,
    TandcError,
    TandcExtractionError,
    TandcFetchError,
)
from tandc.web.api import router as analyze_router

log = logging.getLogger(__name__)

_STATIC_DIR = Path(__file__).parent / "static"


def create_app() -> FastAPI:
    app = FastAPI(
        title="tandc",
        description="Local UI for the Terms & Conditions risk analyzer.",
        version="0.1.0",
    )
    app.include_router(analyze_router)

    _register_exception_handlers(app)

    @app.get("/", include_in_schema=False)
    def root() -> FileResponse:
        return FileResponse(_STATIC_DIR / "index.html")

    app.mount(
        "/static",
        StaticFiles(directory=_STATIC_DIR),
        name="static",
    )
    return app


def _error_body(name: str, message: str, detail: dict | None = None) -> dict:
    body: dict = {"error": name, "message": message}
    if detail is not None:
        body["detail"] = detail
    return body


def _register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(HTTPException)
    async def _http_exc(request: Request, exc: HTTPException):
        # Pass-through structured error dicts from api.py raises (415/422/etc).
        if isinstance(exc.detail, dict) and "error" in exc.detail:
            return JSONResponse(status_code=exc.status_code, content=exc.detail)
        return JSONResponse(
            status_code=exc.status_code,
            content=_error_body("HTTPException", str(exc.detail)),
        )

    @app.exception_handler(TandcFetchError)
    async def _fetch(request: Request, exc: TandcFetchError):
        log.warning("fetch error: %s", exc)
        return JSONResponse(
            status_code=502,
            content=_error_body(
                "TandcFetchError",
                str(exc),
                {"url": exc.url, "status": exc.status},
            ),
        )

    @app.exception_handler(TandcExtractionError)
    async def _extract(request: Request, exc: TandcExtractionError):
        log.warning("extraction error: %s", exc)
        return JSONResponse(
            status_code=400,
            content=_error_body(
                "TandcExtractionError",
                str(exc),
                {
                    "url": exc.url,
                    "raw_bytes": exc.raw_bytes,
                    "extracted_chars": exc.extracted_chars,
                },
            ),
        )

    @app.exception_handler(TandcConfigError)
    async def _config(request: Request, exc: TandcConfigError):
        log.warning("config error: %s", exc)
        return JSONResponse(
            status_code=503,
            content=_error_body("TandcConfigError", str(exc)),
        )

    @app.exception_handler(TandcAnalysisError)
    async def _analysis(request: Request, exc: TandcAnalysisError):
        log.warning("analysis error: %s", exc)
        return JSONResponse(
            status_code=500,
            content=_error_body("TandcAnalysisError", str(exc)),
        )

    @app.exception_handler(TandcError)
    async def _catchall(request: Request, exc: TandcError):
        log.warning("tandc error (catch-all): %s", exc)
        return JSONResponse(
            status_code=500,
            content=_error_body("TandcError", str(exc)),
        )
