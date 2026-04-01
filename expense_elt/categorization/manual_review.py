"""
manual_review.py - Interactive CLI for reviewing transactions that need manual categorization.

Shows transactions where review_required = True and allows the user to:
  1. Confirm or change category
  2. Set deductible status (full/partial/personal/skip)
  3. Enter deductible amount if partial
  4. Add optional notes

Decisions are saved to merchant_memory and categorized_transactions.
"""

from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Optional

import yaml
from rich.console import Console
from rich.prompt import Prompt, Confirm
from rich.table import Table
from rich import box

from categorization.merchant_memory import get_memory
from staging.database import get_connection

_CONFIG_DIR = Path(__file__).parent.parent / "config"
_CATEGORIES_FILE = _CONFIG_DIR / "categories.yaml"

console = Console()


def _load_categories() -> List[str]:
    """Load categories list from YAML."""
    with open(_CATEGORIES_FILE, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return data.get("categories", [])


def _display_transaction(txn: Dict, categories: List[str]) -> None:
    """Display a single transaction for review using rich."""
    console.rule(style="blue")
    table = Table(show_header=False, box=box.SIMPLE, padding=(0, 1))
    table.add_column("Field", style="bold cyan", width=14)
    table.add_column("Value")

    table.add_row("Date", str(txn.get("transaction_date", "")))
    table.add_row("Institution", txn.get("institution", ""))
    table.add_row("Merchant", txn.get("merchant_raw", ""))
    table.add_row("Description", txn.get("description_raw", ""))
    table.add_row("Amount", f"${txn.get('original_amount', 0):.2f}")
    table.add_row(
        "Suggested",
        f"{txn.get('category', '')} (confidence: {txn.get('confidence', 0):.2f})",
    )
    if txn.get("rule_applied"):
        table.add_row("Rule", txn.get("rule_applied", ""))

    console.print(table)

    # Show numbered category list
    console.print("\n[bold]Categories:[/bold]")
    for i, cat in enumerate(categories, start=1):
        console.print(f"  [dim]{i:2d}.[/dim] {cat}")


def _prompt_category(categories: List[str], suggested: str) -> str:
    """Prompt user to select a category."""
    suggested_idx = None
    for i, cat in enumerate(categories, start=1):
        if cat == suggested:
            suggested_idx = i
            break

    default_str = str(suggested_idx) if suggested_idx else "1"
    while True:
        raw = Prompt.ask(
            f"\nCategory number [dim](default {default_str} = {suggested})[/dim]",
            default=default_str,
        )
        try:
            idx = int(raw)
            if 1 <= idx <= len(categories):
                return categories[idx - 1]
        except ValueError:
            pass
        console.print(f"[red]Please enter a number between 1 and {len(categories)}.[/red]")


def _prompt_deductible_status() -> str:
    """Prompt for deductible status."""
    while True:
        raw = Prompt.ask(
            "Deductible: ([bold]f[/bold])ull / ([bold]p[/bold])artial / "
            "([bold]x[/bold]) personal / ([bold]s[/bold])kip",
            default="f",
        ).strip().lower()
        if raw in ("f", "full"):
            return "full"
        if raw in ("p", "partial"):
            return "partial"
        if raw in ("x", "personal"):
            return "personal"
        if raw in ("s", "skip"):
            return "skip"
        console.print("[red]Enter f, p, x, or s.[/red]")


def run_manual_review(limit: Optional[int] = None) -> Dict[str, int]:
    """
    Run the interactive manual review loop.

    Returns stats dict with keys: shown, reviewed, skipped.
    """
    categories = _load_categories()
    memory = get_memory()
    con = get_connection()

    stats = {"shown": 0, "reviewed": 0, "skipped": 0}

    try:
        # Fetch transactions requiring review, joined with normalized data
        query = """
            SELECT
                ct.transaction_id,
                ct.category,
                ct.confidence,
                ct.rule_applied,
                ct.deductible_status,
                ct.original_amount,
                ct.notes,
                nt.transaction_date,
                nt.merchant_raw,
                nt.merchant_normalized,
                nt.description_raw,
                nt.institution
            FROM categorized_transactions ct
            JOIN normalized_transactions nt
                ON ct.transaction_id = nt.transaction_id
            WHERE ct.review_required = TRUE
            ORDER BY nt.transaction_date ASC
        """
        if limit:
            query += f" LIMIT {limit}"

        rows = con.execute(query).fetchall()

        if not rows:
            console.print("[green]No transactions require review.[/green]")
            return stats

        console.print(f"\n[bold yellow]{len(rows)} transactions require review.[/bold yellow]\n")

        for row in rows:
            (
                transaction_id, category, confidence, rule_applied,
                deductible_status, original_amount, notes,
                transaction_date, merchant_raw, merchant_normalized,
                description_raw, institution,
            ) = row

            txn = {
                "transaction_id": transaction_id,
                "transaction_date": transaction_date,
                "institution": institution,
                "merchant_raw": merchant_raw,
                "merchant_normalized": merchant_normalized,
                "description_raw": description_raw,
                "original_amount": float(original_amount) if original_amount else 0.0,
                "category": category,
                "confidence": float(confidence) if confidence else 0.0,
                "rule_applied": rule_applied,
                "deductible_status": deductible_status,
            }

            stats["shown"] += 1
            _display_transaction(txn, categories)

            # --- Get category ---
            chosen_category = _prompt_category(categories, txn["category"])

            # --- Get deductible status ---
            chosen_status = _prompt_deductible_status()

            if chosen_status == "skip":
                console.print("[dim]Skipped.[/dim]\n")
                stats["skipped"] += 1
                continue

            # --- Get deductible amount if partial ---
            deductible_amount = txn["original_amount"]
            if chosen_status == "partial":
                while True:
                    raw = Prompt.ask(
                        f"Deductible amount (max ${txn['original_amount']:.2f})",
                        default=str(round(txn["original_amount"], 2)),
                    )
                    try:
                        deductible_amount = float(raw)
                        break
                    except ValueError:
                        console.print("[red]Enter a valid number.[/red]")
            elif chosen_status == "personal":
                deductible_amount = 0.0

            # --- Optional notes ---
            note_text = Prompt.ask("Notes (optional)", default="")

            # --- Save to DB ---
            con.execute(
                """
                UPDATE categorized_transactions
                SET category = ?,
                    deductible_status = ?,
                    deductible_amount = ?,
                    confidence = 1.0,
                    review_required = FALSE,
                    notes = ?
                WHERE transaction_id = ?
                """,
                [chosen_category, chosen_status, deductible_amount, note_text, transaction_id],
            )
            con.commit()

            # --- Save to merchant memory ---
            memory.save_decision(
                merchant_normalized=merchant_normalized or merchant_raw or "",
                category=chosen_category,
                deductible_status=chosen_status,
                confidence=1.0,
                decision_source="manual",
            )

            console.print(
                f"[green]Saved:[/green] {chosen_category} | {chosen_status} "
                f"| ${deductible_amount:.2f}\n"
            )
            stats["reviewed"] += 1

    finally:
        con.close()

    return stats
