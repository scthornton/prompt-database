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
@click.option(
    "--db", default=str(DEFAULT_DB), envvar="PROMPT_DB_PATH", help="Path to SQLite database"
)
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
    console.print(
        f"\n[green]Done![/green] {total_added} prompts added, {total_skipped} duplicates skipped."
    )
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

    console.print("\n[bold]Prompt Database Statistics[/bold]")
    console.print(f"  Total prompts:      {s['total_prompts']:,}")
    console.print(f"  Verified:           {s['verified']:,}")
    console.print(f"  Curated:            {s['curated']:,}")
    console.print(f"  Test results:       {s['test_results']:,}")
    console.print(f"  Variations:         {s['variations']:,}")
    console.print(f"  Avg sophistication: {s['avg_sophistication']}")

    console.print("\n[bold]By Technique[/bold]")
    table = Table(show_header=True)
    table.add_column("Technique", style="cyan")
    table.add_column("Count", justify="right")
    for tech, count in sorted(s["by_technique"].items(), key=lambda x: -x[1]):
        table.add_row(tech, str(count))
    console.print(table)

    console.print("\n[bold]By Complexity[/bold]")
    table = Table(show_header=True)
    table.add_column("Complexity", style="yellow")
    table.add_column("Count", justify="right")
    for comp, count in sorted(s["by_complexity"].items(), key=lambda x: -x[1]):
        table.add_row(comp, str(count))
    console.print(table)

    console.print("\n[bold]By Source[/bold]")
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
        score = r["sophistication_score"]
        console.print(
            f"  [cyan]#{r['id']}[/cyan] [{r['technique']}] [{r['complexity']}] score={score}"
        )
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
            fields = [
                "id",
                "content",
                "technique",
                "complexity",
                "sophistication_score",
                "source",
                "success_rate",
            ]
            writer = csv.DictWriter(buf, fieldnames=fields)
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
# export-garak - export for Garak security scanner
# =============================================================================


@main.command("export-garak")
@click.option("--output", "-o", required=True, help="Output JSONL file")
@click.option("--technique", "-t", help="Filter by technique")
@click.option("--min-score", type=int, help="Minimum sophistication score")
@click.option("--limit", "-n", type=int, help="Max prompts")
@click.pass_context
def export_garak_cmd(
    ctx: click.Context,
    output: str,
    technique: str | None,
    min_score: int | None,
    limit: int | None,
) -> None:
    """Export prompts in Garak probe format (JSONL)."""
    from prompt_database.exporters import export_garak

    db_path = _resolve_db(ctx)
    if not db_path.exists():
        console.print(f"[red]Database not found:[/red] {db_path}")
        sys.exit(1)

    with PromptDatabase(db_path) as db:
        count = export_garak(
            db,
            Path(output),
            technique=technique,
            min_sophistication=min_score,
            limit=limit,
        )

    console.print(f"[green]Exported {count} prompts to {output} (Garak format)[/green]")


# =============================================================================
# export-ps-fuzz - export for ps-fuzz security fuzzer
# =============================================================================


@main.command("export-ps-fuzz")
@click.option("--output", "-o", required=True, help="Output YAML file")
@click.option("--technique", "-t", help="Filter by technique")
@click.option("--min-score", type=int, help="Minimum sophistication score")
@click.option("--limit", "-n", type=int, help="Max prompts")
@click.pass_context
def export_ps_fuzz_cmd(
    ctx: click.Context,
    output: str,
    technique: str | None,
    min_score: int | None,
    limit: int | None,
) -> None:
    """Export prompts in ps-fuzz YAML format."""
    from prompt_database.exporters import export_ps_fuzz

    db_path = _resolve_db(ctx)
    if not db_path.exists():
        console.print(f"[red]Database not found:[/red] {db_path}")
        sys.exit(1)

    with PromptDatabase(db_path) as db:
        count = export_ps_fuzz(
            db,
            Path(output),
            technique=technique,
            min_sophistication=min_score,
            limit=limit,
        )

    console.print(f"[green]Exported {count} prompts to {output} (ps-fuzz format)[/green]")


# =============================================================================
# export-dataset - export as HuggingFace-compatible dataset
# =============================================================================


@main.command("export-dataset")
@click.option("--output", "-o", required=True, help="Output JSONL file")
@click.option("--technique", "-t", help="Filter by technique")
@click.option("--min-score", type=int, help="Minimum sophistication score")
@click.option("--limit", "-n", type=int, help="Max prompts")
@click.pass_context
def export_dataset_cmd(
    ctx: click.Context,
    output: str,
    technique: str | None,
    min_score: int | None,
    limit: int | None,
) -> None:
    """Export as HuggingFace-compatible dataset (JSONL)."""
    from prompt_database.exporters import export_dataset

    db_path = _resolve_db(ctx)
    if not db_path.exists():
        console.print(f"[red]Database not found:[/red] {db_path}")
        sys.exit(1)

    with PromptDatabase(db_path) as db:
        count = export_dataset(
            db,
            Path(output),
            technique=technique,
            min_sophistication=min_score,
            limit=limit,
        )

    console.print(
        f"[green]Exported {count} prompts to {output} (HuggingFace dataset format)[/green]"
    )


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

    console.print("\n[bold]Content:[/bold]")
    console.print(prompt["content"])
    console.print()


# =============================================================================
# test-prompt - run prompts against model APIs
# =============================================================================


@main.command("test-prompt")
@click.option("--model", "-m", required=True, help="Target model (e.g., gpt-4, claude-sonnet-4-5)")
@click.option("--api-base", default="https://api.openai.com/v1", help="API base URL")
@click.option("--api-key", envvar="OPENAI_API_KEY", help="API key (or set OPENAI_API_KEY)")
@click.option(
    "--system-prompt", default="You are a helpful assistant.", help="System prompt for target"
)
@click.option("--technique", "-t", help="Filter prompts by technique")
@click.option("--min-score", type=int, help="Minimum sophistication score")
@click.option("--limit", "-n", default=10, type=int, help="Number of prompts to test")
@click.option("--prompt-id", type=int, help="Test a specific prompt by ID")
@click.option("--dry-run", is_flag=True, help="Show what would be tested without calling API")
@click.pass_context
def test_prompt_cmd(
    ctx: click.Context,
    model: str,
    api_base: str,
    api_key: str | None,
    system_prompt: str,
    technique: str | None,
    min_score: int | None,
    limit: int,
    prompt_id: int | None,
    dry_run: bool,
) -> None:
    """Test prompts against a model API and record results."""
    from prompt_database.tester import TestConfig, test_prompt

    db_path = _resolve_db(ctx)
    if not db_path.exists():
        console.print(f"[red]Database not found:[/red] {db_path}")
        sys.exit(1)

    if not api_key and not dry_run:
        console.print("[red]API key required. Set OPENAI_API_KEY or use --api-key[/red]")
        sys.exit(1)

    config = TestConfig(
        target_model=model,
        api_base=api_base,
        api_key=api_key or "",
        system_prompt=system_prompt,
    )

    with PromptDatabase(db_path) as db:
        if prompt_id:
            prompt = db.get_prompt(prompt_id)
            if not prompt:
                console.print(f"[red]Prompt #{prompt_id} not found.[/red]")
                sys.exit(1)
            prompts_to_test = [prompt]
        else:
            prompts_to_test = db.filter_prompts(
                technique=technique,
                min_sophistication=min_score,
                limit=limit,
            )

        if not prompts_to_test:
            console.print("[yellow]No prompts matched filters.[/yellow]")
            return

        console.print(f"\n[bold]Testing {len(prompts_to_test)} prompts against {model}[/bold]\n")

        if dry_run:
            for p in prompts_to_test:
                preview = p["content"][:80].replace("\n", " ")
                console.print(f"  #{p['id']} [{p['technique']}] {preview}...")
            console.print("\n[dim]Dry run — no API calls made.[/dim]")
            return

        results_summary = {"SUCCESS": 0, "FAIL": 0, "PARTIAL": 0, "ERROR": 0}

        for i, p in enumerate(prompts_to_test, 1):
            console.print(f"  [{i}/{len(prompts_to_test)}] Testing #{p['id']}... ", end="")

            result = test_prompt(config, p["id"], p["content"])

            # Record to database
            db.add_test_result(
                p["id"],
                target_model=model,
                actual_prompt=p["content"],
                result=result.result,
                response=result.response,
                confidence_score=result.confidence_score,
                model_provider=config.model_provider,
                tool_used="prompt-db",
                response_time_ms=result.response_time_ms,
                prompt_tokens=result.prompt_tokens,
                completion_tokens=result.completion_tokens,
                detected_refusal=result.detected_refusal,
                guardrail_bypassed=result.guardrail_bypassed,
            )

            results_summary[result.result] += 1

            color = {
                "SUCCESS": "red",
                "FAIL": "green",
                "PARTIAL": "yellow",
                "ERROR": "dim",
            }.get(result.result, "white")
            console.print(
                f"[{color}]{result.result}[/{color}] "
                f"(conf={result.confidence_score:.2f}, {result.response_time_ms:.0f}ms)"
            )

        console.print("\n[bold]Results Summary[/bold]")
        console.print(f"  [red]SUCCESS (attack worked):[/red]  {results_summary['SUCCESS']}")
        console.print(f"  [green]FAIL (model defended):[/green]   {results_summary['FAIL']}")
        console.print(f"  [yellow]PARTIAL (ambiguous):[/yellow]     {results_summary['PARTIAL']}")
        console.print(f"  [dim]ERROR (API error):[/dim]        {results_summary['ERROR']}")


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

    console.print("\n[bold]Data Quality Audit[/bold]")
    console.print(f"  Total prompts: {len(rows):,}")
    console.print(f"  [green]Keep:    {keep_count:,}[/green]")
    console.print(f"  [yellow]Review:  {review_count:,}[/yellow]")
    console.print(f"  [red]Remove:  {remove_count:,}[/red]")

    console.print("\n[bold]By Source[/bold]")
    table = Table(show_header=True)
    table.add_column("Source", style="cyan")
    table.add_column("Keep", justify="right", style="green")
    table.add_column("Review", justify="right", style="yellow")
    table.add_column("Remove", justify="right", style="red")

    def _total(s: str) -> int:
        return -(by_source[s]["keep"] + by_source[s]["review"] + by_source[s]["remove"])

    for src in sorted(by_source, key=_total):
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
                        "UPDATE prompts SET is_active = 0, updated_at = datetime('now') "
                        "WHERE id = ?",
                        (row["id"],),
                    )
                deactivated += 1
            elif assessment["quality_score"] >= 50:
                if not dry_run:
                    db.conn.execute(
                        "UPDATE prompts SET is_curated = 1, updated_at = datetime('now') "
                        "WHERE id = ?",
                        (row["id"],),
                    )
                curated += 1

        if not dry_run:
            db.conn.commit()

        action = "Would deactivate" if dry_run else "Deactivated"
        console.print("\n[bold]Curation Results[/bold]")
        console.print(f"  Total prompts:  {len(rows):,}")
        console.print(f"  [red]{action}: {deactivated:,} (quality < {min_quality})[/red]")
        console.print(f"  [green]Curated:      {curated:,} (quality >= 50)[/green]")
        console.print(f"  [dim]Remaining:    {len(rows) - deactivated:,}[/dim]")


if __name__ == "__main__":
    main()
