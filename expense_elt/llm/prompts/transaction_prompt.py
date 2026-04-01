"""Format transactions into the user prompt for LLM evaluation."""

from __future__ import annotations

from typing import Dict, List


def build_transaction_prompt(transactions: List[Dict]) -> str:
    """
    Format a batch of transactions for LLM evaluation.

    Each transaction dict should have:
        index, transaction_date, merchant_normalized, original_amount, institution

    Returns a user prompt string with numbered transactions and JSON output request.
    """
    lines = ["Evaluate the following transactions:\n"]

    for txn in transactions:
        idx = txn["index"]
        date_str = txn.get("transaction_date", "unknown")
        merchant = txn.get("merchant_normalized", "UNKNOWN")
        amount = txn.get("original_amount", 0.0)
        institution = txn.get("institution", "unknown")

        # Format amount with sign
        amount_str = f"${abs(amount):.2f}"
        if amount < 0:
            amount_str = f"-{amount_str} (credit/refund)"

        lines.append(
            f"[{idx}] date={date_str} merchant=\"{merchant}\" "
            f"amount={amount_str} institution={institution}"
        )

    n = len(transactions)
    obj_word = "object" if n == 1 else "objects"
    lines.append(
        f"\nYou MUST evaluate ALL {n} transaction{'s' if n != 1 else ''} above."
        ' Respond with a JSON object: {"evaluations": [...]}'
        f" where the array contains exactly {n} evaluation {obj_word},"
        " one per transaction, in order."
    )

    return "\n".join(lines)
