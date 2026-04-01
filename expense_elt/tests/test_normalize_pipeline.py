"""Integration test for the full normalize pipeline: raw → normalized."""

from unittest.mock import patch

import duckdb
import pytest

from transform.normalize import normalize_transactions


def _create_raw_db(tmp_path):
    """Create a DuckDB with raw_transactions + empty normalized table."""
    db_path = tmp_path / "pipeline_test.duckdb"
    con = duckdb.connect(str(db_path))

    con.execute("""
        CREATE TABLE raw_transactions (
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

    # Insert raw data simulating RBC and BMO formats
    con.execute("""
        INSERT INTO raw_transactions
            (raw_id, institution, source_file, page_number, raw_line,
             transaction_date_raw, posted_date_raw, merchant_raw, amount_raw)
        VALUES
            ('raw-1', 'RBC_VISA', 'stmt1.pdf', 1, 'JAN 15 JAN 17 AMAZON 50.00',
             'JAN 15 2025', 'JAN 17 2025', 'AMAZON.CA*ZR3WI9700', '$50.00'),
            ('raw-2', 'BMO_MASTERCARD', 'stmt2.pdf', 1, 'Feb. 01 NETFLIX 19.99',
             'Feb. 01 2025', '', 'NETFLIX.COM', '19.99'),
            ('raw-3', 'RBC_VISA', 'stmt1.pdf', 2, 'MAR 10 REFUND -25.00',
             'MAR 10 2025', '', 'AMAZON REFUND', '-25.00')
    """)
    con.commit()
    con.close()
    return db_path


class TestNormalizePipeline:

    def test_normalizes_all_raw(self, tmp_path):
        db_path = _create_raw_db(tmp_path)
        with patch("transform.normalize.get_connection", return_value=duckdb.connect(str(db_path))):
            stats = normalize_transactions()

        assert stats["total_raw"] == 3
        assert stats["normalized"] == 3
        assert stats["skipped"] == 0
        assert stats["errors"] == 0

    def test_merchant_normalization_applied(self, tmp_path):
        db_path = _create_raw_db(tmp_path)
        with patch("transform.normalize.get_connection", return_value=duckdb.connect(str(db_path))):
            normalize_transactions()

        con = duckdb.connect(str(db_path))
        rows = con.execute(
            "SELECT merchant_normalized FROM normalized_transactions ORDER BY merchant_normalized"
        ).fetchall()
        con.close()

        merchants = [r[0] for r in rows]
        # AMAZON.CA*ZR3WI9700 → should have reference code stripped
        amazon = [m for m in merchants if "AMAZON" in m]
        assert len(amazon) >= 1
        for m in amazon:
            assert "*ZR3WI9700" not in m

    def test_credit_detected(self, tmp_path):
        db_path = _create_raw_db(tmp_path)
        with patch("transform.normalize.get_connection", return_value=duckdb.connect(str(db_path))):
            normalize_transactions()

        con = duckdb.connect(str(db_path))
        row = con.execute(
            "SELECT original_amount, is_credit FROM normalized_transactions WHERE raw_id = 'raw-3'"
        ).fetchone()
        con.close()

        assert float(row[0]) < 0  # negative amount
        assert row[1] is True  # is_credit

    def test_idempotent_rerun(self, tmp_path):
        db_path = _create_raw_db(tmp_path)

        # First run
        with patch("transform.normalize.get_connection", return_value=duckdb.connect(str(db_path))):
            stats1 = normalize_transactions()

        # Second run — should skip all
        with patch("transform.normalize.get_connection", return_value=duckdb.connect(str(db_path))):
            stats2 = normalize_transactions()

        assert stats1["normalized"] == 3
        assert stats2["normalized"] == 0
        assert stats2["skipped"] == 3

    def test_dedupe_hash_populated(self, tmp_path):
        db_path = _create_raw_db(tmp_path)
        with patch("transform.normalize.get_connection", return_value=duckdb.connect(str(db_path))):
            normalize_transactions()

        con = duckdb.connect(str(db_path))
        rows = con.execute(
            "SELECT dedupe_hash FROM normalized_transactions WHERE dedupe_hash IS NOT NULL"
        ).fetchall()
        con.close()

        assert len(rows) == 3  # all should have a hash
        for row in rows:
            assert len(row[0]) == 32
