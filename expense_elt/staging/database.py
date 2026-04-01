"""
database.py - DuckDB connection and schema management.

DB file: expense_elt/state/transactions.duckdb
"""

from __future__ import annotations

from pathlib import Path

import duckdb

# Resolve DB path relative to this file (expense_elt/staging/ -> expense_elt/state/)
_MODULE_DIR = Path(__file__).parent
_DB_PATH = _MODULE_DIR.parent / "state" / "transactions.duckdb"


def get_connection() -> duckdb.DuckDBPyConnection:
    """Return a DuckDB connection to the project database."""
    _DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    return duckdb.connect(str(_DB_PATH))


def initialize_db() -> None:
    """Create all tables if they do not exist."""
    con = get_connection()
    try:
        con.execute("""
            CREATE TABLE IF NOT EXISTS raw_transactions (
                raw_id VARCHAR PRIMARY KEY,
                institution VARCHAR,
                source_file VARCHAR,
                page_number INTEGER,
                raw_line VARCHAR,
                transaction_date_raw VARCHAR,
                posted_date_raw VARCHAR,
                merchant_raw VARCHAR,
                description_raw VARCHAR,
                amount_raw VARCHAR,
                extra_data JSON,
                ingested_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        con.execute("""
            CREATE TABLE IF NOT EXISTS normalized_transactions (
                transaction_id VARCHAR PRIMARY KEY,
                raw_id VARCHAR,
                institution VARCHAR,
                source_file VARCHAR,
                page_number INTEGER,
                transaction_date DATE,
                posted_date DATE,
                merchant_raw VARCHAR,
                merchant_normalized VARCHAR,
                description_raw VARCHAR,
                original_amount DECIMAL(10,2),
                currency VARCHAR DEFAULT 'CAD',
                is_credit BOOLEAN,
                dedupe_hash VARCHAR,
                normalized_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        con.execute("""
            CREATE TABLE IF NOT EXISTS categorized_transactions (
                transaction_id VARCHAR PRIMARY KEY,
                category VARCHAR,
                deductible_status VARCHAR,
                original_amount DECIMAL(10,2),
                deductible_amount DECIMAL(10,2),
                confidence DECIMAL(4,2),
                review_required BOOLEAN,
                rule_applied VARCHAR,
                notes VARCHAR,
                categorized_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        con.execute("""
            CREATE TABLE IF NOT EXISTS authorized_users (
                email VARCHAR PRIMARY KEY,
                role VARCHAR NOT NULL DEFAULT 'accountant',
                permission VARCHAR NOT NULL DEFAULT 'view',
                invited_by VARCHAR NOT NULL,
                invited_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_login TIMESTAMP,
                status VARCHAR NOT NULL DEFAULT 'active'
            )
        """)

        con.commit()
    finally:
        con.close()
