# CLAUDE.md — Services Layer

## Overview

Shared business logic extracted from UI code so it can be reused across Streamlit pages and FastAPI routes. Avoids duplicating review/save logic in multiple places.

## Structure

```
services/
└── review_service.py    # Review queue helpers
```

## review_service.py

Functions for manual review operations:

| Function | Purpose |
|---|---|
| `load_review_queue()` | Fetch all transactions where `review_required = TRUE`, joined with normalized data |
| `save_single_review()` | Update `categorized_transactions` + append to `merchant_memory.csv` |
| `batch_apply()` | Apply a review decision to all transactions from the same `merchant_normalized` |
| `batch_update_by_ids()` | Apply a review decision to specific transactions by ID + save to merchant memory |
| `count_similar()` | Count how many review-pending transactions share the same merchant |
| `suggest_keyword()` | Extract a plausible keyword from `merchant_normalized` for rules.yaml |

## Usage

Both the Streamlit Review page (`pages/2_Review.py`) and the FastAPI review routes (`api/routes/review.py`) call these functions instead of implementing review logic independently.
