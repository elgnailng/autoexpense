# Tax Expense ELT

Local CLI pipeline for parsing RBC Visa and BMO Mastercard PDF statements into tax-ready CSV exports. Built for BC self-employment bookkeeping.

## Quick Start

```bash
cd expense_elt
pip install -r requirements-dev.txt

# Run the full pipeline (non-interactive steps)
python main.py run

# Then review any flagged transactions
python main.py review

# Check pipeline status at any time
python main.py status
```

## Commands

| Command | What it does |
|---|---|
| `python main.py extract` | Parse PDFs -> load raw transactions into DB |
| `python main.py transform` | Normalize + deduplicate |
| `python main.py categorize` | Apply rules + merchant memory |
| `python main.py review` | Interactive CLI review of unknowns |
| `python main.py export` | Write CSVs to `output/` |
| `python main.py run` | All non-interactive steps in sequence |
| `python main.py status` | Show counts at each stage |

Add `--verbose` / `-v` for detail. Use `--limit N` with `review` to cap session size.

## Inputs

Place PDF statements in:
- `data/RBC_Visa/`
- `data/BMO_Mastercard/`

The pipeline scans these folders recursively.

## Validation

```bash
cd expense_elt
python -m pytest -q

cd ../frontend
npm ci
npm run typecheck
npm run build
```

For the current release, frontend validation is typecheck plus production build. A dedicated frontend test harness is planned separately.

## Outputs

Written to `output/`:

| File | Contents |
|---|---|
| `business_expenses.csv` | Deductible transactions |
| `all_transactions.csv` | All transactions |
| `review_required.csv` | Still needs manual review |
| `category_summary.csv` | Totals by CRA category |

## Configuration

| File | Purpose |
|---|---|
| `config/rules.yaml` | Keyword -> category rules |
| `config/deduction_rules.yaml` | Partial/fixed deduction rules (e.g. phone at $97/month) |
| `config/categories.yaml` | Valid CRA T2125 category names |

To add a new merchant rule, edit `config/rules.yaml`.
To adjust partial deductions (phone, home office, etc.), edit `config/deduction_rules.yaml`.
Manual review decisions are persisted in `state/merchant_memory.csv` and take priority on reruns.

## Adding a New Institution (e.g. AMEX)

1. Create `ingestion/amex_parser.py` following the pattern of `rbc_parser.py`
2. Register it in `staging/load_transactions.py`

## Dependencies

```
pdfplumber, duckdb, typer, rapidfuzz, pyyaml, rich, python-dateutil
```

