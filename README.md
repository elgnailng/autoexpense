# Expense ELT

> Local-first Python ELT pipeline for extracting, categorizing, and exporting self-employed business expenses from bank PDF statements.

Built for Canadian (BC) self-employment tax prep. Extracts transactions from bank statements, categorizes them using a multi-layer AI engine, and exports CRA-ready expense reports.

## Features

- **Multi-bank PDF parsing** -- RBC Visa, BMO Mastercard, AMEX (via [monopoly-core](https://github.com/nicholasclKUL/monopoly-core) or custom regex parsers)
- **AI-powered categorization** -- LLM evaluator (Claude/OpenAI) with BC accountant persona, confidence scoring, and automatic review flagging
- **Multi-layer classification** -- merchant memory (fuzzy matching) > LLM evaluation > keyword rules > manual review fallback
- **Configurable deduction rules** -- fixed monthly caps, percentage-based, full, or personal deductions with date bounds
- **Three interfaces** -- CLI (typer), React SPA (mobile-optimized with swipe gestures), Streamlit dashboard
- **Multi-user auth** -- Google OAuth with owner + accountant roles, personal expense privacy
- **Idempotent pipeline** -- safe to rerun; deduplication via SHA-256 hashing
- **Local-first** -- all data stays in a local DuckDB file, no cloud dependencies

## Architecture

```
PDFs (RBC / BMO / AMEX)
      |
      v
+--------------+     monopoly-core (default) or custom regex parsers
|  ingestion/  |---- rbc_parser.py, bmo_parser.py, monopoly_adapter.py
|  pdf_reader  |     extract raw rows per page
+------+-------+
       | structured dicts
       v
+---------------------+
|  staging/           |
|  load_transactions  |--> raw_transactions  (DuckDB)
+------+--------------+
       | raw rows
       v
+-------------+
|  transform/ |
|  normalize  |--> normalized_transactions  (DuckDB)
|  dedupe     |    logs duplicates to logs/duplicates.log
+------+------+
       | normalized rows
       v
+----------------------+
|  categorization/     |
|  Layer 1: memory     |  exact + fuzzy match (rapidfuzz) on merchant_memory.csv
|  Layer 2: LLM eval   |  (--use-llm) BC accountant persona via Claude/OpenAI
|  Layer 2b: rules     |  keyword match on merchant_normalized (when no --use-llm)
|  Layer 3: fallback   |  review_required = True (when no --use-llm)
|  deduction rules     |  applies fixed/percentage caps from deduction_rules.yaml
+------+---------------+
       | category + deductible amounts
       v
+----------------------+
|  categorized_        |  (DuckDB)
|  transactions        |
+------+---------------+
       |
  +----+------------+
  |    |             |
  v    v             v
CLI  Web UIs       output/
     (Streamlit    csv_export.py
      + React)     -> business_expenses.csv
                   -> all_transactions.csv
                   -> review_required.csv
                   -> category_summary.csv

+------------------------------------------+
|  Web Stack                               |
|                                          |
|  React SPA --> FastAPI --> DuckDB        |
|  (frontend/)   (api/)     (state/)      |
|                                          |
|  Streamlit --> DuckDB directly           |
|  (pages/)     (state/)                  |
+------------------------------------------+
```

## Quick Start

### Prerequisites

- Python 3.11+
- Node.js 20+ (for the React frontend)
- `libpoppler-cpp-dev` and `pkg-config` (Linux, for PDF parsing)

### Install

```bash
# Clone
git clone https://github.com/elgnailng/expense-elt.git
cd expense-elt

# Python dependencies
cd expense_elt
pip install -r requirements.txt

# Frontend
cd ../frontend
npm install
npm run build
```

### Configure

```bash
# Copy the env template
cp expense_elt/.env.example expense_elt/.env

# Edit with your Google OAuth Client ID and email
# See: https://console.cloud.google.com/apis/credentials
```

### Add bank statements

Place PDF statements in the appropriate directories:

```
expense_elt/data/RBC_Visa/
expense_elt/data/BMO_Mastercard/
expense_elt/data/Amex/
```

### Run the pipeline

```bash
cd expense_elt

# Run all steps (extract -> transform -> categorize -> export)
python main.py run

# Or run steps individually
python main.py extract       # Parse PDFs
python main.py transform     # Normalize + deduplicate
python main.py categorize    # Apply rules + merchant memory
python main.py export        # Write CSVs to output/

# With LLM-powered categorization (requires ANTHROPIC_API_KEY or OPENAI_API_KEY)
python main.py categorize --use-llm
```

### Start the web UI

```bash
cd expense_elt
python main.py serve    # http://localhost:9743
```

## CLI Commands

| Command | Description |
|---|---|
| `extract` | Parse PDFs into raw_transactions (`--parser monopoly\|custom\|auto`) |
| `transform` | Normalize + deduplicate |
| `categorize` | Apply rules + merchant memory (`--use-llm` for AI categorization) |
| `review` | Interactive CLI review (`--limit N`) |
| `export` | Write CSVs to output/ |
| `run` | Run all non-interactive steps in sequence |
| `list` | Browse transactions with filters |
| `status` | Show counts at each pipeline stage |
| `serve` | Start FastAPI + React UI (`--port 9743`) |
| `reset` | Wipe data (`--level soft\|medium\|hard`) |
| `restore` | Recover config from backup |

## Tech Stack

**Backend:** Python, FastAPI, DuckDB, pdfplumber, monopoly-core, typer, rapidfuzz

**Frontend:** React 19, TypeScript, Vite, TanStack Query, Tailwind CSS 4

**AI/LLM:** Anthropic Claude, OpenAI (configurable provider), confidence-scored batch evaluation

**Auth:** Google OAuth 2.0, session JWTs, role-based access (owner + accountant)

**Legacy UI:** Streamlit (still functional, maintenance-only)

## CRA Expense Categories

Categories match the CRA T2125 form exactly:

Advertising, Meals & Entertainment, Insurance, Business tax/fees/licences, Office expenses, Supplies, Legal/accounting/professional fees, Management and administration fees, Rent, Maintenance and repairs, Salaries/wages/benefits, Telephone and utilities, Travel, Delivery/freight/express, Motor vehicle expenses, Other expenses

## Configuration

- `config/rules.yaml` -- keyword-to-category mapping rules
- `config/deduction_rules.yaml` -- partial deduction rules (fixed monthly caps, percentages)
- `config/categories.yaml` -- canonical CRA category list
- `config/llm_config.yaml` -- LLM provider, model, batch size, cost limits

See [CLAUDE.md](CLAUDE.md) for detailed documentation of all configuration options.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for development setup, testing, and PR guidelines.

## License

MIT -- see [LICENSE](LICENSE)
