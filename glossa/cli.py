"""Glossa CLI — `glossa ask` and `glossa notebook ...`."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import click
from rich.console import Console
from rich.panel import Panel

from glossa import __version__
from glossa.config import GlossaConfig
from glossa.notebook import NotebookError, NotebookManager
from glossa.provider import NotebookLMError, NotebookLMProvider


console = Console()


def _project_root() -> Path:
    return Path.cwd()


@click.group()
@click.version_option(__version__, prog_name="glossa")
def main() -> None:
    """Glossa — Marginalia for the AI age."""


# ---------------------------------------------------------------------------
# notebook subcommands
# ---------------------------------------------------------------------------


@main.group()
def notebook() -> None:
    """Manage the Glossa notebook for this project."""


@notebook.command("init")
@click.argument("paths", nargs=-1, required=True, type=click.Path(exists=True, path_type=Path))
@click.option("--title", default="Glossa Knowledge Base", help="Notebook title.")
def notebook_init(paths: tuple[Path, ...], title: str) -> None:
    """Create a notebook and upload the given files/directories as sources."""
    try:
        mgr = NotebookManager(_project_root())
        console.print(f"[dim]Creating notebook '{title}'...[/dim]")
        mgr.init(list(paths), title=title)
        console.print(
            f"[green]✓[/green] Notebook initialized: [bold]{mgr.config.notebook_id}[/bold]"
        )
        console.print(f"  {len(mgr.config.sources)} source file(s) uploaded.")
        console.print("[dim]Note: NotebookLM is indexing sources; first ask may be slow.[/dim]")
    except NotebookError as e:
        console.print(f"[red]✗[/red] {e}")
        sys.exit(1)


@notebook.command("sync")
def notebook_sync() -> None:
    """Hash-based incremental sync of tracked sources."""
    try:
        mgr = NotebookManager(_project_root())
        actions = mgr.sync()
        changed = sum(1 for v in actions.values() if v != "unchanged")
        for path, action in sorted(actions.items()):
            colour = "green" if action == "re-uploaded" else "dim"
            console.print(f"  [{colour}]{action:<20}[/{colour}] {path}")
        console.print(
            f"\n[bold]{changed}[/bold] file(s) re-uploaded; {len(actions) - changed} unchanged."
        )
    except NotebookError as e:
        console.print(f"[red]✗[/red] {e}")
        sys.exit(1)


@notebook.command("status")
def notebook_status() -> None:
    """Show notebook ID, title, and tracked sources."""
    mgr = NotebookManager(_project_root())
    s = mgr.status()
    if not s["initialized"]:
        console.print("[yellow]No notebook initialized in this directory.[/yellow]")
        console.print("Run [bold]glossa notebook init <paths>[/bold] to create one.")
        return
    console.print(
        Panel.fit(
            f"[bold]{s['title']}[/bold]\nID: {s['notebook_id']}\nSources: {s['source_count']}",
            title="Glossa Notebook",
        )
    )
    for src in s["sources"]:
        console.print(f"  • {src}")


# ---------------------------------------------------------------------------
# ask
# ---------------------------------------------------------------------------


@main.command("ask")
@click.argument("question", required=True)
@click.option("--json", "as_json", is_flag=True, help="Output raw JSON.")
@click.option("--show-sources", is_flag=True, help="Print citations alongside the answer.")
@click.option("--system", default=None, help="Optional system-style preamble.")
def ask(question: str, as_json: bool, show_sources: bool, system: str | None) -> None:
    """Ask a source-grounded question."""
    cfg = GlossaConfig.load(_project_root())
    if not cfg.is_initialized():
        console.print(
            "[red]✗[/red] No notebook initialized. Run [bold]glossa notebook init <paths>[/bold]."
        )
        sys.exit(1)

    try:
        provider = NotebookLMProvider(cfg.notebook_id)
        response = provider.ask(question, system=system)
    except NotebookLMError as e:
        console.print(f"[red]✗[/red] {e}")
        sys.exit(1)

    if as_json:
        click.echo(json.dumps(response.raw, indent=2))
        return

    console.print(response.answer)
    if show_sources and response.references:
        console.print("\n[dim]Sources:[/dim]")
        for ref in response.references:
            snippet = ref.cited_text[:120].replace("\n", " ")
            console.print(f"  [{ref.citation_number}] {snippet}…")


if __name__ == "__main__":
    main()
