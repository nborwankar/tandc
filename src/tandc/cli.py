"""tandc CLI — thin wrapper around tandc.core.analyze."""

from __future__ import annotations

import logging
import sys
from pathlib import Path

import typer
from rich.console import Console

from tandc import __version__
from tandc.core import analyze
from tandc.core.analyzer import MODEL_OPUS, MODEL_SONNET
from tandc.core.paths import cache_dir
from tandc.core.render import to_terminal
from tandc.errors import (
    TandcAnalysisError,
    TandcConfigError,
    TandcError,
    TandcExtractionError,
    TandcFetchError,
)

app = typer.Typer(help="Terms & Conditions risk analyzer", no_args_is_help=True)
cache_app = typer.Typer(help="Manage the on-disk cache")
app.add_typer(cache_app, name="cache")

console = Console()
err_console = Console(stderr=True)


def _setup_logging(debug: bool) -> None:
    level = logging.DEBUG if debug else logging.INFO
    logging.basicConfig(
        format="%(asctime)s %(levelname)s %(name)s: %(message)s", level=level
    )
    if debug:
        logging.getLogger("httpx").setLevel(logging.DEBUG)
        logging.getLogger("anthropic").setLevel(logging.DEBUG)


@app.command()
def version() -> None:
    """Print tandc version."""
    console.print(f"tandc {__version__}")


def analyze_cmd(
    source: str = typer.Argument(
        ..., metavar="URL|-", help="URL to fetch, or '-' for stdin"
    ),
    opus: bool = typer.Option(
        False, "--opus", help="Use claude-opus-4-7 instead of sonnet"
    ),
    no_cache: bool = typer.Option(
        False, "--no-cache", help="Bypass cache for this call"
    ),
    output_dir: Path | None = typer.Option(
        None, "--output-dir", help="Where to write reports/ (default: CWD)"
    ),
    json_only: bool = typer.Option(
        False,
        "--json",
        help="Emit JSON to stdout; do not write report dir or render terminal",
    ),
    debug: bool = typer.Option(False, "--debug", help="Enable DEBUG logging"),
) -> None:
    """Analyze a T&C / privacy policy by URL or pasted stdin."""
    _setup_logging(debug)
    model = MODEL_OPUS if opus else MODEL_SONNET

    if source == "-":
        url: str | None = None
        stdin = sys.stdin
    else:
        url = source
        stdin = None

    # Resolve output_base at call time (not import time) so monkeypatch.chdir works in tests
    output_base = None if json_only else (output_dir or Path.cwd())

    try:
        report, rdir, _cache_hit = analyze(
            url=url,
            stdin=stdin,
            model=model,
            use_cache=not no_cache,
            output_base=output_base,
        )
    except TandcFetchError as e:
        err_console.print(f"[red]fetch failed:[/red] {e}")
        raise typer.Exit(code=2)
    except TandcExtractionError as e:
        err_console.print(f"[red]extraction failed:[/red] {e}")
        raise typer.Exit(code=2)
    except TandcConfigError as e:
        err_console.print(f"[red]config error:[/red] {e}")
        raise typer.Exit(code=4)
    except TandcAnalysisError as e:
        err_console.print(f"[red]analysis failed:[/red] {e}")
        raise typer.Exit(code=3)
    except TandcError as e:
        # Future-proof fallback for any new TandcError subclass added later.
        err_console.print(f"[red]error:[/red] {e}")
        raise typer.Exit(code=1)

    if json_only:
        # Write to stdout for piping
        typer.echo(report.model_dump_json(indent=2))
        return

    to_terminal(report, console=console)
    if rdir is not None:
        console.print(f"\n[dim]Wrote {rdir}/[/dim]")


# Register under the CLI name "analyze" (not "analyze-cmd")
app.command(name="analyze")(analyze_cmd)


@cache_app.command("list")
def cache_list(
    limit: int = typer.Option(20, "--limit", help="Show this many entries")
) -> None:
    """List cached reports."""
    d = cache_dir()
    if not d.exists():
        console.print("(cache is empty)")
        return
    files = sorted(d.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)[
        :limit
    ]
    if not files:
        console.print("(cache is empty)")
        return
    import json

    for f in files:
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
            model = data.get("model", "?")
            tax = data.get("taxonomy_version", "?")
            host = (data.get("fetch_meta") or {}).get("url") or "stdin"
            analyzed = data.get("analyzed_at", "?")
            console.print(f"{f.stem[:12]}  {model}  tax={tax}  {analyzed}  {host}")
        except Exception as e:
            console.print(f"{f.stem[:12]}  [red]unreadable: {e}[/red]")


@cache_app.command("clear")
def cache_clear(
    yes: bool = typer.Option(False, "--yes", help="Required to actually delete"),
) -> None:
    """Clear all cached reports. Requires --yes."""
    if not yes:
        err_console.print(
            "refusing to clear cache without --yes (project policy: ASK before deleting)"
        )
        raise typer.Exit(code=1)
    d = cache_dir()
    if not d.exists():
        console.print("(cache is empty)")
        return
    removed = 0
    for f in d.glob("*.json"):
        f.unlink()
        removed += 1
    console.print(f"removed {removed} cache entries from {d}")


# --- web serve subcommand -----------------------------------------------------


def _serve_run(*, host: str, port: int, reload: bool) -> None:
    """Indirection so tests can patch the entry point without touching uvicorn."""
    from tandc.web.serve import run as _run

    _run(host=host, port=port, reload=reload)


@app.command()
def serve(
    host: str = typer.Option("127.0.0.1", "--host", help="Bind address"),
    port: int = typer.Option(8765, "--port", help="Listen port"),
    reload: bool = typer.Option(False, "--reload", help="uvicorn auto-reload"),
    debug: bool = typer.Option(False, "--debug", help="Enable DEBUG logging"),
) -> None:
    """Launch the local web UI at http://host:port."""
    _setup_logging(debug)
    try:
        _serve_run(host=host, port=port, reload=reload)
    except TandcConfigError as e:
        err_console.print(f"[red]config error:[/red] {e}")
        raise typer.Exit(code=4)
    except Exception as e:
        # TandcServerPortInUse and any other TandcError surface here. We import
        # TandcServerPortInUse lazily so cli import doesn't pull in uvicorn.
        from tandc.web.serve import TandcServerPortInUse

        if isinstance(e, TandcServerPortInUse):
            err_console.print(f"[red]port error:[/red] {e}")
            raise typer.Exit(code=5)
        if isinstance(e, TandcError):
            err_console.print(f"[red]error:[/red] {e}")
            raise typer.Exit(code=1)
        raise
