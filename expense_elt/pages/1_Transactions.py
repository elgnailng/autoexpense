"""
Transactions page — browse, filter, and download all transactions.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import pandas as pd
import streamlit as st

from staging.database import get_connection

st.set_page_config(page_title="Transactions", layout="wide")
st.title("Transactions")


@st.cache_data(ttl=30)
def load_transactions() -> pd.DataFrame:
    con = get_connection()
    try:
        df = con.execute("""
            SELECT
                ct.transaction_id,
                nt.transaction_date,
                nt.institution,
                nt.merchant_raw,
                nt.merchant_normalized,
                nt.original_amount,
                ct.category,
                ct.deductible_status,
                ct.deductible_amount,
                ROUND(ct.confidence * 100) AS confidence_pct,
                ct.review_required,
                ct.rule_applied,
                ct.notes,
                nt.source_file,
                nt.description_raw
            FROM categorized_transactions ct
            JOIN normalized_transactions nt ON ct.transaction_id = nt.transaction_id
            WHERE nt.is_credit = FALSE
            ORDER BY nt.transaction_date DESC
        """).df()
        return df
    finally:
        con.close()


try:
    df = load_transactions()

    if df.empty:
        st.info("No transactions found. Run `python main.py run` first.")
        st.stop()

    # --- Filters ---
    with st.expander("Filters", expanded=True):
        col1, col2, col3, col4 = st.columns(4)

        with col1:
            institutions = ["All"] + sorted(df["institution"].dropna().unique().tolist())
            institution_filter = st.selectbox("Institution", institutions)

        with col2:
            categories = ["All"] + sorted(df["category"].dropna().unique().tolist())
            category_filter = st.selectbox("Category", categories)

        with col3:
            status_options = ["All", "full", "partial", "personal", "needs review"]
            status_filter = st.selectbox("Deductible Status", status_options)

        with col4:
            min_date = df["transaction_date"].min()
            max_date = df["transaction_date"].max()
            date_range = st.date_input(
                "Date Range",
                value=(min_date, max_date),
                min_value=min_date,
                max_value=max_date,
            )

    # Apply filters
    filtered = df.copy()
    if institution_filter != "All":
        filtered = filtered[filtered["institution"] == institution_filter]
    if category_filter != "All":
        filtered = filtered[filtered["category"] == category_filter]
    if status_filter != "All":
        if status_filter == "needs review":
            filtered = filtered[filtered["review_required"] == True]
        else:
            filtered = filtered[filtered["deductible_status"] == status_filter]
    if isinstance(date_range, (list, tuple)) and len(date_range) == 2:
        filtered = filtered[
            (filtered["transaction_date"] >= pd.Timestamp(date_range[0]))
            & (filtered["transaction_date"] <= pd.Timestamp(date_range[1]))
        ]

    # --- Summary bar ---
    total_shown = filtered["original_amount"].sum()
    total_deductible = filtered.loc[
        filtered["deductible_status"].isin(["full", "partial"]), "deductible_amount"
    ].sum()
    review_count = int(filtered["review_required"].sum())

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Transactions", len(filtered))
    c2.metric("Total amount", f"${total_shown:,.2f}")
    c3.metric("Deductible", f"${total_deductible:,.2f}")
    c4.metric("Needs review", review_count)

    # --- Display table ---
    display_cols = [
        "transaction_date",
        "institution",
        "merchant_raw",
        "original_amount",
        "category",
        "deductible_status",
        "deductible_amount",
        "confidence_pct",
        "notes",
    ]

    # Clean up date column — strip time component
    filtered["transaction_date"] = pd.to_datetime(filtered["transaction_date"]).dt.date

    # Color-code rows by deductible status
    STATUS_COLORS = {
        "full": "background-color: #d4edda; color: #155724",
        "partial": "background-color: #fff3cd; color: #856404",
        "personal": "background-color: #f8f9fa; color: #6c757d",
    }

    display_df = filtered[display_cols + ["review_required"]].copy()

    def color_row(row):
        n = len(row)
        if display_df.loc[row.name, "review_required"]:
            return ["background-color: #f8d7da"] * n
        color = STATUS_COLORS.get(display_df.loc[row.name, "deductible_status"] or "", "")
        return [color] * n

    styled = (
        display_df[display_cols]
        .style.apply(color_row, axis=1)
        .format(
            {
                "original_amount": "${:.2f}",
                "deductible_amount": "${:.2f}",
                "confidence_pct": "{:.0f}%",
            }
        )
    )

    st.dataframe(
        styled,
        use_container_width=True,
        height=1800,
        column_config={
            "transaction_date": st.column_config.DateColumn("Date", width="small"),
            "institution": st.column_config.TextColumn("Institution", width="small"),
            "merchant_raw": st.column_config.TextColumn("Merchant", width="large"),
            "original_amount": st.column_config.TextColumn("Amount", width="small"),
            "category": st.column_config.TextColumn("Category", width="medium"),
            "deductible_status": st.column_config.TextColumn("Status", width="small"),
            "deductible_amount": st.column_config.TextColumn("Deductible", width="small"),
            "confidence_pct": st.column_config.TextColumn("Conf%", width="small"),
            "notes": st.column_config.TextColumn("Notes", width="medium"),
        },
    )

    # --- Actions ---
    col_dl, col_refresh = st.columns([3, 1])
    with col_dl:
        csv_data = filtered[display_cols].to_csv(index=False).encode("utf-8")
        st.download_button(
            "Download filtered as CSV",
            csv_data,
            file_name="filtered_transactions.csv",
            mime="text/csv",
        )
    with col_refresh:
        if st.button("Refresh", use_container_width=True):
            st.cache_data.clear()
            st.rerun()

except Exception as e:
    st.error(f"Error loading transactions: {e}")
    import traceback
    st.code(traceback.format_exc())
