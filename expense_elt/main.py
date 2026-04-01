"""
main.py - Typer CLI for the Tax Expense ELT pipeline.

Commands:
  extract     Step 1+2: Parse PDFs -> load raw_transactions
  transform   Step 3: Normalize + dedupe
  categorize  Step 4: Apply rules + merchant memory
  review      Step 5: Interactive CLI review
  export      Step 6: Generate CSVs
  run         Run all steps in sequence
  status      Show pipeline counts
"""

from __future__ import annotations

import io
import os
import sys
from pathlib import Path
from typing import Optional

if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

_HERE = Path(__file__).parent.resolve()
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

_env_file = _HERE / ".env"
if _env_file.exists():
    try:
        from dotenv import load_dotenv

        load_dotenv(_env_file)
    except ImportError:
        with open(_env_file) as handle:
            for line in handle:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, _, value = line.partition("=")
                    os.environ.setdefault(key.strip(), value.strip())

import typer

from cli_commands.maintenance import reset_command, restore_command
from cli_commands.pipeline import (
    categorize_command,
    export_command,
    extract_command,
    review_command,
    run_command,
    serve_command,
    transform_command,
)
from cli_commands.reporting import list_transactions_command, status_command
from log_config import setup_logging

setup_logging()

app = typer.Typer(
    help="Tax Expense ELT pipeline - parse, normalize, categorize, and export transactions.",
    add_completion=False,
)


@app.command()
def extract(
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Show per-file detail"),
    parser: str = typer.Option(
        "monopoly",
        "--parser",
        "-p",
        help="Parser mode: monopoly (default) / custom / auto (custom with monopoly fallback)",
    ),
) -> None:
    """
    Step 1+2: Parse PDFs and load raw transactions into the database.

    Parser modes:
      monopoly - use monopoly-core package (default)
      custom   - built-in regex parsers (no extra dependencies)
      auto     - try custom; fall back to monopoly if 0 transactions found
    """
    extract_command(verbose=verbose, parser=parser)


@app.command()
def transform(
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Show per-record detail"),
) -> None:
    """Step 3: Normalize raw transactions and detect duplicates."""
    transform_command(verbose=verbose)


@app.command()
def categorize(
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Show per-record detail"),
    use_llm: bool = typer.Option(False, "--use-llm", help="Use LLM evaluator instead of keyword rules"),
    llm_provider: str = typer.Option("", "--llm-provider", help="LLM provider: anthropic or openai (default: from llm_config.yaml)"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Estimate LLM cost without calling API (requires --use-llm)"),
    force: bool = typer.Option(False, "--force", "-f", help="Recategorize: clear non-memory categorizations and re-evaluate"),
) -> None:
    """
    Step 4: Apply categorization rules and merchant memory.

    With --use-llm, uses an LLM to categorize transactions not matched by
    merchant memory. Use --dry-run to estimate cost before running.
    """
    categorize_command(
        verbose=verbose,
        use_llm=use_llm,
        llm_provider=llm_provider,
        dry_run=dry_run,
        force=force,
    )


@app.command()
def review(
    limit: int = typer.Option(0, "--limit", "-n", help="Max transactions to review (0 = all)"),
) -> None:
    """Step 5: Interactive CLI review of transactions requiring manual categorization."""
    review_command(limit=limit)


@app.command()
def export(
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Show file details"),
) -> None:
    """Step 6: Export CSVs to output/ directory."""
    export_command(verbose=verbose)


@app.command()
def run(
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Verbose output"),
    parser: str = typer.Option(
        "monopoly",
        "--parser",
        "-p",
        help="Parser mode: monopoly (default) / custom / auto",
    ),
    use_llm: bool = typer.Option(False, "--use-llm", help="Use LLM evaluator instead of keyword rules"),
    llm_provider: str = typer.Option("", "--llm-provider", help="LLM provider: anthropic or openai (default: from llm_config.yaml)"),
    force: bool = typer.Option(False, "--force", "-f", help="Recategorize: clear non-memory categorizations and re-evaluate"),
) -> None:
    """
    Run all pipeline steps in sequence: extract -> transform -> categorize -> export.
    (Review is interactive and must be run separately.)
    """
    run_command(
        verbose=verbose,
        parser=parser,
        use_llm=use_llm,
        llm_provider=llm_provider,
        force=force,
    )


@app.command(name="list")
def list_transactions(
    institution: Optional[str] = typer.Option(None, "--institution", "-i", help="Filter: RBC_VISA or BMO"),
    file: Optional[str] = typer.Option(None, "--file", "-f", help="Filter by source PDF filename (partial match)"),
    status: Optional[str] = typer.Option(None, "--status", "-s", help="Filter: review / reviewed / business / personal (default: all)"),
    limit: int = typer.Option(50, "--limit", "-n", help="Max rows to show (0 = all)"),
    sort: str = typer.Option("date", "--sort", help="Sort by: date / amount / merchant"),
) -> None:
    """List transactions in a table. Filter by institution, file, or review status."""
    list_transactions_command(
        institution=institution,
        file=file,
        status=status,
        limit=limit,
        sort=sort,
    )


@app.command()
def status() -> None:
    """Show pipeline status: counts at each stage."""
    status_command()


@app.command()
def serve(
    host: str = typer.Option("0.0.0.0", "--host", "-h", help="Bind address"),
    port: int = typer.Option(9743, "--port", "-p", help="Port number"),
    reload: bool = typer.Option(False, "--reload", help="Auto-reload on code changes"),
) -> None:
    """Start the web UI server (FastAPI + React frontend)."""
    serve_command(host=host, port=port, reload=reload)


@app.command()
def reset(
    level: str = typer.Option(
        "soft",
        "--level",
        "-l",
        help="Reset level: soft (DB + outputs), medium (+ merchant memory + config history), hard (+ rules + deduction rules)",
    ),
    yes: bool = typer.Option(False, "--yes", "-y", help="Skip confirmation prompt"),
) -> None:
    """
    Wipe data and start fresh. Three levels:

      soft   - DB, output CSVs, logs (keeps all config and merchant memory)
      medium - soft + merchant memory + config history
      hard   - medium + rules.yaml + deduction_rules.yaml (full factory reset)

    Config files are always backed up to config/backups/ before deletion.
    """
    reset_command(level=level, yes=yes)


@app.command()
def restore(
    backup_id: str = typer.Argument(
        None,
        help="Timestamp of the backup set to restore (e.g. 20260311_143045). Omit to list available backups.",
    ),
    yes: bool = typer.Option(False, "--yes", "-y", help="Skip confirmation prompt"),
) -> None:
    """
    List or restore from a config backup.

    Run without arguments to see available backups grouped by timestamp.
    Pass a timestamp to restore those files to their original locations.
    """
    restore_command(backup_id=backup_id, yes=yes)


if __name__ == "__main__":
    app()
