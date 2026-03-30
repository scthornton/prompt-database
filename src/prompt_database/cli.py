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


# =============================================================================
# audit - data quality audit
# =============================================================================


@main.command()
@click.option("--source", "-s", help="Audit specific source only")
@click.option("--show-remove", is_flag=True, help="Show prompts flagged for removal")
@click.pass_context
def audit(ctx: click.Context, source: str | None, show_remove: bool) -> None:
    """Audit data quality and flag noise."""
    from prompt_database.quality import compute_quality_score

    db_path = _resolve_db(ctx)
    if not db_path.exists():
        console.print(f"[red]Database not found:[/red] {db_path}")
        sys.exit(1)

    with PromptDatabase(db_path) as db:
        conditions = ["is_active = 1"]
        params: list = []
        if source:
            conditions.append("source = ?")
            params.append(source)

        rows = db.conn.execute(
            f"SELECT id, content, source, technique, sophistication_score, matched_patterns "
            f"FROM prompts WHERE {' AND '.join(conditions)}",
            params,
        ).fetchall()

    keep_count = 0
    review_count = 0
    remove_count = 0
    by_source: dict[str, dict[str, int]] = {}

    for row in rows:
        patterns = []
        if row["matched_patterns"]:
            try:
                patterns = json.loads(row["matched_patterns"])
            except json.JSONDecodeError:
                pass

        assessment = compute_quality_score(
            row["content"],
            source=row["source"],
            technique=row["technique"],
            sophistication_score=row["sophistication_score"],
            matched_patterns=patterns,
        )

        rec = assessment["recommendation"]
        src = row["source"] or "unknown"

        if src not in by_source:
            by_source[src] = {"keep": 0, "review": 0, "remove": 0}
        by_source[src][rec] += 1

        if rec == "keep":
            keep_count += 1
        elif rec == "review":
            review_count += 1
        else:
            remove_count += 1

            if show_remove:
                preview = row["content"][:100].replace("\n", " ")
                console.print(f"  [red]REMOVE[/red] #{row['id']} [{src}] {preview}")

    console.print(f"\n[bold]Data Quality Audit[/bold]")
    console.print(f"  Total prompts: {len(rows):,}")
    console.print(f"  [green]Keep:    {keep_count:,}[/green]")
    console.print(f"  [yellow]Review:  {review_count:,}[/yellow]")
    console.print(f"  [red]Remove:  {remove_count:,}[/red]")

    console.print(f"\n[bold]By Source[/bold]")
    table = Table(show_header=True)
    table.add_column("Source", style="cyan")
    table.add_column("Keep", justify="right", style="green")
    table.add_column("Review", justify="right", style="yellow")
    table.add_column("Remove", justify="right", style="red")
    for src in sorted(by_source, key=lambda s: -(by_source[s]["keep"] + by_source[s]["review"] + by_source[s]["remove"])):
        counts = by_source[src]
        table.add_row(src, str(counts["keep"]), str(counts["review"]), str(counts["remove"]))
    console.print(table)


# =============================================================================
# curate - remove noise and flag quality content
# =============================================================================


@main.command()
@click.option("--dry-run", is_flag=True, help="Show what would be removed without changing DB")
@click.option("--min-quality", default=25, type=int, help="Minimum quality score to keep (0-100)")
@click.pass_context
def curate(ctx: click.Context, dry_run: bool, min_quality: int) -> None:
    """Remove noise prompts and flag high-quality content."""
    from prompt_database.quality import compute_quality_score

    db_path = _resolve_db(ctx)
    if not db_path.exists():
        console.print(f"[red]Database not found:[/red] {db_path}")
        sys.exit(1)

    with PromptDatabase(db_path) as db:
        rows = db.conn.execute(
            "SELECT id, content, source, technique, sophistication_score, matched_patterns "
            "FROM prompts WHERE is_active = 1"
        ).fetchall()

        deactivated = 0
        curated = 0

        for row in rows:
            patterns = []
            if row["matched_patterns"]:
                try:
                    patterns = json.loads(row["matched_patterns"])
                except json.JSONDecodeError:
                    pass

            assessment = compute_quality_score(
                row["content"],
                source=row["source"],
                technique=row["technique"],
                sophistication_score=row["sophistication_score"],
                matched_patterns=patterns,
            )

            if assessment["quality_score"] < min_quality:
                if not dry_run:
                    db.conn.execute(
                        "UPDATE prompts SET is_active = 0, updated_at = datetime('now') WHERE id = ?",
                        (row["id"],),
                    )
                deactivated += 1
            elif assessment["quality_score"] >= 50:
                if not dry_run:
                    db.conn.execute(
                        "UPDATE prompts SET is_curated = 1, updated_at = datetime('now') WHERE id = ?",
                        (row["id"],),
                    )
                curated += 1

        if not dry_run:
            db.conn.commit()

        action = "Would deactivate" if dry_run else "Deactivated"
        console.print(f"\n[bold]Curation Results[/bold]")
        console.print(f"  Total prompts:  {len(rows):,}")
        console.print(f"  [red]{action}: {deactivated:,} (quality < {min_quality})[/red]")
        console.print(f"  [green]Curated:      {curated:,} (quality >= 50)[/green]")
        console.print(f"  [dim]Remaining:    {len(rows) - deactivated:,}[/dim]")


if __name__ == "__main__":
    main()
