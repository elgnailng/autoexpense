"""
Tax2025 Expense ELT — Streamlit Web App

Run from expense_elt/:
    streamlit run app.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import streamlit as st

from staging.database import get_connection

st.set_page_config(
    page_title="Tax2025 Expenses",
    page_icon="🧾",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.title("Tax2025 — Expense Dashboard")
st.caption("BC self-employment tax prep · Local-first pipeline")


@st.cache_data(ttl=30)
def get_status():
    con = get_connection()
    try:
        raw = con.execute("SELECT COUNT(*) FROM raw_transactions").fetchone()[0]
        normalized = con.execute("SELECT COUNT(*) FROM normalized_transactions").fetchone()[0]
        categorized = con.execute("SELECT COUNT(*) FROM categorized_transactions").fetchone()[0]
        review_needed = con.execute(
            "SELECT COUNT(*) FROM categorized_transactions WHERE review_required = TRUE"
        ).fetchone()[0]
        total_deductible = con.execute(
            """SELECT COALESCE(SUM(deductible_amount), 0)
               FROM categorized_transactions
               WHERE deductible_status IN ('full', 'partial')"""
        ).fetchone()[0]
        return {
            "raw": raw,
            "normalized": normalized,
            "categorized": categorized,
            "review_needed": review_needed,
            "total_deductible": float(total_deductible),
        }
    finally:
        con.close()


try:
    s = get_status()

    col1, col2, col3, col4, col5 = st.columns(5)
    col1.metric("Raw transactions", s["raw"])
    col2.metric("Normalized", s["normalized"])
    col3.metric("Categorized", s["categorized"])
    col4.metric(
        "Needs review",
        s["review_needed"],
        delta=f"-{s['review_needed']}" if s["review_needed"] > 0 else None,
        delta_color="inverse",
    )
    col5.metric("Total deductible", f"${s['total_deductible']:,.2f}")

    st.divider()

    if s["review_needed"] > 0:
        st.warning(
            f"**{s['review_needed']} transactions need manual review.** "
            "Go to the **Review** page to label them."
        )
    elif s["categorized"] > 0:
        st.success("All transactions reviewed.")

    if s["raw"] == 0:
        st.info(
            "No data yet. Run the pipeline from `expense_elt/`:\n\n"
            "```\npython main.py run\n```"
        )

except Exception as e:
    st.error(f"Could not connect to database: {e}")
    st.info(
        "Make sure you have run the pipeline first:\n\n"
        "```\npython main.py extract\npython main.py transform\npython main.py categorize\n```"
    )

st.divider()

st.markdown("""
### Pipeline commands
Run these from `expense_elt/` in a terminal:

| Command | What it does |
|---|---|
| `python main.py run` | Run all non-interactive steps (extract → transform → categorize) |
| `python main.py extract` | Parse PDFs → load raw transactions |
| `python main.py transform` | Normalize + deduplicate |
| `python main.py categorize` | Apply keyword rules + merchant memory |
| `python main.py export` | Write CSVs to `output/` |

Then come back here to **Review** any flagged transactions.
""")

if st.button("Refresh status"):
    st.cache_data.clear()
    st.rerun()
