"""Tests for staging/load_transactions.py — raw_id generation, txn_to_row
conversion, and parser routing."""

import hashlib
import json

import pytest

from staging.load_transactions import _make_raw_id, _txn_to_row


class TestMakeRawId:

    def test_deterministic(self):
        id1 = _make_raw_id("stmt.pdf", 1, "some raw line")
        id2 = _make_raw_id("stmt.pdf", 1, "some raw line")
        assert id1 == id2

    def test_different_file_different_id(self):
        id1 = _make_raw_id("stmt1.pdf", 1, "line")
        id2 = _make_raw_id("stmt2.pdf", 1, "line")
        assert id1 != id2

    def test_different_page_different_id(self):
        id1 = _make_raw_id("stmt.pdf", 1, "line")
        id2 = _make_raw_id("stmt.pdf", 2, "line")
        assert id1 != id2

    def test_different_line_different_id(self):
        id1 = _make_raw_id("stmt.pdf", 1, "line A")
        id2 = _make_raw_id("stmt.pdf", 1, "line B")
        assert id1 != id2

    def test_is_md5_hex(self):
        rid = _make_raw_id("file.pdf", 1, "line")
        assert len(rid) == 32
        int(rid, 16)  # should not raise — valid hex


class TestTxnToRow:

    def test_basic_conversion(self):
        txn = {
            "source_file": "stmt.pdf",
            "page_number": 2,
            "raw_line": "JAN 15 AMAZON 50.00",
            "institution": "RBC_VISA",
            "transaction_date_raw": "JAN 15 2025",
            "posted_date_raw": "JAN 17 2025",
            "merchant_raw": "AMAZON",
            "description_raw": "",
            "amount_raw": "50.00",
        }
        row = _txn_to_row(txn)
        assert row["institution"] == "RBC_VISA"
        assert row["source_file"] == "stmt.pdf"
        assert row["page_number"] == 2
        assert row["merchant_raw"] == "AMAZON"
        assert row["amount_raw"] == "50.00"
        assert row["raw_id"]  # not empty

    def test_extra_data_packed(self):
        txn = {
            "source_file": "stmt.pdf",
            "page_number": 1,
            "raw_line": "line",
            "institution": "BMO_MASTERCARD",
            "cardholder": "JANE DOE",
            "foreign_currency_info": "USD 100@1.35",
        }
        row = _txn_to_row(txn)
        extra = json.loads(row["extra_data"])
        assert extra["cardholder"] == "JANE DOE"
        assert extra["foreign_currency_info"] == "USD 100@1.35"

    def test_no_extra_data(self):
        txn = {
            "source_file": "stmt.pdf",
            "page_number": 1,
            "raw_line": "line",
            "institution": "RBC_VISA",
        }
        row = _txn_to_row(txn)
        assert row["extra_data"] is None

    def test_missing_fields_default_empty(self):
        txn = {
            "source_file": "stmt.pdf",
            "page_number": 1,
            "raw_line": "line",
        }
        row = _txn_to_row(txn)
        assert row["institution"] == ""
        assert row["merchant_raw"] == ""
        assert row["amount_raw"] == ""
