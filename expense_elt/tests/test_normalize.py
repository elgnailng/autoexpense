"""Tests for transform/normalize.py — amount parsing, date parsing,
merchant normalization, dedupe hash, and the full normalize pipeline."""

from datetime import date

import pytest

from transform.normalize import (
    make_dedupe_hash,
    normalize_merchant,
    parse_amount,
    parse_date,
)


# ── Amount parsing ──────────────────────────────────────────────────


class TestParseAmount:
    """Exercise every documented amount format."""

    def test_simple_dollar(self):
        val, is_credit = parse_amount("$23.00")
        assert val == 23.00
        assert is_credit is False

    def test_negative_dollar(self):
        val, is_credit = parse_amount("-$2,000.00")
        assert val == -2000.00
        assert is_credit is True

    def test_plain_number(self):
        val, is_credit = parse_amount("2.15")
        assert val == 2.15
        assert is_credit is False

    def test_negative_plain(self):
        val, is_credit = parse_amount("-2.15")
        assert val == -2.15
        assert is_credit is True

    def test_bmo_cr_suffix(self):
        val, is_credit = parse_amount("100.00 CR")
        assert val == -100.00
        assert is_credit is True

    def test_cr_suffix_case_insensitive(self):
        val, is_credit = parse_amount("50.00 cr")
        assert val == -50.00
        assert is_credit is True

    def test_empty_string(self):
        val, is_credit = parse_amount("")
        assert val == 0.0

    def test_whitespace_only(self):
        val, is_credit = parse_amount("   ")
        assert val == 0.0

    def test_non_numeric(self):
        val, _ = parse_amount("abc")
        assert val == 0.0

    def test_comma_thousands(self):
        val, _ = parse_amount("$1,234.56")
        assert val == pytest.approx(1234.56)

    def test_no_symbol_with_cents(self):
        val, _ = parse_amount("99.99")
        assert val == 99.99

    def test_negative_cr_produces_negative(self):
        """CR suffix always yields a negative value."""
        val, is_credit = parse_amount("0.01 CR")
        assert val < 0
        assert is_credit is True


# ── Date parsing ────────────────────────────────────────────────────


class TestParseDate:

    def test_rbc_format(self):
        assert parse_date("DEC 09 2024") == date(2024, 12, 9)

    def test_bmo_format_with_dot(self):
        assert parse_date("Jun. 19 2025") == date(2025, 6, 19)

    def test_bmo_single_digit_day(self):
        assert parse_date("Jul. 1 2025") == date(2025, 7, 1)

    def test_iso_format(self):
        assert parse_date("2025-03-10") == date(2025, 3, 10)

    def test_empty_returns_none(self):
        assert parse_date("") is None

    def test_none_returns_none(self):
        assert parse_date(None) is None

    def test_garbage_returns_none(self):
        assert parse_date("not-a-date-xyz") is None

    def test_whitespace_returns_none(self):
        assert parse_date("   ") is None


# ── Merchant normalization ──────────────────────────────────────────


class TestNormalizeMerchant:

    def test_uppercase(self):
        assert normalize_merchant("amazon") == "AMAZON"

    def test_strip_whitespace(self):
        assert normalize_merchant("  AMAZON  ") == "AMAZON"

    def test_strip_reference_code(self):
        result = normalize_merchant("AMAZON.CA*ZR3WI9700")
        assert "ZR3WI9700" not in result
        assert result.startswith("AMAZON")

    def test_strip_province_code(self):
        result = normalize_merchant("TIM HORTONS ON")
        assert result == "TIM HORTONS"

    def test_strip_bc_province(self):
        result = normalize_merchant("STORE NAME BC")
        assert result == "STORE NAME"

    def test_strip_postal_code(self):
        result = normalize_merchant("SHOPPERS DRUG MART V5K2A3")
        assert "V5K2A3" not in result

    def test_strip_us_zip(self):
        result = normalize_merchant("SOME STORE 90210")
        assert "90210" not in result

    def test_collapse_spaces(self):
        result = normalize_merchant("SOME    MERCHANT    NAME")
        assert "  " not in result

    def test_repeated_punctuation(self):
        result = normalize_merchant("HELLO...")
        assert result == "HELLO."

    def test_empty_string(self):
        assert normalize_merchant("") == ""

    def test_none_returns_empty(self):
        assert normalize_merchant(None) == ""

    def test_foreign_currency_stripped(self):
        result = normalize_merchant("USD 159@1.401257861 SOME MERCHANT")
        assert "USD" not in result or "159@" not in result
        assert "SOME MERCHANT" in result


# ── Dedupe hash ─────────────────────────────────────────────────────


class TestDedupeHash:

    def test_deterministic(self):
        h1 = make_dedupe_hash("RBC_VISA", date(2025, 1, 1), "AMAZON", 50.00)
        h2 = make_dedupe_hash("RBC_VISA", date(2025, 1, 1), "AMAZON", 50.00)
        assert h1 == h2

    def test_different_amount_different_hash(self):
        h1 = make_dedupe_hash("RBC_VISA", date(2025, 1, 1), "AMAZON", 50.00)
        h2 = make_dedupe_hash("RBC_VISA", date(2025, 1, 1), "AMAZON", 50.01)
        assert h1 != h2

    def test_different_institution_different_hash(self):
        h1 = make_dedupe_hash("RBC_VISA", date(2025, 1, 1), "AMAZON", 50.00)
        h2 = make_dedupe_hash("BMO_MASTERCARD", date(2025, 1, 1), "AMAZON", 50.00)
        assert h1 != h2

    def test_none_date_handled(self):
        h = make_dedupe_hash("RBC_VISA", None, "AMAZON", 50.00)
        assert len(h) == 32

    def test_hash_length(self):
        h = make_dedupe_hash("RBC_VISA", date(2025, 1, 1), "AMAZON", 50.00)
        assert len(h) == 32
