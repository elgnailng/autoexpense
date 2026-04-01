from __future__ import annotations

import typer
from rich import box
from rich.table import Table

from cli_commands.common import console, error, header, success


def _resolve_llm_provider(use_llm: bool, llm_provider: str) -> str:
    if use_llm and not llm_provider:
        from llm.config import load_llm_config

        return load_llm_config().provider
    return llm_provider


def extract_command(verbose: bool, parser: str) -> None:
    header("Extract: Parsing PDFs -> raw_transactions")

    from staging.database import initialize_db
    from staging.load_transactions import load_all_pdfs

    initialize_db()
    try:
        stats = load_all_pdfs(verbose=verbose, parser=parser)
    except ImportError as exc:
        error(str(exc))
        raise typer.Exit(1)

    parser_used = stats.get("parser_used", parser)
    console.print(f"[dim]Parser: {parser_used}[/dim]")

    table = Table(box=box.SIMPLE)
    table.add_column("Metric", style="cyan")
    table.add_column("Value", justify="right")
    table.add_row("RBC files processed", str(stats["rbc_files"]))
    table.add_row("BMO files processed", str(stats["bmo_files"]))
    table.add_row("Amex files processed", str(stats.get("amex_files", 0)))
    table.add_row("Transactions parsed", str(stats["total_parsed"]))
    table.add_row("New rows inserted", str(stats["total_inserted"]))
    table.add_row("Rows skipped (partial match)", str(stats.get("skipped_partial", 0)))
    table.add_row("Errors", str(stats["errors"]))
    console.print(table)

    if stats.get("skipped_partial", 0) > 0:
        console.print(
            f"[yellow]{stats['skipped_partial']} row(s) had a date but no parseable amount - "
            "check logs/parse_skipped.log[/yellow]"
        )
    if stats["errors"] > 0:
        error(f"{stats['errors']} error(s) - check logs/parse_errors.log")
    else:
        success("Extract complete.")


def transform_command(verbose: bool) -> None:
    header("Transform: Normalize + Deduplicate")

    from transform.normalize import normalize_transactions
    from transform.dedupe import find_and_log_duplicates

    norm_stats = normalize_transactions(verbose=verbose)

    table = Table(box=box.SIMPLE)
    table.add_column("Metric", style="cyan")
    table.add_column("Value", justify="right")
    table.add_row("Raw transactions", str(norm_stats["total_raw"]))
    table.add_row("Newly normalized", str(norm_stats["normalized"]))
    table.add_row("Already normalized (skipped)", str(norm_stats["skipped"]))
    table.add_row("Errors", str(norm_stats["errors"]))
    console.print(table)

    console.print("\n[dim]Checking for duplicates...[/dim]")
    dupe_stats = find_and_log_duplicates(verbose=verbose)
    table2 = Table(box=box.SIMPLE)
    table2.add_column("Metric", style="cyan")
    table2.add_column("Value", justify="right")
    table2.add_row("Total normalized", str(dupe_stats["total_checked"]))
    table2.add_row("Duplicate groups", str(dupe_stats["duplicate_groups"]))
    table2.add_row("Duplicate records", str(dupe_stats["duplicate_records"]))
    console.print(table2)

    if dupe_stats["duplicate_records"] > 0:
        console.print("[yellow]Duplicates logged to logs/duplicates.log[/yellow]")

    success("Transform complete.")


def categorize_command(
    verbose: bool,
    use_llm: bool,
    llm_provider: str,
    dry_run: bool,
    force: bool,
) -> None:
    llm_provider = _resolve_llm_provider(use_llm, llm_provider)

    if use_llm:
        header(f"Categorize: LLM Evaluator ({llm_provider})")
    else:
        header("Categorize: Rules engine + Merchant memory")

    from categorization.categorizer import categorize_all

    stats = categorize_all(
        verbose=verbose,
        use_llm=use_llm,
        llm_provider=llm_provider or "anthropic",
        dry_run=dry_run,
        force=force,
    )

    table = Table(box=box.SIMPLE)
    table.add_column("Metric", style="cyan")
    table.add_column("Value", justify="right")
    table.add_row("Normalized transactions", str(stats["total_normalized"]))

    if force:
        cleared = stats.get("cleared", 0)
        console.print(f"  [yellow]Recategorize: cleared {cleared} non-memory categorizations[/yellow]")

    if dry_run and use_llm:
        table.add_row("Already categorized (skipped)", str(stats["skipped"]))
        table.add_row("Merchant memory matches", str(stats.get("memory_matched", 0)))
        table.add_row("LLM candidates", str(stats.get("llm_candidates", 0)))
        table.add_row("Estimated batches", str(stats.get("estimated_batches", 0)))
        table.add_row("Model", stats.get("model", "?"))
        console.print(table)
        console.print("[yellow]Dry run - no LLM API calls were made.[/yellow]")
        return

    table.add_row("Newly categorized", str(stats["categorized"]))
    table.add_row("Already categorized (skipped)", str(stats["skipped"]))
    table.add_row("Requiring manual review", str(stats["review_required"]))
    table.add_row("Errors", str(stats["errors"]))

    if use_llm:
        table.add_row("Merchant memory matches", str(stats.get("memory_matched", 0)))
        table.add_row("LLM evaluated", str(stats.get("llm_evaluated", 0)))
        table.add_row("Model", stats.get("model", "?"))
        table.add_row("Total cost (USD)", f"${stats.get('total_cost_usd', 0):.4f}")
        table.add_row("Input tokens", str(stats.get("total_input_tokens", 0)))
        table.add_row("Output tokens", str(stats.get("total_output_tokens", 0)))

    console.print(table)

    if stats["review_required"] > 0:
        console.print(
            f"[yellow]{stats['review_required']} transaction(s) need review. "
            "Run: python main.py review[/yellow]"
        )

    success("Categorize complete.")


def review_command(limit: int) -> None:
    header("Manual Review")

    from categorization.manual_review import run_manual_review

    stats = run_manual_review(limit=limit if limit > 0 else None)

    table = Table(box=box.SIMPLE)
    table.add_column("Metric", style="cyan")
    table.add_column("Value", justify="right")
    table.add_row("Shown", str(stats["shown"]))
    table.add_row("Reviewed", str(stats["reviewed"]))
    table.add_row("Skipped", str(stats["skipped"]))
    console.print(table)

    success("Review complete.")


def export_command(verbose: bool) -> None:
    header("Export: Generate CSV reports")

    from output.csv_export import export_all

    stats = export_all(verbose=verbose)

    table = Table(box=box.SIMPLE)
    table.add_column("File", style="cyan")
    table.add_column("Rows", justify="right")
    for filename, count in stats.items():
        table.add_row(f"{filename}.csv", str(count))
    console.print(table)

    success("Export complete. Files written to expense_elt/output/")


def run_command(
    verbose: bool,
    parser: str,
    use_llm: bool,
    llm_provider: str,
    force: bool,
) -> None:
    llm_provider = _resolve_llm_provider(use_llm, llm_provider)

    header("Running Full Pipeline")

    console.print("\n[bold]Step 1: Extract[/bold]")
    from staging.database import initialize_db
    from staging.load_transactions import load_all_pdfs

    initialize_db()
    try:
        stats = load_all_pdfs(verbose=verbose, parser=parser)
    except ImportError as exc:
        error(str(exc))
        raise typer.Exit(1)
    console.print(f"  [dim]Parser: {stats.get('parser_used', parser)}[/dim]")
    console.print(
        f"  Parsed {stats['total_parsed']} transactions, inserted {stats['total_inserted']} new."
    )

    console.print("\n[bold]Step 2: Transform[/bold]")
    from transform.normalize import normalize_transactions
    from transform.dedupe import find_and_log_duplicates

    norm_stats = normalize_transactions(verbose=verbose)
    dupe_stats = find_and_log_duplicates(verbose=verbose)
    console.print(
        f"  Normalized {norm_stats['normalized']} records. "
        f"Found {dupe_stats['duplicate_records']} duplicates."
    )

    console.print("\n[bold]Step 3: Categorize[/bold]")
    if use_llm:
        console.print(f"  [dim]Using LLM evaluator ({llm_provider})[/dim]")
    from categorization.categorizer import categorize_all

    cat_stats = categorize_all(
        verbose=verbose,
        use_llm=use_llm,
        llm_provider=llm_provider or "anthropic",
        force=force,
    )
    console.print(
        f"  Categorized {cat_stats['categorized']} records. "
        f"{cat_stats['review_required']} need review."
    )
    if use_llm:
        console.print(f"  [dim]LLM cost: ${cat_stats.get('total_cost_usd', 0):.4f}[/dim]")

    console.print("\n[bold]Step 4: Export[/bold]")
    from output.csv_export import export_all

    exp_stats = export_all(verbose=verbose)
    total_rows = sum(exp_stats.values())
    console.print(f"  Exported {total_rows} total rows across {len(exp_stats)} files.")

    console.print("")
    success("Pipeline complete.")

    if cat_stats["review_required"] > 0:
        console.print(
            f"\n[yellow]{cat_stats['review_required']} transaction(s) still need manual review.[/yellow]"
            "\nRun: [bold]python main.py review[/bold]"
        )


def serve_command(host: str, port: int, reload: bool) -> None:
    header("Starting Web Server")

    from staging.database import initialize_db

    initialize_db()

    import uvicorn

    console.print(f"Server starting at [bold]http://{host}:{port}[/bold]")
    console.print(f"Access from phone: [bold]http://<your-ip>:{port}[/bold]")
    uvicorn.run("api.server:app", host=host, port=port, reload=reload)
