# Contributing

## Development Setup

### Prerequisites

- Python 3.11+
- Node.js 20+
- `libpoppler-cpp-dev` and `pkg-config` (Linux)

### Backend

```bash
cd expense_elt
python -m pip install -r requirements-dev.txt
python -m pytest -q
```

### Frontend

```bash
cd frontend
npm ci
npm run typecheck
npm run build
```

See [DEVELOPMENT.md](DEVELOPMENT.md) for CI parity details and ngrok hosting setup.

## Running Tests

```bash
# Python tests
cd expense_elt && python -m pytest -q

# Frontend typecheck + build
cd frontend && npm run typecheck && npm run build
```

## How to Extend

### Add a new bank parser

1. Create a parser in `expense_elt/ingestion/` (see `rbc_parser.py` as a template)
2. Register it in `expense_elt/staging/load_transactions.py`
3. Or use monopoly-core which auto-detects many bank formats

### Add a keyword rule

Edit `expense_elt/config/rules.yaml`:

```yaml
- keywords:
  - your merchant keyword
  category: Office expenses
  confidence: 0.9
```

### Add a deduction rule

Edit `expense_elt/config/deduction_rules.yaml`:

```yaml
- name: Description
  merchant_pattern: keyword
  deductible_status: partial
  method: percentage
  percentage: 0.50
  category: Telephone and utilties
```

### Add an API endpoint

1. Create a route module in `expense_elt/api/routes/`
2. Register the router in `expense_elt/api/server.py`

### Add a React page

1. Create a component in `frontend/src/pages/`
2. Add the route in `frontend/src/App.tsx`

## Pull Requests

- Keep PRs focused on a single change
- Ensure `python -m pytest -q` passes
- Ensure `npm run typecheck && npm run build` passes
- Write descriptive commit messages
