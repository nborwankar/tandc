from unittest.mock import patch

from typer.testing import CliRunner

from tandc.cli import app
from tandc.core.schema import AnalysisReport
from tests.test_schema import _valid_report_dict


runner = CliRunner()


def _report():
    return AnalysisReport(**_valid_report_dict())


def test_version_command():
    result = runner.invoke(app, ["version"])
    assert result.exit_code == 0
    assert "tandc" in result.stdout


def test_analyze_url_writes_report(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    report = _report()
    with patch("tandc.cli.analyze") as mock_analyze:
        mock_analyze.return_value = (report, tmp_path / "reports" / "x", False)
        (tmp_path / "reports" / "x").mkdir(parents=True)
        result = runner.invoke(app, ["analyze", "https://example.com/terms"])
    assert result.exit_code == 0
    assert mock_analyze.called
    call_kwargs = mock_analyze.call_args.kwargs
    assert call_kwargs["url"] == "https://example.com/terms"
    assert call_kwargs["use_cache"] is True


def test_analyze_no_cache_flag(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    report = _report()
    with patch("tandc.cli.analyze") as mock_analyze:
        mock_analyze.return_value = (report, tmp_path / "reports" / "x", False)
        (tmp_path / "reports" / "x").mkdir(parents=True)
        runner.invoke(app, ["analyze", "https://example.com/terms", "--no-cache"])
        assert mock_analyze.call_args.kwargs["use_cache"] is False


def test_analyze_opus_flag(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    report = _report()
    with patch("tandc.cli.analyze") as mock_analyze:
        mock_analyze.return_value = (report, tmp_path / "reports" / "x", False)
        (tmp_path / "reports" / "x").mkdir(parents=True)
        runner.invoke(app, ["analyze", "https://example.com/terms", "--opus"])
        assert mock_analyze.call_args.kwargs["model"] == "claude-opus-4-7"


def test_analyze_stdin(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    report = _report()
    with patch("tandc.cli.analyze") as mock_analyze:
        mock_analyze.return_value = (report, tmp_path / "reports" / "x", False)
        (tmp_path / "reports" / "x").mkdir(parents=True)
        result = runner.invoke(app, ["analyze", "-"], input="pasted terms text")
        assert result.exit_code == 0
        assert mock_analyze.call_args.kwargs["url"] is None
        assert mock_analyze.call_args.kwargs["stdin"] is not None


def test_analyze_json_flag_emits_json_to_stdout(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    report = _report()
    with patch("tandc.cli.analyze") as mock_analyze:
        mock_analyze.return_value = (report, None, False)
        result = runner.invoke(app, ["analyze", "https://example.com/", "--json"])
    assert result.exit_code == 0
    assert '"schema_version"' in result.stdout
    # --json should pass output_base=None so analyze() does not write artefacts
    assert mock_analyze.call_args.kwargs["output_base"] is None


def test_fetch_error_exit_code_2(tmp_path, monkeypatch):
    from tandc.errors import TandcFetchError

    monkeypatch.chdir(tmp_path)
    with patch("tandc.cli.analyze", side_effect=TandcFetchError("u", 404, "not found")):
        result = runner.invoke(app, ["analyze", "https://example.com/"])
    assert result.exit_code == 2
    assert (
        "fetch failed" in result.stdout.lower()
        or "fetch failed" in result.stderr.lower()
    )


def test_extraction_error_exit_code_2(tmp_path, monkeypatch):
    from tandc.errors import TandcExtractionError

    monkeypatch.chdir(tmp_path)
    with patch(
        "tandc.cli.analyze",
        side_effect=TandcExtractionError(url=None, raw_bytes=8192, extracted_chars=10),
    ):
        result = runner.invoke(app, ["analyze", "https://example.com/"])
    assert result.exit_code == 2
    assert (
        "extraction failed" in result.stdout.lower()
        or "extraction failed" in result.stderr.lower()
    )


def test_analysis_error_exit_code_3(tmp_path, monkeypatch):
    from tandc.errors import TandcAnalysisError

    monkeypatch.chdir(tmp_path)
    with patch("tandc.cli.analyze", side_effect=TandcAnalysisError("bad json twice")):
        result = runner.invoke(app, ["analyze", "https://example.com/"])
    assert result.exit_code == 3


def test_config_error_exit_code_4(tmp_path, monkeypatch):
    from tandc.errors import TandcConfigError

    monkeypatch.chdir(tmp_path)
    with patch("tandc.cli.analyze", side_effect=TandcConfigError("no API key")):
        result = runner.invoke(app, ["analyze", "https://example.com/"])
    assert result.exit_code == 4


def test_cache_clear_refuses_without_yes(tmp_path, monkeypatch):
    monkeypatch.setenv("TANDC_CACHE_DIR", str(tmp_path / "cache"))
    result = runner.invoke(app, ["cache", "clear"])
    assert result.exit_code != 0
    assert "--yes" in result.stdout or "--yes" in result.stderr
