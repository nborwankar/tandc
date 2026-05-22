import io

from rich.console import Console

from tandc.core.render import to_markdown, to_terminal
from tandc.core.schema import AnalysisReport
from tests.test_schema import _valid_report_dict


def _report() -> AnalysisReport:
    return AnalysisReport(**_valid_report_dict())


class TestToMarkdown:
    def test_includes_headline(self):
        md = to_markdown(_report())
        assert "Service collects data and uses arbitration." in md

    def test_lists_all_core_categories(self):
        md = to_markdown(_report())
        for cat in (
            "personal_data",
            "pii_protection",
            "continuity",
            "liability_dispute",
        ):
            assert cat in md

    def test_lists_all_flag_categories(self):
        md = to_markdown(_report())
        for cat in (
            "content_licensing",
            "account_access",
            "payment_subscription",
            "jurisdictional",
        ):
            assert cat in md

    def test_includes_evidence_quotes(self):
        md = to_markdown(_report())
        assert "we share your data" in md

    def test_includes_content_type_line(self):
        md = to_markdown(_report())
        assert "Content-Type" in md
        assert "text/html" in md


class TestToTerminal:
    def test_writes_headline_to_console(self):
        report = _report()
        buf = io.StringIO()
        console = Console(file=buf, width=120, force_terminal=False, no_color=True)
        to_terminal(report, console=console)
        out = buf.getvalue()
        assert "Service collects data and uses arbitration." in out

    def test_writes_content_type_summary(self):
        report = _report()
        buf = io.StringIO()
        console = Console(file=buf, width=120, force_terminal=False, no_color=True)
        to_terminal(report, console=console)
        out = buf.getvalue()
        assert "Content-Type" in out
        assert "plain=False" in out

    def test_does_not_choke_on_rich_markup_in_free_text(self):
        """Claude's output may contain '[' etc.; rich.markup.escape() must neutralise."""
        d = _valid_report_dict()
        d["headline"] = "Use [bold]caution[/bold] — terms have [unmatched"
        d["core_findings"][0]["summary"] = "We collect data; see [Section 4]."
        d["core_findings"][0]["why_it_matters"] = "Your [PII] leaves the service."
        d["flags"][0]["note"] = "License grants [worldwide] rights."
        d["notes"] = ["[important] note with brackets"]
        report = AnalysisReport(**d)
        buf = io.StringIO()
        console = Console(file=buf, width=120, force_terminal=False, no_color=True)
        to_terminal(report, console=console)  # must not raise
        out = buf.getvalue()
        # Headline brackets should appear literally, not be interpreted as styles
        assert "[bold]caution[/bold]" in out

    def test_markdown_pipe_in_flag_note_is_escaped(self):
        """Pipes in flag note would corrupt the markdown table row."""
        d = _valid_report_dict()
        d["flags"][0]["note"] = "alpha | beta | gamma"
        report = AnalysisReport(**d)
        md = to_markdown(report)
        row_lines = [line for line in md.splitlines() if "alpha" in line]
        assert len(row_lines) == 1
        # The two body pipes must be backslash-escaped so the table parser sees them as text
        assert row_lines[0].count("\\|") == 2
        # And the original literal text round-trips when the backslashes are removed
        assert "alpha \\| beta \\| gamma" in row_lines[0]
