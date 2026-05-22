"""Render AnalysisReport to terminal (rich) and markdown."""

from __future__ import annotations

from rich.console import Console
from rich.markup import escape
from rich.panel import Panel
from rich.table import Table

from tandc.core.schema import AnalysisReport, CoreFinding, FlagFinding

_SEVERITY_STYLE = {
    "low": "green",
    "medium": "yellow",
    "high": "red",
    "critical": "bold red",
}


def _md_safe(s: str) -> str:
    """Neutralise characters that would break the surrounding markdown structure."""
    # Pipe corrupts table rows; newline can extend blockquotes or break table layout.
    return s.replace("|", "\\|").replace("\n", " ")


def _content_type_line(report: AnalysisReport) -> str:
    fm = report.fetch_meta
    if fm.source == "stdin":
        return "Input: stdin (no Content-Type)"
    return (
        f"Fetched: {fm.url} "
        f"(Content-Type: {fm.content_type or 'unknown'}, "
        f"plain={fm.content_type_was_plain}, "
        f"{fm.raw_bytes // 1024} KiB)"
    )


def to_terminal(report: AnalysisReport, console: Console | None = None) -> None:
    """Print a rich-formatted report to the terminal."""
    console = console or Console()
    overall_style = _SEVERITY_STYLE.get(report.overall_risk, "white")
    console.print()
    console.print(
        Panel(
            f"[{overall_style}]{escape(report.headline)}[/{overall_style}]\n\n"
            f"Overall risk: [{overall_style}]{report.overall_risk.upper()}[/{overall_style}]   "
            f"Model: {escape(report.model)}",
            title="tandc report",
            border_style=overall_style,
        )
    )
    console.print(_content_type_line(report))
    console.print()

    table = Table(title="Core findings", show_lines=True)
    table.add_column("Category", style="bold")
    table.add_column("Severity")
    table.add_column("Summary")
    for f in report.core_findings:
        style = _SEVERITY_STYLE.get(f.severity, "white")
        table.add_row(
            f.category,
            f"[{style}]{f.severity}[/{style}]",
            f"{escape(f.summary)}\n[dim]Why: {escape(f.why_it_matters)}[/dim]",
        )
    console.print(table)

    flags_table = Table(title="Flags", show_lines=False)
    flags_table.add_column("Category", style="bold")
    flags_table.add_column("Presence")
    flags_table.add_column("Note")
    for f in report.flags:
        flags_table.add_row(f.category, f.presence, escape(f.note))
    console.print(flags_table)

    if report.notes:
        console.print()
        console.print("[dim]Notes:[/dim]")
        for n in report.notes:
            console.print(f"  - {escape(n)}")


def _core_section(f: CoreFinding) -> str:
    quotes = "\n".join(
        f"> {_md_safe(e.quote)}  *(chars {e.char_start}–{e.char_end})*"
        for e in f.evidence
    )
    return (
        f"### {f.category} — **{f.severity.upper()}**\n\n"
        f"{f.summary}\n\n"
        f"*Why it matters:* {f.why_it_matters}\n\n"
        f"**Evidence:**\n\n{quotes}\n"
    )


def _flag_row(f: FlagFinding) -> str:
    return f"| {f.category} | {f.presence} | {_md_safe(f.note)} |"


def to_markdown(report: AnalysisReport) -> str:
    """Render the report as Markdown for `report.md`."""
    lines = [
        f"# {report.headline}",
        "",
        f"**Overall risk:** {report.overall_risk.upper()}",
        f"**Model:** {report.model}",
        f"**Analyzed:** {report.analyzed_at.isoformat()}",
        f"**Taxonomy:** {report.taxonomy_version} (schema {report.schema_version})",
        "",
        f"_{_content_type_line(report)}_",
        "",
        "## Core findings",
        "",
    ]
    for f in report.core_findings:
        lines.append(_core_section(f))
    lines.append("## Flags")
    lines.append("")
    lines.append("| Category | Presence | Note |")
    lines.append("|----------|----------|------|")
    for f in report.flags:
        lines.append(_flag_row(f))
    if report.notes:
        lines.extend(["", "## Notes", ""] + [f"- {n}" for n in report.notes])
    return "\n".join(lines) + "\n"
