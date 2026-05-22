"""uvicorn launcher for `tandc serve`. Translates env/socket failures into TandcErrors."""

from __future__ import annotations

import logging
import os

import uvicorn

from tandc.errors import TandcConfigError, TandcError
from tandc.web.app import create_app

log = logging.getLogger(__name__)


class TandcServerPortInUse(TandcError):
    """The port we asked uvicorn to bind to is already in use."""


# Module-level app for uvicorn --reload, which requires an import string.
app = create_app()


def run(*, host: str, port: int, reload: bool) -> None:
    """Pre-flight + launch uvicorn.

    Raises TandcConfigError if ANTHROPIC_API_KEY is unset.
    Raises TandcServerPortInUse if uvicorn fails with EADDRINUSE.
    """
    if not os.environ.get("ANTHROPIC_API_KEY"):
        raise TandcConfigError(
            "ANTHROPIC_API_KEY is not set — export it before running `tandc serve`"
        )

    target = "tandc.web.serve:app" if reload else app
    log.info("tandc serve listening on http://%s:%d", host, port)
    try:
        uvicorn.run(target, host=host, port=port, reload=reload)
    except OSError as e:
        if e.errno in (48, 98):  # EADDRINUSE on darwin / linux
            raise TandcServerPortInUse(
                f"port {port} is already in use on {host}; pick another with --port"
            ) from e
        raise
