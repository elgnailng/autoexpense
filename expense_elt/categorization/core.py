from __future__ import annotations

from datetime import date
from typing import Any, Optional



def parse_transaction_date(txn_date_value: Any) -> Optional[date]:
    if not txn_date_value:
        return None
    try:
        if isinstance(txn_date_value, str):
            return date.fromisoformat(txn_date_value)
        return txn_date_value
    except ValueError:
        return None
