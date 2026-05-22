from unittest.mock import patch

from typer.testing import CliRunner

from tandc.cli import app


runner = CliRunner()


def test_serve_command_invokes_web_run_with_defaults(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "x")
    with patch("tandc.cli._serve_run") as m_run:
        result = runner.invoke(app, ["serve"])
    assert result.exit_code == 0, result.output
    m_run.assert_called_once_with(host="127.0.0.1", port=8765, reload=False)


def test_serve_command_passes_host_port_reload(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "x")
    with patch("tandc.cli._serve_run") as m_run:
        result = runner.invoke(
            app, ["serve", "--host", "0.0.0.0", "--port", "9000", "--reload"]
        )
    assert result.exit_code == 0, result.output
    m_run.assert_called_once_with(host="0.0.0.0", port=9000, reload=True)


def test_serve_command_exits_4_on_missing_api_key(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    from tandc.errors import TandcConfigError

    with patch("tandc.cli._serve_run") as m_run:
        m_run.side_effect = TandcConfigError("ANTHROPIC_API_KEY is not set")
        result = runner.invoke(app, ["serve"])
    assert result.exit_code == 4, result.output
    assert "config error" in result.output.lower()


def test_serve_command_exits_5_on_port_in_use(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "x")
    from tandc.web.serve import TandcServerPortInUse

    with patch("tandc.cli._serve_run") as m_run:
        m_run.side_effect = TandcServerPortInUse("port 8765 already in use")
        result = runner.invoke(app, ["serve"])
    assert result.exit_code == 5, result.output
    assert "port" in result.output.lower()
