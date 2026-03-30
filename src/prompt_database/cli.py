"""CLI for the prompt injection attack database."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import click
from rich.console import Console
from rich.table import Table

from prompt_database import __version__
from prompt_database.db import PromptDatabase
from prompt_database.ingest import build_database

console = Console()

DEFAULT_DB = Path("prompts.db")


def _resolve_db(ctx: click.Context) -> Path:
    return Path(ctx.obj.get("db", DEFAULT_DB))


@click.group()
@click.version_option(__version__, prog_name="prompt-db")
@click.option("--db", default=str(DEFAULT_DB), envvar="PROMPT_DB_PATH", help="Path to SQLite database")
@click.pass_context
def main(ctx: click.Context, db: str) -> None:
    """Prompt injection attack database for defensive AI security research."""
    ctx.ensure_object(dict)
    ctx.obj["db"] = db


# =============================================================================
# build - create database from JSON sources
# =============================================================================


@main.command()
@click.option("--data-dir", default=".", help="Directory containing JSON source files")
@click.option("--output", "-o", default=str(DEFAULT_DB), help="Output database path")
@click.option("--force", is_flag=True, help="Overwrite existing database")
@click.pass_context
def build(ctx: click.Context, data_dir: str, output: str, force: bool) -> None:
    """Build the database from JSON source files."""
    out_path = Path(output)
    data_path = Path(data_dir)

    if out_path.exists() and not force:
        console.print(f"[red]Database already exists:[/red] {out_path}")
        console.print("Use --force to overwrite.")
        sys.exit(1)

    if out_path.exists() and force:
        out_path.unlink()

    console.print(f"[bold]Building database from[/bold] {data_path}")
    results = build_database(out_path, data_path, verbose=True)

    total_added = sum(r["added"] for r in results.values())
    total_skipped = sum(r["skipped"] for r in results.values())
    console.print(f"\n[green]Done![/green] {total_added} prompts added, {total_skipped} duplicates skipped.")
    console.print(f"Database: {out_path} ({out_path.stat().st_size / 1024 / 1024:.1f} MB)")


# =============================================================================
# stats - show database statistics
# =============================================================================


@main.command()
@click.pass_context
def stats(ctx: click.Context) -> None:
    """Show database statistics."""
    db_path = _resolve_db(ctx)
    if not db_path.exists():
        console.print(f"[red]Database not found:[/red] {db_path}")
        sys.exit(1)

    with PromptDatabase(db_path) as db:
        s = db.stats()

    console.print(f"\n[bold]Prompt Database Statistics[/bold]")
    console.print(f"  Total prompts:      {s['total_prompts']:,}")
    console.print(f"  Verified:           {s['verified']:,}")
    console.print(f"  Curated:            {s['curated']:,}")
    console.print(f"  Test results:       {s['test_results']:,}")
    console.print(f"  Variations:         {s['variations']:,}")
    console.print(f"  Avg sophistication: {s['avg_sophistication']}")

    console.print(f"\n[bold]By Technique[/bold]")
    table = Table(show_header=True)
    table.add_column("Technique", style="cyan")
    table.add_column("Count", justify="right")
    for tech, count in sorted(s["by_technique"].items(), key=lambda x: -x[1]):
        table.add_row(tech, str(count))
    console.print(table)

    console.print(f"\n[bold]By Complexity[/bold]")
    table = Table(show_header=True)
    table.add_column("Complexity", style="yellow")
    table.add_column("Count", justify="right")
    for comp, count in sorted(s["by_complexity"].items(), key=lambda x: -x[1]):
        table.add_row(comp, str(count))
    console.print(table)

    console.print(f"\n[bold]By Source[/bold]")
    table = Table(show_header=True)
    table.add_column("Source", style="green")
    table.add_column("Count", justify="right")
    for src, count in sorted(s["by_source"].items(), key=lambda x: -x[1])[:15]:
        table.add_row(src, str(count))
    console.print(table)


# =============================================================================
# search - full-text search
# =============================================================================


@main.command()
@click.argument("query")
@click.option("--technique", "-t", help="Filter by technique")
@click.option("--complexity", "-c", help="Filter by complexity")
@click.option("--min-score", type=int, help="Minimum sophistication score")
@click.option("--limit", "-n", default=10, help="Max results")
@click.option("--full", is_flag=True, help="Show full prompt content")
@click.option("--json-output", "as_json", is_flag=True, help="Output as JSON")
@click.pass_context
def search(
    ctx: click.Context,
    query: str,
    technique: str | None,
    complexity: str | None,
    min_score: int | None,
    limit: int,
    full: bool,
    as_json: bool,
) -> None:
    """Search prompts by text content."""
    db_path = _resolve_db(ctx)
    if not db_path.exists():
        console.print(f"[red]Database not found:[/red] {db_path}")
        sys.exit(1)

    with PromptDatabase(db_path) as db:
        results = db.search(
            query,
            technique=technique,
            complexity=complexity,
            min_sophistication=min_score,
            limit=limit,
        )

    if as_json:
        click.echo(json.dumps(results, indent=2, default=str))
        return

    if not results:
        console.print("[yellow]No results found.[/yellow]")
        return

    console.print(f"\n[bold]{len(results)} results for[/bold] '{query}'\n")

    for r in results:
        content_preview = r["content"][:120].replace("\n", " ") if not full else r["content"]
        console.print(f"  [cyan]#{r['id']}[/cyan] [{r['technique']}] [{r['complexity']}] score={r['sophistication_score']}")
        console.print(f"    {content_preview}")
        if not full:
            console.print(f"    [dim]source={r['source']}[/dim]")
        console.print()


# =============================================================================
# export - export prompts to various formats
# =============================================================================


@main.command()
@click.option("--format", "fmt", type=click.Choice(["json", "jsonl", "csv"]), default="json")
@click.option("--output", "-o", help="Output file (default: stdout)")
@click.option("--technique", "-t", help="Filter by technique")
@click.option("--min-score", type=int, help="Minimum sophistication score")
@click.option("--verified", is_flag=True, help="Only verified prompts")
@click.option("--limit", "-n", type=int, help="Max prompts to export")
@click.pass_context
def export(
    ctx: click.Context,
    fmt: str,
    output: str | None,
    technique: str | None,
    min_score: int | None,
    verified: bool,
    limit: int | None,
) -> None:
    """Export prompts to JSON, JSONL, or CSV."""
    db_path = _resolve_db(ctx)
    if not db_path.exists():
        console.print(f"[red]Database not found:[/red] {db_path}")
        sys.exit(1)

    with PromptDatabase(db_path) as db:
        prompts = db.export_prompts(
            technique=technique,
            min_sophistication=min_score,
            verified_only=verified,
            limit=limit,
        )

    if fmt == "json":
        text = json.dumps(prompts, indent=2, default=str)
    elif fmt == "jsonl":
        text = "\n".join(json.dumps(p, default=str) for p in prompts)
    elif fmt == "csv":
        import csv
        import io

        buf = io.StringIO()
        if prompts:
            writer = csv.DictWriter(buf, fieldnames=["id", "content", "technique", "complexity", "sophistication_score", "source", "success_rate"])
            writer.writeheader()
            for p in prompts:
                writer.writerow({k: p.get(k) for k in writer.fieldnames})
        text = buf.getvalue()

    if output:
        Path(output).write_text(text, encoding="utf-8")
        console.print(f"[green]Exported {len(prompts)} prompts to {output}[/green]")
    else:
        click.echo(text)


# =============================================================================
# info - show details of a single prompt
# =============================================================================


@main.command()
@click.argument("prompt_id", type=int)
@click.pass_context
def info(ctx: click.Context, prompt_id: int) -> None:
    """Show detailed information about a specific prompt."""
    db_path = _resolve_db(ctx)
    if not db_path.exists():
        console.print(f"[red]Database not found:[/red] {db_path}")
        sys.exit(1)

    with PromptDatabase(db_path) as db:
        prompt = db.get_prompt(prompt_id)

    if not prompt:
        console.print(f"[red]Prompt #{prompt_id} not found.[/red]")
        sys.exit(1)

    console.print(f"\n[bold cyan]Prompt #{prompt['id']}[/bold cyan]")
    if prompt["title"]:
        console.print(f"  Title:         {prompt['title']}")
    console.print(f"  Technique:     {prompt['technique']}")
    console.print(f"  Complexity:    {prompt['complexity']}")
    console.print(f"  Sophistication: {prompt['sophistication_score']}")
    console.print(f"  Source:        {prompt['source']}")
    console.print(f"  Success Rate:  {prompt['success_rate']}")
    console.print(f"  Tests:         {prompt['test_count']}")
    console.print(f"  Verified:      {'Yes' if prompt['is_verified'] else 'No'}")
    console.print(f"  Curated:       {'Yes' if prompt['is_curated'] else 'No'}")

    if prompt["tags"]:
        console.print(f"  Tags:          {', '.join(prompt['tags'])}")
    if prompt["categories"]:
        cats = [f"{c['code']} ({c['name']})" for c in prompt["categories"]]
        console.print(f"  Categories:    {', '.join(cats)}")

    console.print(f"\n[bold]Content:[/bold]")
    console.print(prompt["content"])
    console.print()


if __name__ == "__main__":
    main()
