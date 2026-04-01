# CLAUDE.md — FastAPI REST Backend

## Overview

FastAPI application serving the React SPA and exposing all pipeline operations as REST endpoints. Runs on port 9743 via `python main.py serve`. All API endpoints require Google OAuth authentication except `/api/auth/*`. Supports two roles: **owner** (full access) and **accountant** (read-only + optional flag permission).

## Structure

```
api/
├── server.py         # FastAPI app setup, CORS, security headers, rate limiting, SPA serving
├── auth.py           # Google OAuth token verification, session JWT, require_auth/require_owner dependencies
├── schemas.py        # Pydantic models for request/response validation
├── dependencies.py   # DuckDB connection pool, pipeline_lock, rate limiter, require_flag_permission
└── routes/
    ├── auth.py           # POST /api/auth/google, GET /api/auth/me, POST /api/auth/logout, GET /api/auth/client-id
    ├── status.py         # GET /api/status — pipeline counts + institution breakdown
    ├── transactions.py   # GET /api/transactions, GET /api/transactions/{id}, POST /api/transactions/{id}/flag
    ├── review.py         # GET /api/review-queue, POST /api/transactions/{id}/review, POST /api/transactions/batch-review
    ├── categories.py     # GET /api/categories — CRA category list from categories.yaml
    ├── summary.py        # GET /api/summary — category totals + institution breakdown
    ├── pipeline.py       # POST /api/pipeline/{step} — trigger extract/transform/categorize/export/run
    ├── config.py         # GET/POST/PUT/DELETE /api/config/* — keyword/deduction rules + history
    ├── export.py         # GET /api/export/{file_type} — CSV file download (any auth user)
    └── accountant_management.py  # GET/POST/PUT/DELETE /api/accountants — accountant CRUD (owner only)
```

## Key Design Decisions

- **Multi-user Google OAuth** — `require_auth` dependency on all routers except auth; verifies session JWT from HttpOnly cookie. JWT includes `role` claim (`owner` or `accountant`) and permissions
- **Role-based route protection** — `require_owner` dependency restricts review, pipeline, config, and accountant management routes to the owner. `require_flag_permission` gates transaction flagging on the `can_flag` permission
- **Personal expense privacy** — accountants cannot see personal transactions. Routes (`transactions`, `summary`, `status`, `export`) inject `claims` via `Depends(require_auth)` and filter out `deductible_status = 'personal'` for accountant role
- **Accountant management** — owner can CRUD accountant users via `/api/accountants`; accountant records stored in `authorized_users` DuckDB table
- **Session JWT** — HS256-signed, 24h expiry, stored in HttpOnly/SameSite=Lax cookie (immune to XSS)
- **CORS configurable** — `CORS_ORIGINS` env var; defaults to `*` for local dev
- **Security headers** — nosniff, DENY frame, strict referrer, permissions policy, CSP allowing Google GIS
- **Rate limiting** — `slowapi` with 60/min global default, 10/min on auth endpoints
- **Path traversal protection** — SPA catch-all resolves paths and validates they stay within `frontend/dist/`
- **Error sanitization** — pipeline error messages strip internal file paths
- **SPA catch-all** — any non-`/api` route serves `frontend/dist/index.html` for client-side routing
- **Pipeline lock** — `dependencies.pipeline_lock` (threading.Lock) serializes all DuckDB write operations to prevent concurrent writer conflicts
- **Config lock during pipeline** — `require_pipeline_idle()` dependency rejects config/review writes (409) when pipeline is running
- **`get_db()` dependency** — yields a DuckDB connection per request, closes on completion
- **SSE progress streaming** — `/api/pipeline/llm-categorize/stream` uses Server-Sent Events to stream batch-by-batch progress during LLM categorization
- **Docs disabled in production** — `/docs` and `/openapi.json` hidden when `ENV=production`

## API Routes

| Method | Path | Auth | Description |
|---|---|---|---|
| POST | `/api/auth/google` | No | Verify Google id_token, set session cookie |
| GET | `/api/auth/me` | No | Return current user from session cookie |
| POST | `/api/auth/logout` | No | Clear session cookie |
| GET | `/api/auth/client-id` | No | Return Google Client ID for frontend |
| GET | `/api/status` | Any auth | Pipeline counts per stage + per institution |
| GET | `/api/transactions` | Any auth | List transactions with filters |
| GET | `/api/transactions/{id}` | Any auth | Single transaction detail |
| POST | `/api/transactions` | Any auth | Manually create a transaction (cash, transfers, etc.) |
| POST | `/api/transactions/{id}/flag` | Flag perm | Flag a transaction for review (requires `can_flag` permission) |
| POST | `/api/transactions/batch-flag` | Flag perm | Batch-flag multiple transactions for review |
| GET | `/api/review-queue` | Owner | Transactions where `review_required = TRUE` |
| POST | `/api/transactions/{id}/review` | Owner | Submit review decision for one transaction |
| POST | `/api/transactions/batch-review` | Owner | Batch-apply a decision to all matching merchants |
| POST | `/api/transactions/batch-update` | Owner | Batch-update category/status for specific transaction IDs |
| GET | `/api/categories` | Any auth | List of valid CRA categories |
| GET | `/api/summary` | Any auth | Deductible amounts grouped by category |
| GET | `/api/export/{file_type}` | Any auth | Download CSV file (business_expenses, all_transactions, etc.) |
| POST | `/api/pipeline/{step}` | Owner | Run a pipeline step |
| POST | `/api/pipeline/llm-categorize` | Owner | LLM categorization (query: `provider`, `dry_run`) |
| GET | `/api/pipeline/llm-categorize/stream` | Owner | SSE stream of LLM categorization progress |
| GET | `/api/config/history` | Owner | Config change history |
| GET | `/api/accountants` | Owner | List all accountant users |
| POST | `/api/accountants` | Owner | Add a new accountant user |
| PUT | `/api/accountants/{email}` | Owner | Update an accountant user |
| DELETE | `/api/accountants/{email}` | Owner | Remove an accountant user |

## Static File Serving

`server.py` mounts the React build directory (`frontend/dist/`) at root. The catch-all route validates the resolved path stays within the dist directory (path traversal protection) and returns `index.html` for any non-file path, enabling React Router's client-side navigation.
