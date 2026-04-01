"""
dedupe.py - Detect and handle duplicate transactions in normalized_transactions.

Strategy: keep the first occurrence (by normalized_at timestamp) for each
dedupe_hash. Log all duplicates found.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Dict

from staging.database import get_connection

_LOG_FILE = Path(__file__).parent.parent / "logs" / "duplicates.log"
_LOG_FILE.parent.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    filename=str(_LOG_FILE),
    level=logging.INFO,
    format="%(asctime)s %(message)s",
)
_logger = logging.getLogger("dedupe")


def find_and_log_duplicates(verbose: bool = False) -> Dict[str, int]:
    """
    Identify duplicate records sharing the same dedupe_hash.

    The first-inserted record (lowest rowid / earliest normalized_at) is
    considered the canonical record.  Duplicates are logged to
    logs/duplicates.log.

    Returns stats dict: total_checked, duplicate_groups, duplicate_records.
    """
    con = get_connection()
    stats = {
        "total_checked": 0,
        "duplicate_groups": 0,
        "duplicate_records": 0,
    }

    try:
        # Count total records
        result = con.execute("SELECT COUNT(*) FROM normalized_transactions").fetchone()
        stats["total_checked"] = result[0] if result else 0

        # Find hashes that appear more than once
        dupes = con.execute(
            """
            SELECT dedupe_hash, COUNT(*) AS cnt
            FROM normalized_transactions
            WHERE dedupe_hash IS NOT NULL
            GROUP BY dedupe_hash
            HAVING COUNT(*) > 1
            ORDER BY cnt DESC
            """
        ).fetchall()

        stats["duplicate_groups"] = len(dupes)

        for dedupe_hash, cnt in dupes:
            stats["duplicate_records"] += cnt - 1  # keep 1, the rest are dupes

            # Fetch all occurrences ordered by normalized_at (keep first)
            records = con.execute(
                """
                SELECT transaction_id, institution, source_file, page_number,
                       merchant_normalized, original_amount, transaction_date
                FROM normalized_transactions
                WHERE dedupe_hash = ?
                ORDER BY normalized_at ASC
                """,
                [dedupe_hash],
            ).fetchall()

            canonical = records[0]
            duplicates = records[1:]

            _logger.info(
                "Duplicate group hash=%s count=%d canonical=%s",
                dedupe_hash, cnt, canonical[0],
            )
            for dup in duplicates:
                _logger.info(
                    "  DUPLICATE transaction_id=%s institution=%s source=%s merchant=%s amount=%s date=%s",
                    dup[0], dup[1], dup[2], dup[4], dup[5], dup[6],
                )
                if verbose:
                    print(
                        f"  [DUPE] {dup[4]} | {dup[5]} | {dup[6]} "
                        f"(source: {dup[2]}) — duplicate of {canonical[0]}"
                    )

        if verbose and stats["duplicate_groups"] == 0:
            print("  No duplicates found.")

    finally:
        con.close()

    return stats
