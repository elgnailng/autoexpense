"""Tests for transform/dedupe.py — duplicate detection and logging."""

import duckdb
import pytest
from unittest.mock import patch

from transform.dedupe import find_and_log_duplicates


@pytest.fixture
def db_with_dupes(tmp_path):
    """Create an in-memory DuckDB with normalized_transactions including duplicates."""
    db_path = tmp_path / "test.duckdb"
    con = duckdb.connect(str(db_path))
    con.execute("""
        CREATE TABLE normalized_transactions (
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

    # Insert 3 records: 2 with same dedupe_hash (duplicates), 1 unique
    con.execute("""
        INSERT INTO normalized_transactions
            (transaction_id, raw_id, institution, source_file, page_number,
             merchant_normalized, original_amount, dedupe_hash, transaction_date)
        VALUES
            ('txn-1', 'raw-1', 'RBC_VISA', 'stmt1.pdf', 1, 'AMAZON', 50.00, 'hash_dup', '2025-01-15'),
            ('txn-2', 'raw-2', 'RBC_VISA', 'stmt2.pdf', 2, 'AMAZON', 50.00, 'hash_dup', '2025-01-15'),
            ('txn-3', 'raw-3', 'BMO_MASTERCARD', 'stmt3.pdf', 1, 'NETFLIX', 19.99, 'hash_unique', '2025-02-01')
    """)
    con.commit()
    con.close()
    return db_path


@pytest.fixture
def db_no_dupes(tmp_path):
    """DuckDB with all unique dedupe_hashes."""
    db_path = tmp_path / "test_nodup.duckdb"
    con = duckdb.connect(str(db_path))
    con.execute("""
        CREATE TABLE normalized_transactions (
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
        INSERT INTO normalized_transactions
            (transaction_id, raw_id, institution, source_file, page_number,
             merchant_normalized, original_amount, dedupe_hash, transaction_date)
        VALUES
            ('txn-a', 'raw-a', 'RBC_VISA', 's1.pdf', 1, 'AMAZON', 50.00, 'h1', '2025-01-01'),
            ('txn-b', 'raw-b', 'BMO_MASTERCARD', 's2.pdf', 1, 'NETFLIX', 19.99, 'h2', '2025-02-01')
    """)
    con.commit()
    con.close()
    return db_path


class TestFindDuplicates:

    def test_detects_duplicate_group(self, db_with_dupes):
        with patch("transform.dedupe.get_connection") as mock_conn:
            mock_conn.return_value = duckdb.connect(str(db_with_dupes))
            stats = find_and_log_duplicates()

        assert stats["total_checked"] == 3
        assert stats["duplicate_groups"] == 1
        assert stats["duplicate_records"] == 1  # 2 in group, keep 1

    def test_no_duplicates(self, db_no_dupes):
        with patch("transform.dedupe.get_connection") as mock_conn:
            mock_conn.return_value = duckdb.connect(str(db_no_dupes))
            stats = find_and_log_duplicates()

        assert stats["total_checked"] == 2
        assert stats["duplicate_groups"] == 0
        assert stats["duplicate_records"] == 0

    def test_empty_table(self, tmp_path):
        db_path = tmp_path / "empty.duckdb"
        con = duckdb.connect(str(db_path))
        con.execute("""
            CREATE TABLE normalized_transactions (
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
        con.commit()
        con.close()

        with patch("transform.dedupe.get_connection") as mock_conn:
            mock_conn.return_value = duckdb.connect(str(db_path))
            stats = find_and_log_duplicates()

        assert stats["total_checked"] == 0
        assert stats["duplicate_groups"] == 0
