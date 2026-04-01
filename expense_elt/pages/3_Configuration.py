"""
Configuration page — edit keyword rules, deduction rules, and view categories.

Keyword rules: editable data table with save button.
Deduction rules: editable form per rule with add/delete support.
Categories: read-only reference list.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import streamlit as st
import pandas as pd
import yaml

from config.config_writer import (
    load_categories,
    load_config_history,
    load_deduction_rules,
    load_keyword_rules,
    record_config_change,
    remove_deduction_rule,
    save_deduction_rules,
    save_keyword_rules,
)

st.set_page_config(page_title="Configuration", layout="wide")
st.title("Configuration")

_CONFIG_DIR = Path(__file__).parent.parent / "config"

categories = load_categories()

tab1, tab2, tab3, tab4 = st.tabs(["Keyword Rules", "Deduction Rules", "Categories", "Change History"])

# ---------------------------------------------------------------------------
# Tab 1: Keyword Rules
# ---------------------------------------------------------------------------
with tab1:
    st.subheader("Keyword Rules")
    st.caption(
        "Case-insensitive substring match against `merchant_normalized`. "
        "Changes take effect on next `python main.py categorize` run."
    )

    try:
        rules = load_keyword_rules()

        rows = [
            {
                "keywords": ", ".join(rule.get("keywords", [])),
                "category": rule.get("category", ""),
                "confidence": rule.get("confidence", 0.9),
            }
            for rule in rules
        ]
        df_rules = pd.DataFrame(rows)

        edited_df = st.data_editor(
            df_rules,
            use_container_width=True,
            num_rows="dynamic",
            column_config={
                "keywords": st.column_config.TextColumn(
                    "Keywords (comma-separated)", width="large"
                ),
                "category": st.column_config.SelectboxColumn(
                    "Category",
                    options=categories,
                    width="medium",
                ),
                "confidence": st.column_config.NumberColumn(
                    "Confidence",
                    min_value=0.0,
                    max_value=1.0,
                    step=0.05,
                    format="%.2f",
                ),
            },
        )

        if st.button("Save keyword rules", type="primary", key="save_kw"):
            new_rules = []
            for _, row in edited_df.iterrows():
                kw = str(row["keywords"]).strip()
                if kw:
                    keywords = [k.strip() for k in kw.split(",") if k.strip()]
                    cat = str(row["category"]).strip()
                    if cat and keywords:
                        new_rules.append(
                            {
                                "keywords": keywords,
                                "category": cat,
                                "confidence": float(row["confidence"]),
                            }
                        )
            save_keyword_rules(new_rules)
            record_config_change("rules.yaml", "bulk_save", f"Saved {len(new_rules)} keyword rules", "streamlit")
            st.success(f"Saved {len(new_rules)} keyword rules.")

    except Exception as e:
        st.error(f"Error loading rules.yaml: {e}")

# ---------------------------------------------------------------------------
# Tab 2: Deduction Rules
# ---------------------------------------------------------------------------
with tab2:
    st.subheader("Deduction Rules")
    st.caption(
        "Partial/fixed deduction rules applied per merchant during categorization. "
        "Changes take effect on next `python main.py categorize` run."
    )

    try:
        ded_rules = load_deduction_rules()

        # --- Existing rules (editable) ---
        if ded_rules:
            rules_to_delete = []

            for i, rule in enumerate(ded_rules):
                method = rule.get("method", "full")
                if method == "fixed_monthly":
                    detail = f"${rule.get('amount', 0):.2f}/month"
                elif method == "percentage":
                    detail = f"{rule.get('percentage', 0) * 100:.0f}%"
                else:
                    detail = method

                with st.expander(
                    f"{rule.get('name', f'Rule {i+1}')} — "
                    f"`{rule.get('merchant_pattern', '')}` ({detail})",
                    expanded=False,
                ):
                    col_l, col_r = st.columns(2)

                    with col_l:
                        name = st.text_input("Name", value=rule.get("name", ""), key=f"dn_{i}")
                        pattern = st.text_input("Merchant pattern", value=rule.get("merchant_pattern", ""), key=f"dp_{i}")
                        status = st.selectbox(
                            "Deductible status",
                            ["full", "partial", "personal"],
                            index=["full", "partial", "personal"].index(rule.get("deductible_status", "partial")),
                            key=f"ds_{i}",
                        )
                        cat = st.selectbox(
                            "Category (optional)",
                            [""] + categories,
                            index=(categories.index(rule["category"]) + 1) if rule.get("category") in categories else 0,
                            key=f"dc_{i}",
                        )

                    with col_r:
                        method_val = st.selectbox(
                            "Method",
                            ["fixed_monthly", "percentage", "full"],
                            index=["fixed_monthly", "percentage", "full"].index(method) if method in ["fixed_monthly", "percentage", "full"] else 0,
                            key=f"dm_{i}",
                        )
                        if method_val == "fixed_monthly":
                            amount = st.number_input(
                                "Fixed amount ($/month)",
                                min_value=0.0,
                                value=float(rule.get("amount", 0)),
                                step=1.0,
                                format="%.2f",
                                key=f"da_{i}",
                            )
                            pct = None
                        elif method_val == "percentage":
                            pct_val = rule.get("percentage", 0)
                            pct = st.slider(
                                "Percentage",
                                0, 100,
                                int(float(pct_val) * 100) if pct_val else 0,
                                5,
                                key=f"dpc_{i}",
                            )
                            amount = None
                        else:
                            amount = None
                            pct = None

                        start = st.text_input("Start date (YYYY-MM-DD)", value=str(rule.get("start_date", "")), key=f"dsd_{i}")
                        end = st.text_input("End date (YYYY-MM-DD)", value=str(rule.get("end_date", "")), key=f"ded_{i}")

                    notes = st.text_input("Notes", value=rule.get("notes", ""), key=f"dno_{i}")

                    col_update, col_del = st.columns([3, 1])

                    if col_update.button("Update rule", key=f"upd_{i}", type="primary", use_container_width=True):
                        updated = {"name": name, "merchant_pattern": pattern, "deductible_status": status, "method": method_val}
                        if cat:
                            updated["category"] = cat
                        if method_val == "fixed_monthly" and amount is not None:
                            updated["amount"] = amount
                        if method_val == "percentage" and pct is not None:
                            updated["percentage"] = pct / 100.0
                        if start.strip():
                            updated["start_date"] = start.strip()
                        if end.strip():
                            updated["end_date"] = end.strip()
                        if notes.strip():
                            updated["notes"] = notes.strip()

                        current_rules = load_deduction_rules()
                        if i < len(current_rules):
                            current_rules[i] = updated
                            save_deduction_rules(current_rules)
                            record_config_change("deduction_rules.yaml", "update", f"Updated deduction rule #{i}: '{name}'", "streamlit")
                            st.success(f"Updated: {name}")
                            st.rerun()

                    if col_del.button("Delete", key=f"del_{i}", type="secondary", use_container_width=True):
                        rules_to_delete.append(i)

            # Process deletes (from highest index to avoid shifting)
            if rules_to_delete:
                for idx in sorted(rules_to_delete, reverse=True):
                    remove_deduction_rule(idx, source="streamlit")
                st.success(f"Deleted {len(rules_to_delete)} rule(s).")
                st.rerun()

        else:
            st.info("No deduction rules configured yet.")

        # --- Add new rule ---
        st.divider()
        st.markdown("**Add new deduction rule**")

        with st.form("new_ded_rule"):
            col_l, col_r = st.columns(2)

            with col_l:
                new_name = st.text_input("Name", placeholder="e.g. Rogers phone business use")
                new_pattern = st.text_input("Merchant pattern", placeholder="e.g. rogers")
                new_status = st.selectbox("Deductible status", ["partial", "personal", "full"])
                new_cat = st.selectbox("Category (optional)", [""] + categories, key="new_ded_cat")

            with col_r:
                new_method = st.selectbox("Method", ["fixed_monthly", "percentage", "full"], key="new_ded_method")
                if new_method == "fixed_monthly":
                    new_amount = st.number_input("Fixed amount ($/month)", min_value=0.0, value=0.0, step=1.0, format="%.2f", key="new_ded_amt")
                    new_pct = None
                elif new_method == "percentage":
                    new_pct = st.slider("Percentage", 0, 100, 50, 5, key="new_ded_pct")
                    new_amount = None
                else:
                    new_amount = None
                    new_pct = None

                new_start = st.text_input("Start date (YYYY-MM-DD, optional)", key="new_ded_start")
                new_end = st.text_input("End date (YYYY-MM-DD, optional)", key="new_ded_end")

            new_notes = st.text_input("Notes", key="new_ded_notes")

            if st.form_submit_button("Add rule", type="primary"):
                if new_name.strip() and new_pattern.strip():
                    rule_data = {
                        "name": new_name.strip(),
                        "merchant_pattern": new_pattern.strip(),
                        "deductible_status": new_status,
                        "method": new_method,
                    }
                    if new_cat:
                        rule_data["category"] = new_cat
                    if new_method == "fixed_monthly" and new_amount is not None:
                        rule_data["amount"] = new_amount
                    if new_method == "percentage" and new_pct is not None:
                        rule_data["percentage"] = new_pct / 100.0
                    if new_start.strip():
                        rule_data["start_date"] = new_start.strip()
                    if new_end.strip():
                        rule_data["end_date"] = new_end.strip()
                    if new_notes.strip():
                        rule_data["notes"] = new_notes.strip()

                    current = load_deduction_rules()
                    current.append(rule_data)
                    save_deduction_rules(current)
                    record_config_change("deduction_rules.yaml", "add", f"Added deduction rule: '{new_name.strip()}' ({new_method})", "streamlit")
                    st.success(f"Added: {new_name.strip()}")
                    st.rerun()
                else:
                    st.warning("Name and merchant pattern are required.")

        # --- Advanced: raw YAML (collapsed) ---
        with st.expander("Advanced: Raw YAML editor", expanded=False):
            raw_data = {"deduction_rules": load_deduction_rules()}
            raw_yaml = yaml.dump(raw_data, default_flow_style=False, allow_unicode=True, sort_keys=False)
            edited_yaml = st.text_area("deduction_rules.yaml", value=raw_yaml, height=320)

            if st.button("Save raw YAML", key="save_raw_ded"):
                try:
                    parsed = yaml.safe_load(edited_yaml)
                    new_rules = parsed.get("deduction_rules", [])
                    save_deduction_rules(new_rules)
                    record_config_change("deduction_rules.yaml", "bulk_save", f"Saved {len(new_rules)} deduction rules from raw YAML", "streamlit")
                    st.success("Saved from raw YAML.")
                    st.rerun()
                except yaml.YAMLError as ye:
                    st.error(f"Invalid YAML: {ye}")

    except Exception as e:
        st.error(f"Error loading deduction_rules.yaml: {e}")

# ---------------------------------------------------------------------------
# Tab 3: Categories
# ---------------------------------------------------------------------------
with tab3:
    st.subheader("CRA T2125 Expense Categories")
    st.caption(
        "These must match the CRA form exactly — including intentional spelling. "
        "Do not rename them."
    )

    try:
        for i, cat in enumerate(categories, 1):
            st.markdown(f"**{i}.** {cat}")
    except Exception as e:
        st.error(f"Error loading categories.yaml: {e}")

# ---------------------------------------------------------------------------
# Tab 4: Change History
# ---------------------------------------------------------------------------
with tab4:
    st.subheader("Config Change History")
    st.caption("Recent changes to rules.yaml and deduction_rules.yaml across all interfaces.")

    col_filter, col_limit = st.columns([2, 1])
    with col_filter:
        file_filter = st.selectbox(
            "Filter by file",
            ["All", "rules.yaml", "deduction_rules.yaml"],
            key="hist_filter",
        )
    with col_limit:
        hist_limit = st.number_input("Show last N entries", min_value=10, max_value=500, value=50, step=10, key="hist_limit")

    history = load_config_history(
        limit=hist_limit,
        config_file=file_filter if file_filter != "All" else None,
    )

    if history:
        for entry in history:
            ts = entry.get("timestamp", "")[:19].replace("T", " ")
            action = entry.get("action", "")
            config_file = entry.get("config_file", "")
            detail = entry.get("detail", "")
            source = entry.get("source", "")

            action_colors = {"add": "green", "update": "blue", "delete": "red", "bulk_save": "orange"}
            color = action_colors.get(action, "gray")

            st.markdown(
                f":{color}[**{action.upper()}**] `{config_file}` — {detail}  \n"
                f"<small style='color:gray'>{ts} UTC | source: {source}</small>",
                unsafe_allow_html=True,
            )
    else:
        st.info("No config changes recorded yet.")
