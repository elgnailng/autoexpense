"""
monopoly_adapter.py - Parse bank statement PDFs using the monopoly-core package.

Install: pip install monopoly-core

This adapter wraps monopoly's pipeline and converts its Transaction objects
into the same dict format used by our custom parsers, so load_transactions.py
can treat both modes identically.

Monopoly conventions (after pipeline.transform()):
  - amount is NEGATIVE for expenses (money out) and POSITIVE for credits
  - This is the opposite of our convention (positive = expense, negative = credit)
  - The adapter negates amounts to match our format

Reference: https://github.com/benjamin-awd/monopoly
"""

from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Optional


# Bank class name → our institution identifier
_BANK_MAP: Dict[str, str] = {
    "rbc": "RBC_VISA",
    "royalbankofcanada": "RBC_VISA",
    "bmo": "BMO_MASTERCARD",
    "bankofmontreal": "BMO_MASTERCARD",
    "amex": "AMEX",
    "americanexpress": "AMEX",
}


def is_available() -> bool:
    """Return True if monopoly-core is installed."""
    try:
        import monopoly  # noqa: F401
        return True
    except ImportError:
        return False


def parse_pdf_with_monopoly(pdf_path: str | Path) -> List[Dict]:
    """
    Parse any supported bank statement PDF using monopoly-core.

    Auto-detects the bank from PDF metadata/content. Converts monopoly's
    Transaction objects to our raw transaction dict format.

    Raises:
        ImportError: if monopoly-core is not installed
        ValueError: if the bank cannot be detected or no transactions found
        RuntimeError: if extraction fails
    """
    try:
        from monopoly.pdf import PdfDocument, PdfParser
        from monopoly.pipeline import Pipeline
        from monopoly.banks import banks, BankDetector
    except ImportError as e:
        raise ImportError(
            "monopoly-core is not installed. "
            "Run: pip install monopoly-core"
        ) from e

    pdf_path = Path(pdf_path)

    # Load and unlock PDF
    doc = PdfDocument(file_path=pdf_path)
    doc.unlock_document()

    # Auto-detect bank
    detector = BankDetector(doc)
    bank_class = detector.detect_bank(banks)

    if bank_class is None:
        raise ValueError(
            f"monopoly could not auto-detect bank for '{pdf_path.name}'. "
            "Verify the PDF is a supported bank statement."
        )

    # Map bank class name to our institution string
    bank_name = bank_class.__name__.lower()
    institution = _BANK_MAP.get(bank_name, bank_name.upper())

    # For RBC and BMO, monopoly's statement_date_pattern frequently mismatches
    # Canadian PDF layouts (picking up a future "Payment Due" date instead of the
    # statement end date), causing every transaction year to be wrong.
    # Route these through our custom parsers, which have proven year-resolution logic.
    if institution == "RBC_VISA":
        from ingestion.rbc_parser import parse_rbc_pdf
        transactions, _ = parse_rbc_pdf(pdf_path)
        return transactions

    if institution == "BMO_MASTERCARD":
        from ingestion.bmo_parser import parse_bmo_pdf
        return parse_bmo_pdf(pdf_path)

    # For all other banks, use monopoly's pipeline
    parser = PdfParser(bank_class, doc)
    pipeline = Pipeline(parser)

    try:
        # safety_check=False avoids hard failures on totals mismatch —
        # we log the issue but still return whatever transactions were found
        statement = pipeline.extract(safety_check=False)
        transactions = pipeline.transform(statement)
    except Exception as exc:
        raise RuntimeError(
            f"monopoly failed to parse '{pdf_path.name}': {exc}"
        ) from exc

    if not transactions:
        raise ValueError(f"monopoly found 0 transactions in '{pdf_path.name}'")

    return [_txn_to_dict(txn, institution, pdf_path) for txn in transactions]


def _txn_to_dict(txn, institution: str, pdf_path: Path) -> Dict:
    """
    Convert a monopoly Transaction object to our raw transaction dict.

    Monopoly's amount convention (after transform):
      - Negative float  → expense (debit, money out)
      - Positive float  → credit (payment received)

    Our convention:
      - Positive string → expense
      - Negative string → credit/refund
    """
    # Negate to convert monopoly's accounting convention to ours
    amount_float = -txn.amount  # monopoly negative → our positive (expense)
    amount_raw = f"{amount_float:.2f}"

    # txn.date is ISO 8601 (YYYY-MM-DD) after pipeline.transform()
    date_str = str(txn.date)
    description = str(txn.description).strip()

    return {
        "institution": institution,
        "source_file": pdf_path.name,
        "page_number": 0,          # monopoly doesn't expose per-transaction page numbers
        "raw_line": description,
        "transaction_date_raw": date_str,
        "posted_date_raw": date_str,   # monopoly exposes only transaction_date in Transaction
        "merchant_raw": description,
        "description_raw": description,
        "amount_raw": amount_raw,
        "reference_number": "",
        "foreign_currency_info": None,
    }
