# CLAUDE.md — Tax2025 Expense ELT

## Project Overview

Local-first Python ELT pipeline for extracting, categorizing, and exporting self-employed business expenses from bank PDF statements. Includes a CLI, Streamlit web dashboard, FastAPI REST backend, and a React TypeScript SPA with mobile-optimized gesture-driven review. Target use: BC self-employment tax prep.

## Key Concepts

| Concept | Description |
|---|---|
| **Raw transaction** | Unmodified row extracted directly from a PDF — never mutated |
| **Normalized transaction** | Cleaned record with standardized dates, amounts, and merchant name |
| **Categorized transaction** | Normalized record with CRA category, deductible status, and deductible amount |
| **Merchant memory** | Persistent CSV of past categorization decisions, keyed on `merchant_normalized` |
| **Deductible status** | One of `full`, `partial`, `personal`, `needs_review` — controls how much of a transaction counts as a business expense |
| **Deductible amount** | The portion of `original_amount` claimable as a business expense (computed per transaction using deduction rules) |
| **Confidence score** | Float 0.0–1.0 indicating how certain the system is about a categorization. Below 0.70–0.85 (depending on source) triggers `review_required` |
| **Dedupe hash** | SHA-256 of `(institution, transaction_date, amount, merchant_normalized)` — prevents duplicate rows from multiple pipeline runs |
| **Idempotency** | Every pipeline step is safe to rerun; already-processed records are skipped, not duplicated |
| **LLM evaluator** | Optional LLM-based categorization (`--use-llm`) that replaces keyword rules + fallback. Uses a BC accountant persona with anti-hallucination rules. Merchant memory still wins. |

---

## Architecture

```
PDFs (RBC / BMO / AMEX)
      │
      ▼
┌──────────────┐     monopoly-core (default) or custom regex parsers
│  ingestion/  │────  rbc_parser.py, bmo_parser.py, monopoly_adapter.py
│  pdf_reader  │     extract raw rows per page
└──────┬───────┘
       │ structured dicts
       ▼
┌─────────────────────┐
│  staging/           │
│  load_transactions  │──→  raw_transactions  (DuckDB)
└──────┬──────────────┘
       │ raw rows
       ▼
┌─────────────┐
│  transform/ │
│  normalize  │──→  normalized_transactions  (DuckDB)
│  dedupe     │     logs duplicates to logs/duplicates.log
└──────┬──────┘
       │ normalized rows
       ▼
┌──────────────────────┐
│  categorization/     │
│  Layer 1: memory     │  exact + fuzzy match (rapidfuzz) on merchant_memory.csv
│  Layer 2: LLM eval   │  (--use-llm) BC accountant persona via Claude/OpenAI
│  Layer 2b: rules     │  keyword match on merchant_normalized (when no --use-llm)
│  Layer 3: fallback   │  review_required = True (when no --use-llm)
│  deduction rules     │  applies fixed/percentage caps from deduction_rules.yaml
└──────┬───────────────┘
       │ category + deductible amounts
       ▼
┌──────────────────────┐
│  categorized_        │  (DuckDB)
│  transactions        │
└──────┬───────────────┘
       │
  ┌────┼────────────┐
  │    │             │
  ▼    ▼             ▼
CLI  Web UIs       output/
     (Streamlit    csv_export.py
      + React)     → business_expenses.csv
                   → all_transactions.csv
                   → review_required.csv
                   → category_summary.csv

┌──────────────────────────────────────────┐
│  Web Stack                               │
│                                          │
│  React SPA ──→ FastAPI ──→ DuckDB        │
│  (frontend/)   (api/)      (state/)      │
│                                          │
│  Streamlit ──→ DuckDB directly           │
│  (pages/)      (state/)                  │
└──────────────────────────────────────────┘
```

### Data Store
Single DuckDB file at `expense_elt/state/transactions.duckdb` with four tables:

| Table | Key | Purpose |
|---|---|---|
| `raw_transactions` | `raw_id` (hash of source+line) | Immutable extracted rows |
| `normalized_transactions` | `transaction_id` (UUID) | Cleaned, deduplicated records |
| `categorized_transactions` | `transaction_id` (FK) | Category + deductible amounts |
| `authorized_users` | `email` | Accountant users with role + permissions (managed by owner) |

### Categorization Confidence Thresholds

| Source | Confidence | Triggers review? |
|---|---|---|
| Merchant memory — exact | 0.98 | No |
| Merchant memory — fuzzy | 0.75 | Yes (< 0.85) |
| LLM evaluator | 0.00–1.00 | Yes if `review_flag=true` or confidence < 0.70 |
| Keyword rule — high | 0.88–0.90 | No |
| Keyword rule — low | 0.50–0.75 | Yes (< 0.70) |
| No match (fallback) | 0.00 | Always |

---

## Core Processing Pipeline

### Step 1 — Extract (`python main.py extract`)
- Scans `expense_elt/data/RBC_Visa/` and `expense_elt/data/BMO_Mastercard/` recursively for PDFs
- Default parser: `monopoly-core` library (bank-agnostic). Flags: `--parser monopoly|custom|auto`
- Custom parsers (`rbc_parser.py`, `bmo_parser.py`) use regex-based extraction with `pdfplumber`
- `auto` mode: tries custom parsers first, falls back to monopoly if 0 transactions found
- Rows inserted into `raw_transactions`; duplicates skipped via `raw_id` hash
- Parse failures logged to `logs/parse_errors.log`, partial matches to `logs/parse_skipped.log`

### Step 2 — Transform (`python main.py transform`)
- Reads all `raw_transactions` not yet in `normalized_transactions`
- **Date parsing**: handles multiple formats (`DEC 09 2024`, `Jun. 19 2025`, ISO) via `python-dateutil`
- **Amount parsing**: strips `$`, handles negatives, `CR` suffix (BMO credits → negative float)
- **Merchant normalization**: uppercase, trim whitespace, strip noise suffixes → `merchant_normalized`
- **Dedupe hash**: SHA-256 of `(institution, date, amount, merchant_normalized)` — duplicate groups logged to `logs/duplicates.log`
- Writes into `normalized_transactions` with a new UUID `transaction_id`

### Step 3 — Categorize (`python main.py categorize`)
Processes each `normalized_transaction` not yet in `categorized_transactions`:

1. **Layer 1 — Merchant memory** (`state/merchant_memory.csv`):
   - Exact match → confidence 0.98
   - Fuzzy match via `rapidfuzz` → confidence 0.75
   - Manual decisions always win over rules

2. **Layer 2 — LLM evaluator** (when `--use-llm`):
   - Replaces keyword rules + fallback for transactions not matched by memory
   - BC accountant persona with anti-hallucination rules
   - Returns: category, expensable_pct, confidence, reasoning, review_flag
   - Batch processing with retry, cost tracking, and hot-reload of rules
   - Config: `config/llm_config.yaml` (provider, model, batch_size, cost limits)

2b. **Layer 2b — Rules engine** (`config/rules.yaml`, when no `--use-llm`):
   - Case-insensitive substring match on `merchant_normalized`
   - Confidence set per rule (0.50–0.90)

3. **Layer 3 — Fallback** (when no `--use-llm`):
   - Category: `Other expenses`, confidence: 0.0, `review_required = True`

4. **Deduction rules** (`config/deduction_rules.yaml`) applied per transaction after categorization:
   - `fixed_monthly`: `deductible_amount = min(original_amount, cap)`
   - `percentage`: `deductible_amount = original_amount × pct`
   - `personal`: `deductible_amount = 0`
   - `full`: fully deductible
   - Rules can have date bounds (`start_date`, `end_date`)
   - Credits (negative amounts) are always `personal`, deductible 0
   - Config deduction rules override LLM percentages when matched

### Step 4 — Review
Three review interfaces available:
- **CLI**: `python main.py review` — interactive terminal prompts
- **Streamlit**: `streamlit run app.py` → Review page with auto-save to rules/deductions + batch apply
- **React SPA**: `python main.py serve` → Swipeable card-based review (mobile-optimized)

All interfaces save decisions to `state/merchant_memory.csv` and update `categorized_transactions`. Next categorize run will match via memory — manual decisions persist permanently.

### Step 5 — Export (`python main.py export`)
Joins all three tables and writes:
- `business_expenses.csv` — `deductible_status IN ('full', 'partial')`
- `all_transactions.csv` — all records
- `review_required.csv` — `review_required = True`
- `category_summary.csv` — `SUM(deductible_amount)` grouped by category

---

## Repository Layout

```
expense-elt/
├── CLAUDE.md               # This file — project-wide documentation
├── DEVELOPMENT.md          # Local validation and CI parity commands
├── CONTRIBUTING.md         # Contribution guidelines
├── LICENSE                 # MIT license
│
├── expense_elt/            # Python backend + CLI (all server code lives here)
│   ├── main.py             # CLI entry point (typer) — 12 commands
│   ├── app.py              # Streamlit main page
│   ├── requirements.txt    # Runtime Python dependencies
│   ├── requirements-dev.txt # Test dependencies + runtime requirements
│   ├── CLAUDE.md           # Sub-component docs (see below)
│   │
│   ├── .env.example         # Environment variable template (auth, CORS)
│   │
│   ├── api/                # FastAPI REST backend
│   │   ├── CLAUDE.md
│   │   ├── server.py       # App setup, CORS, security headers, rate limiting, SPA serving
│   │   ├── auth.py          # Google OAuth verification, session JWT, require_auth/require_owner dependencies
│   │   ├── schemas.py      # Pydantic request/response models
│   │   ├── dependencies.py # DuckDB connection, pipeline lock, rate limiter, require_flag_permission
│   │   └── routes/         # Route modules (auth, status, transactions, review, categories, summary, pipeline, export, accountant_management)
│   │
│   ├── services/           # Shared business logic
│   │   ├── CLAUDE.md
│   │   └── review_service.py  # Review helpers (used by Streamlit + FastAPI)
│   │
│   ├── ingestion/          # PDF parsing
│   │   ├── CLAUDE.md
│   │   ├── pdf_reader.py         # pdfplumber wrapper
│   │   ├── rbc_parser.py         # RBC Visa regex parser
│   │   ├── bmo_parser.py         # BMO Mastercard regex parser
│   │   ├── amex_parser.py        # AMEX parser (stub)
│   │   └── monopoly_adapter.py   # monopoly-core wrapper (bank-agnostic)
│   │
│   ├── staging/
│   │   ├── database.py           # DuckDB init + connection
│   │   └── load_transactions.py  # Orchestrates PDF → raw_transactions
│   │
│   ├── transform/
│   │   ├── normalize.py          # raw → normalized_transactions
│   │   └── dedupe.py             # Duplicate detection + logging
│   │
│   ├── categorization/     # Categorization engine
│   │   ├── CLAUDE.md
│   │   ├── categorizer.py        # Orchestrates layers + deduction rules
│   │   ├── rules_engine.py       # Layer 2: keyword rules
│   │   ├── merchant_memory.py    # Layer 1: fuzzy merchant memory (rapidfuzz)
│   │   └── manual_review.py      # Legacy CLI review
│   │
│   ├── pages/              # Streamlit web pages
│   │   ├── CLAUDE.md
│   │   ├── 1_Transactions.py     # Browse with filters
│   │   ├── 2_Review.py           # Manual review + auto-save rules
│   │   ├── 3_Configuration.py    # Edit rules + deduction rules
│   │   └── 4_Summary.py          # Category totals
│   │
│   ├── output/
│   │   └── csv_export.py         # Writes final CSVs
│   │
│   ├── llm/                # LLM-based transaction evaluator (--use-llm)
│   │   ├── __init__.py
│   │   ├── evaluator.py          # Batch orchestrator: retry, cost tracking, hot-reload
│   │   ├── config.py             # Load llm_config.yaml with defaults
│   │   ├── schemas.py            # Pydantic: TransactionEvaluation, EvaluationBatch
│   │   ├── providers/
│   │   │   ├── __init__.py       # get_provider() factory
│   │   │   ├── base.py           # LLMProvider ABC + LLMResponse dataclass
│   │   │   ├── anthropic_provider.py  # Claude implementation
│   │   │   └── openai_provider.py     # OpenAI implementation
│   │   └── prompts/
│   │       ├── __init__.py
│   │       ├── system_prompt.py  # BC accountant persona + categories + rules context
│   │       └── transaction_prompt.py  # Per-batch transaction formatting
│   │
│   ├── config/
│   │   ├── categories.yaml       # Valid CRA expense categories
│   │   ├── rules.yaml            # Keyword → category rules
│   │   ├── deduction_rules.yaml  # Partial/fixed deduction rules
│   │   ├── llm_config.yaml       # LLM evaluator config (provider, model, batch_size, cost limits)
│   │   ├── config_writer.py      # YAML config read/write helpers + change history
│   │   └── config_history.jsonl  # Append-only log of config changes (gitignored)
│   │
│   ├── tests/              # pytest suite (currently LLM-heavy; core pipeline expansion planned)
│   │
│   ├── state/
│   │   ├── merchant_memory.csv   # Persisted manual review decisions
│   │   └── transactions.duckdb   # DuckDB database
│   │
│   ├── logs/                     # parse_errors.log, duplicates.log, parse_skipped.log
│   └── output/                   # Generated CSV reports
│
└── frontend/               # React TypeScript SPA
    ├── CLAUDE.md
    ├── package.json         # React 19, Vite, TanStack Query, Tailwind CSS 4
    ├── vite.config.ts       # Dev server proxies /api → localhost:8000
    ├── index.html
    └── src/
        ├── App.tsx          # Root with React Router (9 routes, AuthProvider, OwnerOnly guards)
        ├── api/client.ts    # Centralized fetch wrapper (credentials: include, 401 redirect)
        ├── contexts/AuthContext.tsx  # Auth state management (Google sign-in, session, role/permissions)
        ├── hooks/           # TanStack Query hooks + swipe gesture hook
        ├── types/index.ts   # TypeScript interfaces (incl. AccountantUser, role-aware AuthUser)
        ├── components/      # Reusable UI components (incl. ProtectedRoute, OwnerOnly, FlagModal, TransactionDetailModal)
        └── pages/           # Dashboard, Transactions, ReviewQueue, Pipeline, Configuration, Login, AccountantOverview, AccountantExport, AccountantManagement
```

## CLI Commands

All commands run from inside `expense_elt/`:

```bash
python main.py extract       # Parse PDFs → load raw_transactions (--parser monopoly|custom|auto)
python main.py transform     # Normalize + deduplicate
python main.py categorize    # Apply rules + merchant memory (--use-llm for LLM, --dry-run to estimate cost)
python main.py review        # Interactive CLI review (--limit N)
python main.py export        # Write CSVs to output/
python main.py run           # Run all non-interactive steps in sequence
python main.py list          # Browse transactions (--institution, --file, --status, --sort, --limit)
python main.py status        # Show counts at each pipeline stage
python main.py serve         # Start FastAPI + React UI (--host, --port 9743, --reload)
python main.py reset         # Wipe data (--level soft|medium|hard, --yes to skip prompt)
python main.py restore       # List backups; restore <timestamp|index> to recover config files
```

### Reset (`python main.py reset`)
Wipe pipeline data and start fresh. Config files are always backed up to `config/backups/` before deletion.

Three levels (`--level` / `-l`):

| Level | Deletes | Keeps |
|---|---|---|
| `soft` (default) | DB, output CSVs, logs | merchant memory, config history, rules, deduction rules |
| `medium` | soft + merchant memory + config history | rules, deduction rules |
| `hard` | medium + rules.yaml + deduction_rules.yaml | nothing (full factory reset) |

Flags: `--yes` / `-y` to skip confirmation.

### Restore (`python main.py restore`)
Recover config files from a backup created by `reset`.

- **List backups**: `python main.py restore` (no arguments) — shows all backup sets grouped by timestamp, numbered for selection
- **Restore by timestamp**: `python main.py restore 20260311_143045`
- **Restore by index**: `python main.py restore 1` (most recent)

Restores up to 4 files to their original locations: `rules.yaml`, `deduction_rules.yaml`, `merchant_memory.csv`, `config_history.jsonl`. Flags: `--yes` / `-y` to skip confirmation.

## Web Interfaces

### React SPA (primary)
- Start: `python main.py serve` → `http://localhost:9743`
- **Authentication required** — Google OAuth, multi-user (owner + accountant roles)
- Mobile-optimized with swipe gestures for review
- **Owner pages**: Dashboard (KPIs + pie chart), Transactions (filterable table), Review Queue (swipeable cards), Pipeline (run steps), Configuration (rules editor + change history), Accountant Management (CRUD)
- **Accountant pages**: AccountantOverview (read-only dashboard), Transactions (view + flag), AccountantExport (CSV downloads)
- Navigation adapts based on user role; owner-only routes guarded by `OwnerOnly` component
- Communicates via FastAPI REST endpoints at `/api/*`

### Streamlit (legacy, still functional)
- Start: `cd expense_elt && streamlit run app.py`
- Pages: Transactions, Review (with auto-save to rules/deductions + batch apply), Configuration (YAML editor), Summary
- Reads DuckDB directly (no API layer)

## Authentication & Security

### Google OAuth (Multi-User)
All API endpoints (except `/api/auth/*`) require authentication via session cookie. Two roles are supported:

| Role | Who | Access |
|---|---|---|
| `owner` | `ALLOWED_EMAIL` env var | Full access — all routes including review, pipeline, config, accountant management |
| `accountant` | Stored in `authorized_users` DuckDB table | Read-only — status, transactions, categories, summary, export; can flag transactions if granted `can_flag` permission |

Authentication flow:
1. Frontend loads Google Identity Services script
2. User signs in with Google → receives `id_token`
3. Frontend POSTs token to `POST /api/auth/google`
4. Backend verifies token, checks email is owner (`ALLOWED_EMAIL`) or exists in `authorized_users` table
5. Session JWT includes `role` claim (`owner` or `accountant`) and permissions
6. All subsequent API requests carry the cookie automatically

Route protection dependencies:
- `require_auth` — any authenticated user (owner or accountant); also used to inject `claims` for role-based data filtering
- `require_owner` — owner-only routes (review, pipeline, config, accountant management)
- `require_flag_permission` — requires `can_flag` permission (for flagging/batch-flagging transactions)

Privacy: accountants cannot see personal transactions. The `transactions`, `summary`, `status`, and `export` routes filter out `deductible_status = 'personal'` when `claims["role"] == "accountant"`.

### Environment Variables (`expense_elt/.env`)
| Variable | Required | Default | Description |
|---|---|---|---|
| `GOOGLE_CLIENT_ID` | Yes | — | Google OAuth 2.0 Client ID |
| `ALLOWED_EMAIL` | Yes | — | Owner email (full access); accountants managed via API |
| `SESSION_SECRET` | No | auto-generated | HMAC key for session JWTs (set for persistent sessions) |
| `CORS_ORIGINS` | No | `*` | Comma-separated allowed origins |
| `ENV` | No | — | Set to `production` to disable `/docs` and `/openapi.json` |

### Security Hardening
- **CORS** — configurable origins via `CORS_ORIGINS` env var (defaults to `*` for local dev)
- **Session cookies** — HttpOnly, SameSite=Lax (immune to XSS token theft)
- **Security headers** — X-Content-Type-Options, X-Frame-Options, Referrer-Policy, Permissions-Policy, CSP
- **Rate limiting** — 60 req/min global, 10 req/min on auth endpoints (via `slowapi`)
- **Path traversal protection** — SPA catch-all validates resolved path stays within `frontend/dist/`
- **Input validation** — max_length constraints on string fields, ge=0 on amounts
- **Error sanitization** — pipeline errors strip internal file paths
- **Docs disabled in production** — `/docs` and `/openapi.json` hidden when `ENV=production`

## Configuration

### `config/rules.yaml`
Keyword → category mapping. Case-insensitive substring matches on `merchant_normalized`.

### `config/deduction_rules.yaml`
Handles partial deductions. Supports four methods:
- `fixed_monthly` — caps deductible at a fixed dollar amount per month
- `percentage` — applies a % to the original amount
- `full` — fully deductible
- `personal` — not deductible (deductible_amount = 0)

Rules can have date bounds (`start_date`, `end_date`). Example: Rogers phone capped at $97/month from 2024-04-01.

### `config/llm_config.yaml`
LLM evaluator configuration. All fields have sane defaults — file is optional.

| Field | Default | Description |
|---|---|---|
| `provider` | `anthropic` | LLM provider: `anthropic` or `openai` |
| `model` | `claude-sonnet-4-20250514` | Model identifier |
| `batch_size` | `10` | Transactions per LLM call |
| `max_retries` | `3` | Retries on rate limit / timeout |
| `initial_backoff_seconds` | `2.0` | Exponential backoff base |
| `max_cost_per_run` | `5.00` | Cost guard — abort if exceeded (USD) |
| `temperature` | `0.1` | Low for deterministic output |

### `config/categories.yaml`
Canonical CRA category strings. Do not rename — they must match CRA T2125 form exactly.

### Config Change History
All config modifications are logged to `config/config_history.jsonl` (append-only JSONL). Each entry records timestamp, config file, action (`add`/`update`/`delete`/`bulk_save`), detail, and source (`api`, `streamlit`, `streamlit_review`, `api_review`). View history via:
- **API**: `GET /api/config/history?limit=50&config_file=rules.yaml`
- **Streamlit**: Configuration page → "Change History" tab

## Expense Categories (CRA)

Exactly as required by CRA T2125:
- Advertising
- Meals & Entertainment
- Insurance
- Business tax, fees, licences
- Office expenses
- Supplies
- Legal, accounting, and other professional fees
- Management and administration fees
- Rent
- Maintenance and repairs
- Salaries, wages, and benefits
- Telephone and utilties *(keep this spelling — matches CRA form)*
- Travel
- Delivery, freight, and express
- Motor vehcie expenses *(keep this spelling — matches CRA form)*
- Other expenses

## Database

DuckDB file at `expense_elt/state/transactions.duckdb` (created on first run).

Key tables:
- `raw_transactions` — unmodified extracted rows
- `normalized_transactions` — cleaned, deduplicated records
- `categorized_transactions` — final categorized records with per-transaction deductible amounts
- `authorized_users` — accountant users with email, name, role, permissions (e.g., `can_flag`), managed by owner via API

## Dependencies

### Python (`expense_elt/requirements.txt`)
```
pdfplumber>=0.11        # PDF text extraction
duckdb>=1.0             # Local database
typer>=0.12             # CLI framework
rapidfuzz>=3.0          # Fuzzy merchant matching
pyyaml>=6.0             # Config files
rich>=13.0              # Terminal formatting
python-dateutil>=2.9    # Date parsing
streamlit>=1.35         # Streamlit web pages
plotly>=5.0             # Charts
pandas>=2.0             # DataFrames
monopoly-core>=0.9      # Bank-agnostic PDF parsing
fastapi>=0.115          # REST API backend
uvicorn[standard]>=0.32 # ASGI server
anthropic>=0.40         # Claude LLM provider (lazy import, only needed with --use-llm)
openai>=1.50            # OpenAI LLM provider (lazy import, only needed with --use-llm)
google-auth>=2.0        # Google OAuth token verification
PyJWT>=2.0              # Session JWT creation/verification
slowapi>=0.1.9          # Rate limiting
python-dotenv>=1.0      # .env file loading
```

### Frontend (`frontend/package.json`)
```
react 19               # UI framework
react-router 7         # Client-side routing
@tanstack/react-query   # Server state management
tailwindcss 4           # Styling
vite                    # Build tool + dev server
typescript              # Type safety
```

Install: `pip install -r requirements.txt` and `cd frontend && npm install`

## Extending the System

- **Add a new bank**: create parser in `ingestion/`, register in `staging/load_transactions.py`. Or use monopoly-core (auto-detects bank)
- **Add a new keyword rule**: edit `config/rules.yaml`
- **Add a partial deduction rule**: edit `config/deduction_rules.yaml`
- **Fix a miscategorized merchant**: use any review interface, or edit `state/merchant_memory.csv` directly
- **Add a new API endpoint**: add route module in `api/routes/`, register in `api/server.py`
- **Add a new React page**: add component in `frontend/src/pages/`, register in `App.tsx`

## Workflow: Commit & Update Docs

After completing any code change (feature, bug fix, refactor, iteration):

1. **Commit** — Stage and commit all changed files with a descriptive message.
2. **Update docs** — Review whether any CLAUDE.md files (root or sub-component) need updating. Only update docs that are actually impacted by the changes (e.g., new files, new commands, changed architecture, new config options, new dependencies). Skip this step if the changes don't affect documented behavior.

Do not do this for non-code work (answering questions, reading files, research).

---

## Important Notes

- Never discard raw extracted text — all data traces back to source PDF and page number
- Manual review decisions always win over rule-based categorization on rerun
- The DB is idempotent — re-running `extract` skips already-loaded rows
- Application logs go to `logs/app.log` (rotating, 5 MB, 3 backups) — captures runtime errors, LLM batch progress, cost tracking, pipeline failures
- Parse-specific logs go to `logs/parse_errors.log`, `logs/duplicates.log`, and `logs/parse_skipped.log`
- Place bank statement PDFs in `expense_elt/data/` (`RBC_Visa/`, `BMO_Mastercard/`, `Amex/`)
- FastAPI uses a threading lock (`pipeline_lock`) to serialize DuckDB writes
- Config/review API endpoints reject writes (HTTP 409) while a pipeline step is running (`require_pipeline_idle` dependency)
- LLM categorization supports SSE progress streaming via `GET /api/pipeline/llm-categorize/stream` (batch-by-batch progress, cost, tokens)
- React SPA is built to `frontend/dist/` and served as static files by FastAPI
- All API endpoints require Google OAuth session cookie (except `/api/auth/*`); owner-only routes additionally enforce `require_owner`
- Create a `.env` file in `expense_elt/` with `GOOGLE_CLIENT_ID` before running the web UI (see `.env.example`)

