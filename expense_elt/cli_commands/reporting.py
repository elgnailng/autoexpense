from __future__ import annotations

from typing import Optional

from rich import box
from rich.table import Table

from cli_commands.common import console, header


def list_transactions_command(
    institution: Optional[str],
    file: Optional[str],
    status: Optional[str],
    limit: int,
    sort: str,
) -> None:
    from staging.database import get_connection, initialize_db

    initialize_db()
    con = get_connection()

    conditions = []
    params = []

    if institution:
        conditions.append("n.institution = ?")
        params.append(institution.upper())

    if file:
        conditions.append("n.source_file LIKE ?")
        params.append(f"%{file}%")

    if status:
        normalized_status = status.lower()
        if normalized_status == "review":
            conditions.append("c.review_required = TRUE")
        elif normalized_status == "reviewed":
            conditions.append("c.review_required = FALSE")
        elif normalized_status == "business":
            conditions.append("c.deductible_status IN ('full', 'partial')")
        elif normalized_status == "personal":
            conditions.append("c.deductible_status = 'personal'")

    where_clause = ("WHERE " + " AND ".join(conditions)) if conditions else ""

    sort_map = {
        "date": "n.transaction_date, n.merchant_normalized",
        "amount": "n.original_amount DESC",
        "merchant": "n.merchant_normalized",
    }
    order_by = sort_map.get(sort.lower(), "n.transaction_date, n.merchant_normalized")

    limit_clause = f"LIMIT {limit}" if limit > 0 else ""

    query = f"""
        SELECT
            n.transaction_date,
            n.institution,
            n.source_file,
            n.merchant_normalized,
            n.original_amount,
            n.is_credit,
            c.category,
            c.deductible_status,
            c.review_required
        FROM normalized_transactions n
        LEFT JOIN categorized_transactions c ON n.transaction_id = c.transaction_id
        {where_clause}
        ORDER BY {order_by}
        {limit_clause}
    """

    try:
        rows = con.execute(query, params).fetchall()

        count_query = f"""
            SELECT COUNT(*), ROUND(SUM(n.original_amount), 2)
            FROM normalized_transactions n
            LEFT JOIN categorized_transactions c ON n.transaction_id = c.transaction_id
            {where_clause}
        """
        count_row = con.execute(count_query, params).fetchone()
        total_count = count_row[0] if count_row else 0
        total_amount = count_row[1] if count_row and count_row[1] else 0.0
    finally:
        con.close()

    if not rows:
        console.print("[yellow]No transactions found matching the filters.[/yellow]")
        return

    title_parts = ["Transactions"]
    if institution:
        title_parts.append(institution.upper())
    if file:
        title_parts.append(f"file~{file}")
    if status:
        title_parts.append(f"status={status}")

    table = Table(
        title=" | ".join(title_parts),
        box=box.SIMPLE_HEAD,
        show_footer=True,
    )
    table.add_column("Date", style="dim", footer="")
    table.add_column("Institution", footer="")
    table.add_column("Source File", footer="")
    table.add_column("Merchant", footer=f"Total ({total_count} rows)")
    table.add_column("Amount", justify="right", footer=f"${total_amount:,.2f}")
    table.add_column("Category", footer="")
    table.add_column("Status", footer="")

    for row in rows:
        txn_date, inst, src_file, merchant, amount, is_credit, category, ded_status, review_req = row

        date_str = str(txn_date) if txn_date else "-"
        merchant_str = merchant or "-"
        amount_str = f"${amount:,.2f}" if amount is not None else "-"
        category_str = category or "[dim]-[/dim]"

        if is_credit:
            amount_str = f"[green]{amount_str} CR[/green]"

        if review_req is True:
            status_str = "[yellow]needs review[/yellow]"
        elif ded_status == "full":
            status_str = "[green]business (full)[/green]"
        elif ded_status == "partial":
            status_str = "[cyan]business (partial)[/cyan]"
        elif ded_status == "personal":
            status_str = "[dim]personal[/dim]"
        elif review_req is False:
            status_str = "[green]reviewed[/green]"
        else:
            status_str = "[dim]not categorized[/dim]"

        table.add_row(date_str, inst or "-", src_file or "-", merchant_str, amount_str, category_str, status_str)

    console.print(table)
    if limit > 0 and total_count > limit:
        console.print(f"[dim]Showing {limit} of {total_count} rows. Use --limit 0 to show all.[/dim]")


def status_command() -> None:
    header("Pipeline Status")

    from staging.database import get_connection, initialize_db

    initialize_db()
    con = get_connection()

    try:
        def count(query: str) -> int:
            result = con.execute(query).fetchone()
            return result[0] if result else 0

        raw_count = count("SELECT COUNT(*) FROM raw_transactions")
        norm_count = count("SELECT COUNT(*) FROM normalized_transactions")
        cat_count = count("SELECT COUNT(*) FROM categorized_transactions")
        review_count = count(
            "SELECT COUNT(*) FROM categorized_transactions WHERE review_required = TRUE"
        )
        reviewed_count = count(
            "SELECT COUNT(*) FROM categorized_transactions WHERE review_required = FALSE"
        )
        biz_count = count(
            "SELECT COUNT(*) FROM categorized_transactions WHERE deductible_status IN ('full', 'partial') AND review_required = FALSE"
        )
        personal_count = count(
            "SELECT COUNT(*) FROM categorized_transactions WHERE deductible_status = 'personal'"
        )
        total_deductible = con.execute(
            "SELECT ROUND(SUM(deductible_amount), 2) FROM categorized_transactions "
            "WHERE deductible_status IN ('full', 'partial') AND review_required = FALSE"
        ).fetchone()
        total_ded_val = total_deductible[0] if total_deductible and total_deductible[0] else 0.0

        inst_rows = con.execute("""
            SELECT
                r.institution,
                COUNT(DISTINCT r.raw_id)                                                  AS raw_count,
                COUNT(DISTINCT n.transaction_id)                                          AS norm_count,
                COUNT(DISTINCT c.transaction_id)                                          AS cat_count,
                COUNT(DISTINCT CASE WHEN c.review_required = TRUE  THEN c.transaction_id END) AS review_count,
                COUNT(DISTINCT CASE WHEN c.deductible_status IN ('full','partial') AND c.review_required = FALSE THEN c.transaction_id END) AS biz_count
            FROM raw_transactions r
            LEFT JOIN normalized_transactions n ON r.raw_id = n.raw_id
            LEFT JOIN categorized_transactions c ON n.transaction_id = c.transaction_id
            GROUP BY r.institution
            ORDER BY r.institution
        """).fetchall()
    finally:
        con.close()

    table = Table(title="Pipeline Status", box=box.ROUNDED)
    table.add_column("Stage", style="cyan", width=35)
    table.add_column("Count", justify="right", style="bold")

    table.add_row("Raw transactions loaded", str(raw_count))
    table.add_row("Normalized transactions", str(norm_count))
    table.add_row("Categorized transactions", str(cat_count))
    table.add_row("Pending manual review", f"[yellow]{review_count}[/yellow]")
    table.add_row("Reviewed / confirmed", f"[green]{reviewed_count}[/green]")
    table.add_row("Business expense records", str(biz_count))
    table.add_row("Personal records", str(personal_count))
    table.add_row("Total deductible amount (CAD)", f"[bold green]${total_ded_val:,.2f}[/bold green]")

    console.print(table)

    if inst_rows:
        inst_table = Table(title="By Institution", box=box.SIMPLE_HEAD)
        inst_table.add_column("Institution", style="cyan")
        inst_table.add_column("Raw", justify="right")
        inst_table.add_column("Normalized", justify="right")
        inst_table.add_column("Categorized", justify="right")
        inst_table.add_column("Needs Review", justify="right")
        inst_table.add_column("Business", justify="right")

        for institution, raw, norm, cat, rev, biz in inst_rows:
            rev_str = f"[yellow]{rev}[/yellow]" if rev else "0"
            biz_str = f"[green]{biz}[/green]" if biz else "0"
            inst_table.add_row(institution or "?", str(raw), str(norm), str(cat), rev_str, biz_str)

        console.print(inst_table)
