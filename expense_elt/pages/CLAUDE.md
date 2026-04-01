# CLAUDE.md — Streamlit Web Pages

## Overview

Streamlit-based web dashboard for browsing, reviewing, and configuring the expense pipeline. Launched via `streamlit run app.py` from `expense_elt/`. This is the legacy UI — the React SPA is the primary interface going forward.

## Structure

```
pages/
├── 1_Transactions.py     # Browse all transactions with filters
├── 2_Review.py           # Manual review with auto-save + batch apply
├── 3_Configuration.py    # Edit rules.yaml + deduction_rules.yaml
└── 4_Summary.py          # Category totals + breakdown charts
```

## Pages

### 1_Transactions
- Filterable table of all normalized + categorized transactions
- Filters: institution, review status, search
- Reads from DuckDB directly

### 2_Review
- Shows transactions where `review_required = TRUE`
- For each transaction: select category, deductible status, amount override, notes
- **Auto-save features**:
  - Saves decision to `state/merchant_memory.csv`
  - Optionally appends a keyword rule to `config/rules.yaml`
  - Optionally appends a deduction rule to `config/deduction_rules.yaml`
- **Batch apply**: applies the same decision to all transactions from the same `merchant_normalized`
- Uses `services/review_service.py` for business logic

### 3_Configuration
- Tabbed interface for editing:
  - `config/rules.yaml` (keyword → category rules)
  - `config/deduction_rules.yaml` (partial deduction rules)
- Uses `config/config_writer.py` for safe YAML read/write

### 4_Summary
- Category totals with `SUM(deductible_amount)` grouped by category
- Institution breakdown
- Uses plotly for charts

## Entry Point

`app.py` at the `expense_elt/` root is the Streamlit main page. Pages are auto-discovered from the `pages/` directory by Streamlit's multipage app convention (filenames prefixed with numbers).
