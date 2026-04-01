"""
Review page — manual labeling of transactions flagged for review.

On save:
  1. Updates categorized_transactions in DB
  2. Saves decision to merchant_memory.csv
  3. Optionally appends a keyword rule to config/rules.yaml
  4. Optionally appends a deduction rule to config/deduction_rules.yaml
  5. Optionally batch-applies the same decision to all similar transactions
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import streamlit as st

from categorization.merchant_memory import get_memory
from config.config_writer import (
    append_deduction_rule,
    append_keyword_rule,
    load_categories,
)
from services.review_service import (
    load_review_queue,
    save_single_review,
    batch_apply,
    count_similar,
    suggest_keyword,
)

st.set_page_config(page_title="Review", layout="wide")
st.title("Manual Review")


# ---------------------------------------------------------------------------
# Main page
# ---------------------------------------------------------------------------

try:
    categories = load_categories()
    queue = load_review_queue()
    total = len(queue)

    if total == 0:
        st.success("All caught up — nothing left to review.")
        if st.button("Refresh"):
            st.rerun()
        st.stop()

    # Session state
    if "review_idx" not in st.session_state:
        st.session_state.review_idx = 0

    idx = min(st.session_state.review_idx, total - 1)
    txn = queue[idx]
    original_amount = float(txn["original_amount"] or 0)
    suggested_category = txn["category"] or categories[0]
    confidence = float(txn["confidence"] or 0)
    merchant_norm = txn["merchant_normalized"] or ""
    similar_count = count_similar(merchant_norm, queue)

    # --- Progress ---
    st.progress(idx / total, text=f"Transaction {idx + 1} of {total} remaining")

    # --- Transaction card ---
    with st.container(border=True):
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Date", str(txn["transaction_date"]))
        c2.metric("Institution", txn["institution"] or "—")
        c3.metric("Amount", f"${original_amount:.2f}")
        c4.metric("Confidence", f"{confidence:.0%}" if confidence else "—")

        st.markdown(f"**Merchant:** `{txn['merchant_raw']}`")
        if merchant_norm and merchant_norm != txn["merchant_raw"]:
            st.markdown(f"**Normalized:** `{merchant_norm}`")
        if txn["description_raw"] and txn["description_raw"] != txn["merchant_raw"]:
            st.markdown(f"**Description:** {txn['description_raw']}")
        if txn["rule_applied"]:
            st.caption(f"Suggested by rule: `{txn['rule_applied']}` · Suggested category: {suggested_category}")
        elif suggested_category:
            st.caption(f"Suggested category: {suggested_category}")

        if similar_count > 0:
            st.info(f"{similar_count} other transaction(s) from the same merchant are also pending review.")

    # --- Review form ---
    with st.form(key=f"form_{txn['transaction_id']}"):
        category_idx = categories.index(suggested_category) if suggested_category in categories else 0
        chosen_category = st.selectbox("Category", categories, index=category_idx)

        col_status, col_amount = st.columns(2)

        with col_status:
            chosen_status = st.radio(
                "Deductible status",
                options=["full", "partial", "personal"],
                index=0,
                horizontal=True,
            )

        with col_amount:
            if chosen_status == "partial":
                deductible_amount = st.number_input(
                    "Deductible amount",
                    min_value=0.0,
                    max_value=float(original_amount),
                    value=float(original_amount),
                    step=0.01,
                    format="%.2f",
                )
            elif chosen_status == "full":
                deductible_amount = original_amount
                st.metric("Deductible amount", f"${original_amount:.2f}")
            else:
                deductible_amount = 0.0
                st.metric("Deductible amount", "$0.00")

        notes = st.text_input("Notes (optional)", value=txn.get("notes") or "")

        st.divider()

        # --- Auto-config options ---
        st.markdown("**Auto-save to configuration**")

        col_kw, col_ded = st.columns(2)

        with col_kw:
            add_keyword = st.checkbox("Add keyword rule", value=False, help="Append a keyword rule to rules.yaml so future transactions auto-categorize")
            default_kw = suggest_keyword(merchant_norm)
            keyword_val = st.text_input("Keyword", value=default_kw, disabled=not add_keyword)
            keyword_conf = st.slider("Rule confidence", 0.5, 1.0, 0.90, 0.05, disabled=not add_keyword)

        with col_ded:
            add_deduction = st.checkbox(
                "Add deduction rule",
                value=False,
                disabled=(chosen_status != "partial"),
                help="Append a deduction rule to deduction_rules.yaml for this merchant",
            )
            ded_method = st.selectbox(
                "Method",
                ["fixed_monthly", "percentage"],
                disabled=not add_deduction,
            )
            if ded_method == "fixed_monthly":
                ded_amount = st.number_input("Fixed amount ($/month)", min_value=0.0, value=deductible_amount, step=1.0, format="%.2f", disabled=not add_deduction)
                ded_pct = None
            else:
                ded_pct = st.slider("Percentage", 0, 100, 50, 5, disabled=not add_deduction)
                ded_amount = None
            ded_start = st.text_input("Start date (YYYY-MM-DD, optional)", value="", disabled=not add_deduction)

        st.divider()

        # --- Apply to similar ---
        apply_all = st.checkbox(
            f"Apply to all {similar_count + 1} transactions from this merchant",
            value=False,
            disabled=(similar_count == 0),
            help="Batch-apply the same category and deductible status to all pending transactions from this merchant",
        )

        # --- Buttons ---
        col_save, col_skip = st.columns([3, 1])
        submitted = col_save.form_submit_button("Save & Next", type="primary", use_container_width=True)
        skipped = col_skip.form_submit_button("Skip", use_container_width=True)

    # Navigation (outside form)
    col_prev, _, col_next = st.columns([1, 3, 1])
    if col_prev.button("Previous", disabled=(idx == 0)):
        st.session_state.review_idx = max(0, idx - 1)
        st.rerun()
    if col_next.button("Next", disabled=(idx >= total - 1)):
        st.session_state.review_idx = min(total - 1, idx + 1)
        st.rerun()

    # --- Handle form submission ---
    if submitted:
        if apply_all and merchant_norm:
            applied = batch_apply(merchant_norm, chosen_category, chosen_status, notes)
            # Also save to merchant memory
            memory = get_memory()
            memory.save_decision(
                merchant_normalized=merchant_norm,
                category=chosen_category,
                deductible_status=chosen_status,
                confidence=1.0,
                decision_source="manual_web_batch",
            )
            st.toast(f"Applied to {applied} transaction(s)")
        else:
            save_single_review(
                transaction_id=txn["transaction_id"],
                category=chosen_category,
                deductible_status=chosen_status,
                deductible_amount=deductible_amount,
                notes=notes,
                merchant_normalized=merchant_norm,
                merchant_raw=txn["merchant_raw"],
            )

        # Auto-save keyword rule
        if add_keyword and keyword_val.strip():
            append_keyword_rule(keyword_val.strip(), chosen_category, keyword_conf, source="streamlit_review")
            st.toast(f"Keyword rule added: '{keyword_val.strip()}' -> {chosen_category}")

        # Auto-save deduction rule
        if add_deduction and chosen_status == "partial":
            rule_name = f"{merchant_norm[:30]} partial deduction"
            append_deduction_rule(
                name=rule_name,
                merchant_pattern=suggest_keyword(merchant_norm),
                deductible_status="partial",
                method=ded_method,
                amount=ded_amount,
                percentage=(ded_pct / 100.0) if ded_pct is not None else None,
                category=chosen_category,
                start_date=ded_start.strip() if ded_start.strip() else None,
                notes=f"Created during manual review",
                source="streamlit_review",
            )
            st.toast(f"Deduction rule added for '{merchant_norm[:30]}'")

        st.rerun()

    if skipped:
        st.session_state.review_idx = min(total - 1, idx + 1)
        st.rerun()

except Exception as e:
    st.error(f"Error: {e}")
    import traceback
    st.code(traceback.format_exc())
