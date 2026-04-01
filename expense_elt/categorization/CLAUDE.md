# CLAUDE.md — Categorization Engine

## Overview

Three-layer categorization system that assigns CRA expense categories and computes deductible amounts for each transaction.

## Structure

```
categorization/
├── categorizer.py      # Public facade: stable imports + categorize_all()
├── core.py             # Shared transaction date parsing helper
├── deduction_rules.py  # Deduction rule loading + apply_deduction_rule()
├── workflow.py         # Rule/LLM workflows + categorized_transactions writes
├── merchant_memory.py  # Layer 1: fuzzy merchant memory (rapidfuzz)
├── rules_engine.py     # Layer 2: keyword rules from rules.yaml
└── manual_review.py    # Legacy CLI review (Layer 3 fallback triggers this)
```

## Categorization Layers

Processed in order for each `normalized_transaction` not yet in `categorized_transactions`:

### Layer 1 — Merchant Memory (`state/merchant_memory.csv`)
- Checked first — manual decisions always win over rules
- Exact match on `merchant_normalized` → confidence 0.98
- Fuzzy match via `rapidfuzz` → confidence 0.75 (triggers review if < 0.85)

### Layer 2 — LLM Evaluator (when `--use-llm`)
- Replaces Layer 2b + 3 for transactions not matched by merchant memory
- BC accountant persona via Claude or OpenAI (`llm/` module)
- Returns category, expensable_pct, confidence, reasoning, review_flag
- Config deduction rules still override LLM percentages when matched
- Batch processing with retry, cost tracking, and rules hot-reload

### Layer 2b — Rules Engine (`config/rules.yaml`, when no `--use-llm`)
- Case-insensitive substring match on `merchant_normalized`
- Each rule has a configurable confidence (0.50–0.90)
- Triggers review if confidence < 0.70

### Layer 3 — Fallback (when no `--use-llm`)
- No match found → category: `Other expenses`, confidence: 0.0, `review_required = True`

## Deduction Rules

Applied per transaction after categorization by `deduction_rules.py`:

| Method | Behavior |
|---|---|
| `fixed_monthly` | `deductible_amount = min(original_amount, cap)` |
| `percentage` | `deductible_amount = original_amount × pct` |
| `full` | `deductible_amount = original_amount` |
| `personal` | `deductible_amount = 0` |

- Rules can be date-bounded (`start_date`, `end_date`)
- Credits (negative amounts) always return `deductible_status=personal`, `deductible_amount=0`
- `apply_deduction_rule()` returns `(deductible_status, deductible_amount, rule_name)`

## Key Entry Point

`categorize_all(verbose=False, use_llm=False, llm_provider="anthropic", dry_run=False)` in `categorizer.py`:
- Preserves the public API expected by CLI, FastAPI routes, and tests
- Delegates non-LLM and LLM runs to `workflow.py`
- Keeps `categorize_transaction()` in `categorizer.py` so tests can still patch `apply_rules` and `get_memory`
- Applies deduction rules per transaction (config caps override LLM percentages)
- Inserts results into `categorized_transactions`
- Returns stats dict with counts (+ cost/token stats when LLM used)
