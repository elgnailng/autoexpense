# CLAUDE.md — React Frontend

## Overview

Modern React TypeScript SPA for expense review and pipeline management. Mobile-optimized with gesture-driven card review. Built with Vite, served by the FastAPI backend at `http://localhost:9743`.

## Tech Stack

| Tool | Purpose |
|---|---|
| React 19 | UI framework |
| TypeScript | Type safety |
| Vite | Build tool + dev server |
| React Router 7 | Client-side routing |
| TanStack React Query | Server state, caching, auto-refetch |
| Tailwind CSS 4 | Utility-first styling |

## Structure

```
frontend/
├── package.json
├── vite.config.ts       # Dev server proxies /api → http://localhost:8000
├── tsconfig.json
├── index.html           # HTML entry point
├── dist/                # Production build (served by FastAPI as static files)
│
└── src/
    ├── main.tsx         # React entry point
    ├── App.tsx          # Root component — React Router with 9 routes, AuthProvider, OwnerOnly guards
    ├── index.css        # Global Tailwind imports
    │
    ├── api/
    │   └── client.ts            # Centralized fetch wrapper (credentials: include, 401 redirect)
    │
    ├── contexts/
    │   └── AuthContext.tsx       # Auth state management (Google sign-in, session check, role/permissions)
    │
    ├── hooks/
    │   ├── useApi.ts            # TanStack Query hooks for all API endpoints
    │   ├── useLLMProgress.ts    # SSE hook for LLM categorization progress streaming
    │   └── useSwipe.ts          # Touch gesture detection (swipe left/right/up/down)
    │
    ├── types/
    │   └── index.ts             # TypeScript interfaces (Transaction, ReviewDecision, PipelineStatus, AccountantUser, etc.)
    │
    ├── components/
    │   ├── Layout.tsx           # Sidebar navigation + user info + logout + outlet (role-aware nav)
    │   ├── ProtectedRoute.tsx   # Route guard — redirects to /login if not authenticated
    │   ├── OwnerOnly.tsx        # Route guard — restricts child routes to owner role only
    │   ├── StatusBar.tsx        # Top status indicator
    │   ├── TransactionCard.tsx  # Review card with swipe overlay (shows confidence, suggested category)
    │   ├── SwipeContainer.tsx   # Swipeable card stack (gesture-driven review)
    │   ├── TransactionTable.tsx # Tabular transaction view (supports selectable mode with checkboxes)
    │   ├── BatchActionBar.tsx   # Floating bar for batch update (owner) / batch flag (accountant) actions
    │   ├── TransactionDetailModal.tsx  # Transaction detail view (Edit for owner, Flag for accountant)
    │   ├── FlagModal.tsx        # Modal for accountants to flag transactions for review
    │   ├── AddTransactionModal.tsx  # Modal for manually adding transactions (cash, transfers)
    │   ├── CategorySelect.tsx   # Category dropdown
    │   ├── LLMProgressBar.tsx   # Real-time progress bar for LLM categorization (SSE)
    │   ├── PartialAmountModal.tsx  # Modal for entering partial deductible amount
    │   └── PipelineControls.tsx # Buttons to trigger pipeline steps + SSE progress for LLM
    │
    └── pages/
        ├── Login.tsx            # Google sign-in page (unauthenticated)
        ├── Dashboard.tsx        # KPI cards + pie chart (owner); delegates to AccountantOverview for accountants
        ├── Transactions.tsx     # Transaction browser with search + filters
        ├── ReviewQueue.tsx      # Swipeable card-based review (owner only)
        ├── Pipeline.tsx         # Run pipeline steps via API (owner only)
        ├── Configuration.tsx    # Edit keyword/deduction rules + change history (owner only)
        ├── AccountantOverview.tsx    # Read-only dashboard for accountant role
        ├── AccountantExport.tsx     # CSV download page for accountants
        └── AccountantManagement.tsx # CRUD interface for managing accountant users (owner only)
```

## Routes

| Path | Page | Auth | Description |
|---|---|---|---|
| `/login` | Login | No | Google sign-in page |
| `/` | Dashboard | Any auth | KPI cards, category breakdown (owner); AccountantOverview (accountant) |
| `/transactions` | Transactions | Any auth | Filterable, searchable transaction table |
| `/review` | ReviewQueue | Owner | Swipe-based mobile review (main feature) |
| `/pipeline` | Pipeline | Owner | Trigger and monitor pipeline steps |
| `/config` | Configuration | Owner | Edit keyword/deduction rules, view categories, change history |
| `/accountants` | AccountantManagement | Owner | Add, edit, remove accountant users |
| `/export` | AccountantExport | Any auth | Download CSV exports |

## Review Gestures (Mobile)

The ReviewQueue page uses swipe gestures on `TransactionCard` components:
- **Swipe right** → Mark as `full` (business expense)
- **Swipe left** → Mark as `personal`
- **Swipe up** → Mark as `partial` (opens PartialAmountModal for amount entry)
- **Swipe down** → Skip / needs review

## Development

```bash
cd frontend
npm install        # Install dependencies
npm run dev        # Start Vite dev server (proxies /api to localhost:8000)
npm run build      # Build to dist/ (served by FastAPI in production)
```

The Vite dev server (`npm run dev`) proxies `/api` requests to `http://localhost:8000`, so run `python main.py serve --port 8000` alongside for development.

## Production

The FastAPI server (`python main.py serve`) serves the built `frontend/dist/` as static files. No separate frontend server needed. Build with `cd frontend && npm run build` before deploying.
