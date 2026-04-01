# CLAUDE.md — PDF Ingestion

## Overview

Extracts raw transaction rows from bank PDF statements. Supports multiple parser backends and institutions.

## Structure

```
ingestion/
├── pdf_reader.py         # pdfplumber wrapper — common page text extraction
├── rbc_parser.py         # RBC Visa regex parser
├── bmo_parser.py         # BMO Mastercard regex parser
├── amex_parser.py        # AMEX parser (stub — not yet implemented)
└── monopoly_adapter.py   # monopoly-core wrapper (bank-agnostic)
```

## Parser Modes

Selected via `--parser` flag on `extract` command:

| Mode | Description |
|---|---|
| `monopoly` (default) | Uses `monopoly-core` library for bank-agnostic parsing. Auto-detects institution from PDF content. |
| `custom` | Uses built-in regex parsers (`rbc_parser.py`, `bmo_parser.py`). No extra dependencies beyond pdfplumber. |
| `auto` | Tries custom parsers first; falls back to monopoly if 0 transactions extracted from a file. |

## Custom Parsers

Each custom parser (`rbc_parser.py`, `bmo_parser.py`) follows the same interface:
- Input: PDF file path
- Output: list of dicts with fields: `institution`, `source_file`, `page_number`, `raw_line`, `transaction_date_raw`, `merchant_raw`, `description_raw`, `amount_raw`
- Uses `pdfplumber` to extract page text, then regex patterns to identify transaction lines
- Parse failures logged to `logs/parse_errors.log`, partial matches to `logs/parse_skipped.log`

## monopoly_adapter.py

- Wraps `monopoly-core` Transaction objects into the same dict format as custom parsers
- For RBC/BMO: custom parsers are preferred (monopoly has unreliable year detection for these institutions)
- For other banks (AMEX, etc.): monopoly is used directly

## Adding a New Bank

1. Create `ingestion/<bank>_parser.py` following the existing interface
2. Register it in `staging/load_transactions.py`
3. Or rely on `monopoly-core` if it supports the bank's statement format
