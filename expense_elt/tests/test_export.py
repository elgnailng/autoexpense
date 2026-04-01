"""Tests for output/csv_export.py — CSV output generation."""

import csv
from pathlib import Path
from unittest.mock import patch

import duckdb
import pytest


def _create_export_db(tmp_path):
    """Create a test DuckDB with data for export testing."""
    db_path = tmp_path / "export_test.duckdb"
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
        CREATE TABLE categorized_transactions (
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

    # 4 transactions: 2 fully deductible, 1 personal, 1 needs review
    con.execute("""
        INSERT INTO normalized_transactions
            (transaction_id, raw_id, institution, source_file, page_number,
             transaction_date, merchant_raw, merchant_normalized, original_amount, currency, is_credit)
        VALUES
            ('txn-biz1', 'r1', 'RBC_VISA', 's1.pdf', 1, '2025-01-15', 'Amazon.ca', 'AMAZON', 150.00, 'CAD', FALSE),
            ('txn-biz2', 'r2', 'RBC_VISA', 's1.pdf', 2, '2025-02-01', 'AWS', 'AWS', 200.00, 'CAD', FALSE),
            ('txn-personal', 'r3', 'BMO_MASTERCARD', 's2.pdf', 1, '2025-02-15', 'Netflix', 'NETFLIX', 19.99, 'CAD', FALSE),
            ('txn-review', 'r4', 'RBC_VISA', 's1.pdf', 3, '2025-03-01', 'Unknown', 'UNKNOWN', 50.00, 'CAD', FALSE)
    """)

    con.execute("""
        INSERT INTO categorized_transactions
            (transaction_id, category, deductible_status, original_amount,
             deductible_amount, confidence, review_required, rule_applied, notes)
        VALUES
            ('txn-biz1', 'Office expenses', 'full', 150.00, 150.00, 0.98, FALSE, 'memory:manual', ''),
            ('txn-biz2', 'Office expenses', 'full', 200.00, 200.00, 0.88, FALSE, 'keyword:aws', ''),
            ('txn-personal', 'Other expenses', 'personal', 19.99, 0.00, 0.90, FALSE, 'keyword:netflix', ''),
            ('txn-review', 'Other expenses', 'needs_review', 50.00, 0.00, 0.00, TRUE, '', '')
    """)
    con.commit()
    con.close()
    return db_path


class TestExportAll:

    def test_generates_four_files(self, tmp_path):
        db_path = _create_export_db(tmp_path)
        output_dir = tmp_path / "output"

        with patch("output.csv_export.get_connection", return_value=duckdb.connect(str(db_path))), \
             patch("output.csv_export._OUTPUT_DIR", output_dir):
            from output.csv_export import export_all
            stats = export_all()

        assert (output_dir / "all_transactions.csv").exists()
        assert (output_dir / "business_expenses.csv").exists()
        assert (output_dir / "review_required.csv").exists()
        assert (output_dir / "category_summary.csv").exists()

    def test_all_transactions_count(self, tmp_path):
        db_path = _create_export_db(tmp_path)
        output_dir = tmp_path / "output"

        with patch("output.csv_export.get_connection", return_value=duckdb.connect(str(db_path))), \
             patch("output.csv_export._OUTPUT_DIR", output_dir):
            from output.csv_export import export_all
            stats = export_all()

        assert stats["all_transactions"] == 4

    def test_business_expenses_excludes_personal_and_review(self, tmp_path):
        db_path = _create_export_db(tmp_path)
        output_dir = tmp_path / "output"

        with patch("output.csv_export.get_connection", return_value=duckdb.connect(str(db_path))), \
             patch("output.csv_export._OUTPUT_DIR", output_dir):
            from output.csv_export import export_all
            stats = export_all()

        # Only txn-biz1 and txn-biz2 are deductible + not in review
        assert stats["business_expenses"] == 2

        # Verify CSV content
        with open(output_dir / "business_expenses.csv", "r", encoding="utf-8") as f:
            rows = list(csv.DictReader(f))
        assert len(rows) == 2
        merchants = {r["merchant_normalized"] for r in rows}
        assert "AMAZON" in merchants
        assert "AWS" in merchants
        assert "NETFLIX" not in merchants
        assert "UNKNOWN" not in merchants

    def test_review_required_csv(self, tmp_path):
        db_path = _create_export_db(tmp_path)
        output_dir = tmp_path / "output"

        with patch("output.csv_export.get_connection", return_value=duckdb.connect(str(db_path))), \
             patch("output.csv_export._OUTPUT_DIR", output_dir):
            from output.csv_export import export_all
            stats = export_all()

        assert stats["review_required"] == 1

    def test_category_summary_aggregation(self, tmp_path):
        db_path = _create_export_db(tmp_path)
        output_dir = tmp_path / "output"

        with patch("output.csv_export.get_connection", return_value=duckdb.connect(str(db_path))), \
             patch("output.csv_export._OUTPUT_DIR", output_dir):
            from output.csv_export import export_all
            stats = export_all()

        with open(output_dir / "category_summary.csv", "r", encoding="utf-8") as f:
            rows = list(csv.DictReader(f))

        # Only deductible_status in (full, partial) and review_required=FALSE
        # That's txn-biz1 (150) and txn-biz2 (200), both "Office expenses"
        assert len(rows) == 1  # one category group
        assert rows[0]["category"] == "Office expenses"
        assert float(rows[0]["total_deductible_amount"]) == 350.0
        assert int(rows[0]["transaction_count"]) == 2

    def test_empty_db_produces_empty_csvs(self, tmp_path):
        db_path = tmp_path / "empty.duckdb"
        con = duckdb.connect(str(db_path))
        con.execute("""
            CREATE TABLE normalized_transactions (
                transaction_id VARCHAR PRIMARY KEY, raw_id VARCHAR, institution VARCHAR,
                source_file VARCHAR, page_number INTEGER, transaction_date DATE,
                posted_date DATE, merchant_raw VARCHAR, merchant_normalized VARCHAR,
                description_raw VARCHAR, original_amount DECIMAL(10,2),
                currency VARCHAR DEFAULT 'CAD', is_credit BOOLEAN, dedupe_hash VARCHAR,
                normalized_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)
        """)
        con.execute("""
            CREATE TABLE categorized_transactions (
                transaction_id VARCHAR PRIMARY KEY, category VARCHAR,
                deductible_status VARCHAR, original_amount DECIMAL(10,2),
                deductible_amount DECIMAL(10,2), confidence DECIMAL(4,2),
                review_required BOOLEAN, rule_applied VARCHAR, notes VARCHAR,
                categorized_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)
        """)
        con.commit()
        con.close()

        output_dir = tmp_path / "output"
        with patch("output.csv_export.get_connection", return_value=duckdb.connect(str(db_path))), \
             patch("output.csv_export._OUTPUT_DIR", output_dir):
            from output.csv_export import export_all
            stats = export_all()

        assert stats["all_transactions"] == 0
        assert stats["business_expenses"] == 0
        assert stats["review_required"] == 0
        assert stats["category_summary"] == 0
