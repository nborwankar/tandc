"""Behavioural tests for the uvicorn launcher wrapper (no real socket bind)."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from tandc.errors import TandcConfigError
from tandc.web import serve as serve_mod


def test_run_raises_config_error_without_api_key(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    with pytest.raises(TandcConfigError):
        serve_mod.run(host="127.0.0.1", port=8765, reload=False)


def test_run_invokes_uvicorn_with_args(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "x")
    with patch.object(serve_mod, "uvicorn") as mock_uv:
        serve_mod.run(host="127.0.0.1", port=9999, reload=False)
    mock_uv.run.assert_called_once()
    _, kwargs = mock_uv.run.call_args
    assert kwargs["host"] == "127.0.0.1"
    assert kwargs["port"] == 9999
    assert kwargs["reload"] is False


def test_run_reload_uses_import_string(monkeypatch):
    """uvicorn requires the app target as an import string when reload=True."""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "x")
    with patch.object(serve_mod, "uvicorn") as mock_uv:
        serve_mod.run(host="127.0.0.1", port=8765, reload=True)
    args, _ = mock_uv.run.call_args
    assert args[0] == "tandc.web.serve:app"


def test_run_translates_oserror_to_port_in_use(monkeypatch):
    """Port-in-use surfaces as TandcServerPortInUse so the CLI can exit 5."""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "x")

    def _raise(*a, **kw):
        raise OSError(48, "Address already in use")

    with patch.object(serve_mod, "uvicorn") as mock_uv:
        mock_uv.run.side_effect = _raise
        with pytest.raises(serve_mod.TandcServerPortInUse):
            serve_mod.run(host="127.0.0.1", port=8765, reload=False)
