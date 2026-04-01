"""Tests for services/review_service.py — review queue, save, batch apply."""

import csv
from pathlib import Path
from unittest.mock import patch

import duckdb
import pytest

from categorization.merchant_memory import MerchantMemory, _FIELDNAMES
from services.review_service import (
    batch_apply,
    count_similar,
    load_review_queue,
    save_single_review,
    suggest_keyword,
)


def _create_test_db(tmp_path):
    """Create a test DuckDB with normalized + categorized tables and sample data."""
    db_path = tmp_path / "test_review.duckdb"
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

    # Insert normalized records
    con.execute("""
        INSERT INTO normalized_transactions
            (transaction_id, raw_id, institution, source_file, page_number,
             transaction_date, merchant_raw, merchant_normalized, original_amount)
        VALUES
            ('txn-r1', 'raw-1', 'RBC_VISA', 's1.pdf', 1, '2025-01-15', 'Amazon.ca', 'AMAZON', 50.00),
            ('txn-r2', 'raw-2', 'RBC_VISA', 's1.pdf', 2, '2025-01-20', 'Amazon.ca', 'AMAZON', 75.00),
            ('txn-r3', 'raw-3', 'BMO_MASTERCARD', 's2.pdf', 1, '2025-02-01', 'Netflix', 'NETFLIX', 19.99),
            ('txn-ok', 'raw-4', 'RBC_VISA', 's1.pdf', 3, '2025-02-15', 'Shell Gas', 'SHELL GAS', 80.00)
    """)

    # Insert categorized: 3 needing review, 1 already OK
    con.execute("""
        INSERT INTO categorized_transactions
            (transaction_id, category, deductible_status, original_amount,
             deductible_amount, confidence, review_required, rule_applied, notes)
        VALUES
            ('txn-r1', 'Other expenses', 'needs_review', 50.00, 0.00, 0.00, TRUE, '', ''),
            ('txn-r2', 'Other expenses', 'needs_review', 75.00, 0.00, 0.00, TRUE, '', ''),
            ('txn-r3', 'Other expenses', 'needs_review', 19.99, 0.00, 0.50, TRUE, 'keyword:netflix', ''),
            ('txn-ok', 'Motor vehcie expenses', 'full', 80.00, 80.00, 0.98, FALSE, 'memory:manual', '')
    """)
    con.commit()
    con.close()
    return db_path


class TestLoadReviewQueue:

    def test_returns_only_review_required(self, tmp_path):
        db_path = _create_test_db(tmp_path)
        with patch("services.review_service.get_connection", return_value=duckdb.connect(str(db_path))):
            queue = load_review_queue()
        assert len(queue) == 3
        for item in queue:
            assert "transaction_id" in item
            assert "merchant_normalized" in item

    def test_ordered_by_date(self, tmp_path):
        db_path = _create_test_db(tmp_path)
        with patch("services.review_service.get_connection", return_value=duckdb.connect(str(db_path))):
            queue = load_review_queue()
        dates = [str(q["transaction_date"]) for q in queue]
        assert dates == sorted(dates)

    def test_empty_when_no_reviews(self, tmp_path):
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

        with patch("services.review_service.get_connection", return_value=duckdb.connect(str(db_path))):
            queue = load_review_queue()
        assert queue == []


class TestSaveSingleReview:

    def test_updates_db_and_memory(self, tmp_path):
        db_path = _create_test_db(tmp_path)
        mem_file = tmp_path / "merchant_memory.csv"
        with open(mem_file, "w", newline="", encoding="utf-8") as fh:
            writer = csv.DictWriter(fh, fieldnames=_FIELDNAMES)
            writer.writeheader()
        memory = MerchantMemory(memory_file=mem_file)

        with patch("services.review_service.get_connection", return_value=duckdb.connect(str(db_path))), \
             patch("services.review_service.get_memory", return_value=memory):
            save_single_review(
                transaction_id="txn-r1",
                category="Office expenses",
                deductible_status="full",
                deductible_amount=50.0,
                notes="Cloud service",
                merchant_normalized="AMAZON",
                merchant_raw="Amazon.ca",
            )

        # Verify DB updated
        con = duckdb.connect(str(db_path))
        row = con.execute(
            "SELECT category, confidence, review_required FROM categorized_transactions WHERE transaction_id = 'txn-r1'"
        ).fetchone()
        con.close()
        assert row[0] == "Office expenses"
        assert float(row[1]) == 1.0
        assert row[2] is False

        # Verify merchant memory updated
        result = memory.lookup("AMAZON")
        assert result is not None
        assert result[0] == "Office expenses"


class TestBatchApply:

    def test_applies_to_all_matching_merchants(self, tmp_path):
        db_path = _create_test_db(tmp_path)
        with patch("services.review_service.get_connection", return_value=duckdb.connect(str(db_path))):
            count = batch_apply(
                merchant_normalized="AMAZON",
                category="Office expenses",
                deductible_status="full",
                notes="Bulk reviewed",
            )

        assert count == 2  # txn-r1 and txn-r2

        # Verify both updated
        con = duckdb.connect(str(db_path))
        rows = con.execute(
            "SELECT review_required, deductible_amount FROM categorized_transactions WHERE transaction_id IN ('txn-r1', 'txn-r2')"
        ).fetchall()
        con.close()
        for review_req, ded_amount in rows:
            assert review_req is False
            assert float(ded_amount) > 0

    def test_personal_sets_zero_deductible(self, tmp_path):
        db_path = _create_test_db(tmp_path)
        with patch("services.review_service.get_connection", return_value=duckdb.connect(str(db_path))):
            batch_apply(
                merchant_normalized="NETFLIX",
                category="Other expenses",
                deductible_status="personal",
                notes="Personal subscription",
            )

        con = duckdb.connect(str(db_path))
        row = con.execute(
            "SELECT deductible_amount, deductible_status FROM categorized_transactions WHERE transaction_id = 'txn-r3'"
        ).fetchone()
        con.close()
        assert float(row[0]) == 0.0
        assert row[1] == "personal"


class TestCountSimilar:

    def test_counts_excluding_current(self):
        queue = [
            {"merchant_normalized": "AMAZON"},
            {"merchant_normalized": "AMAZON"},
            {"merchant_normalized": "NETFLIX"},
        ]
        assert count_similar("AMAZON", queue) == 1  # 2 total - 1 = 1

    def test_no_similar(self):
        queue = [{"merchant_normalized": "NETFLIX"}]
        assert count_similar("AMAZON", queue) == -1  # 0 - 1 = -1 (none present minus self)

    def test_empty_merchant(self):
        queue = [{"merchant_normalized": "AMAZON"}]
        assert count_similar("", queue) == 0


class TestSuggestKeyword:

    def test_extracts_first_word(self):
        assert suggest_keyword("AMAZON WEB SERVICES") == "amazon"

    def test_skips_short_tokens(self):
        assert suggest_keyword("A B LONGWORD") == "longword"

    def test_empty_string(self):
        assert suggest_keyword("") == ""
