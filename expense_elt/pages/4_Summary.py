"""
Summary page — financial overview, charts, and T2125-ready breakdown.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from staging.database import get_connection

st.set_page_config(page_title="Summary", layout="wide")
st.title("Summary")


@st.cache_data(ttl=60)
def load_data():
    con = get_connection()
    try:
        totals = con.execute("""
            SELECT
                COUNT(*)                                                                    AS total_transactions,
                COALESCE(SUM(ct.original_amount), 0)                                       AS total_spend,
                COALESCE(SUM(CASE WHEN ct.deductible_status IN ('full','partial')
                                    AND ct.review_required = FALSE
                               THEN ct.deductible_amount ELSE 0 END), 0)                   AS total_deductible,
                COALESCE(SUM(CASE WHEN ct.deductible_status = 'personal'
                               THEN ct.original_amount ELSE 0 END), 0)                     AS total_personal,
                COUNT(CASE WHEN ct.review_required THEN 1 END)                             AS review_count
            FROM categorized_transactions ct
            JOIN normalized_transactions nt ON ct.transaction_id = nt.transaction_id
            WHERE nt.is_credit = FALSE
        """).fetchone()

        category_df = con.execute("""
            SELECT
                ct.category,
                COUNT(*)                    AS tx_count,
                SUM(ct.original_amount)     AS total_original,
                SUM(ct.deductible_amount)   AS total_deductible
            FROM categorized_transactions ct
            JOIN normalized_transactions nt ON ct.transaction_id = nt.transaction_id
            WHERE nt.is_credit = FALSE
              AND ct.deductible_status IN ('full', 'partial')
              AND ct.review_required = FALSE
            GROUP BY ct.category
            ORDER BY total_deductible DESC
        """).df()

        monthly_df = con.execute("""
            SELECT
                DATE_TRUNC('month', nt.transaction_date)                                        AS month,
                SUM(ct.original_amount)                                                         AS total_spend,
                SUM(CASE WHEN ct.deductible_status IN ('full','partial')
                         AND ct.review_required = FALSE
                    THEN ct.deductible_amount ELSE 0 END)                                       AS total_deductible
            FROM categorized_transactions ct
            JOIN normalized_transactions nt ON ct.transaction_id = nt.transaction_id
            WHERE nt.is_credit = FALSE
            GROUP BY month
            ORDER BY month
        """).df()

        institution_df = con.execute("""
            SELECT
                nt.institution,
                COUNT(*)                AS tx_count,
                SUM(ct.original_amount) AS total_spend
            FROM categorized_transactions ct
            JOIN normalized_transactions nt ON ct.transaction_id = nt.transaction_id
            WHERE nt.is_credit = FALSE
            GROUP BY nt.institution
        """).df()

        return totals, category_df, monthly_df, institution_df
    finally:
        con.close()


try:
    totals, category_df, monthly_df, institution_df = load_data()

    if totals[0] == 0:
        st.info("No data yet. Run `python main.py run` first.")
        st.stop()

    total_txns, total_spend, total_deductible, total_personal, review_count = totals
    total_spend = float(total_spend)
    total_deductible = float(total_deductible)
    total_personal = float(total_personal)
    deductible_pct = (total_deductible / total_spend * 100) if total_spend else 0

    # --- KPIs ---
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Transactions", int(total_txns))
    c2.metric("Total spend", f"${total_spend:,.2f}")
    c3.metric("Deductible", f"${total_deductible:,.2f}")
    c4.metric("Personal", f"${total_personal:,.2f}")
    c5.metric("Deductible %", f"{deductible_pct:.1f}%")

    if int(review_count) > 0:
        st.warning(
            f"**{int(review_count)} transactions still need review** — "
            "totals above may be incomplete. Go to the Review page."
        )

    st.divider()

    # --- Charts row ---
    col_bar, col_pie = st.columns([3, 2])

    with col_bar:
        st.subheader("Deductible by Category")
        if not category_df.empty:
            cat_sorted = category_df.sort_values("total_deductible", ascending=True)
            fig = px.bar(
                cat_sorted,
                x="total_deductible",
                y="category",
                orientation="h",
                labels={"total_deductible": "Deductible Amount (CAD)", "category": ""},
                color="total_deductible",
                color_continuous_scale="Blues",
                text=cat_sorted["total_deductible"].apply(lambda v: f"${v:,.0f}"),
            )
            fig.update_traces(textposition="outside")
            fig.update_layout(
                showlegend=False,
                coloraxis_showscale=False,
                margin=dict(l=0, r=40, t=10, b=0),
                height=420,
            )
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No deductible transactions yet.")

    with col_pie:
        st.subheader("Spend Breakdown")
        uncategorized = max(0.0, total_spend - total_deductible - total_personal)
        fig2 = go.Figure(
            data=[
                go.Pie(
                    labels=["Deductible", "Personal", "Uncategorized/Review"],
                    values=[total_deductible, total_personal, uncategorized],
                    hole=0.45,
                    marker_colors=["#28a745", "#6c757d", "#ffc107"],
                    textinfo="label+percent",
                )
            ]
        )
        fig2.update_layout(
            showlegend=False,
            margin=dict(l=0, r=0, t=10, b=0),
            height=280,
        )
        st.plotly_chart(fig2, use_container_width=True)

        if not institution_df.empty:
            st.subheader("By Institution")
            for _, row in institution_df.iterrows():
                st.metric(
                    row["institution"],
                    f"${float(row['total_spend']):,.2f}",
                    f"{int(row['tx_count'])} transactions",
                )

    # --- Monthly trend ---
    if not monthly_df.empty and len(monthly_df) > 1:
        st.subheader("Monthly Trend")
        monthly_df["month"] = monthly_df["month"].astype(str).str[:7]
        fig3 = px.line(
            monthly_df,
            x="month",
            y=["total_spend", "total_deductible"],
            markers=True,
            labels={"value": "Amount (CAD)", "month": "", "variable": ""},
            color_discrete_map={
                "total_spend": "#6c757d",
                "total_deductible": "#28a745",
            },
        )
        fig3.update_layout(height=260, margin=dict(l=0, r=0, t=10, b=0))
        st.plotly_chart(fig3, use_container_width=True)

    # --- T2125 table ---
    st.divider()
    st.subheader("T2125 — Business Expenses Summary")
    st.caption("Copy these totals into your CRA T2125 form (Statement of Business Activities).")

    if not category_df.empty:
        t2125 = category_df[["category", "tx_count", "total_deductible"]].copy()
        t2125 = t2125.sort_values("total_deductible", ascending=False)

        # Totals row
        totals_row = {
            "category": "**TOTAL**",
            "tx_count": t2125["tx_count"].sum(),
            "total_deductible": t2125["total_deductible"].sum(),
        }

        t2125["total_deductible_fmt"] = t2125["total_deductible"].apply(lambda v: f"${float(v):,.2f}")
        t2125_display = t2125[["category", "tx_count", "total_deductible_fmt"]].copy()
        t2125_display.columns = ["CRA Category", "# Transactions", "Deductible Amount"]

        st.dataframe(t2125_display, use_container_width=True, hide_index=True)

        st.markdown(
            f"**Grand total deductible: ${t2125['total_deductible'].sum():,.2f} CAD**"
        )

        csv_data = t2125_display.to_csv(index=False).encode("utf-8")
        st.download_button(
            "Download T2125 summary as CSV",
            csv_data,
            file_name="t2125_summary.csv",
            mime="text/csv",
        )

    if st.button("Refresh data"):
        st.cache_data.clear()
        st.rerun()

except Exception as e:
    st.error(f"Error loading summary: {e}")
    import traceback
    st.code(traceback.format_exc())
