"""
merchant_memory.py - Persistent merchant->category mapping with fuzzy lookup.

Storage: state/merchant_memory.csv
Columns: merchant_normalized, category, deductible_status,
         deductible_amount_rule (JSON), confidence, decision_source
"""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from rapidfuzz import fuzz, process

_STATE_DIR = Path(__file__).parent.parent / "state"
_MEMORY_FILE = _STATE_DIR / "merchant_memory.csv"

_FIELDNAMES = [
    "merchant_normalized",
    "category",
    "deductible_status",
    "deductible_amount_rule",
    "confidence",
    "decision_source",
]

_FUZZY_THRESHOLD = 85  # minimum score for a fuzzy match (0-100)


class MerchantMemory:
    """
    In-memory store backed by a CSV file.

    Provides exact and fuzzy merchant lookups, and persists new decisions.
    """

    def __init__(self, memory_file: Optional[Path] = None):
        self._file = memory_file or _MEMORY_FILE
        self._records: Dict[str, Dict] = {}  # keyed by merchant_normalized
        self._load()

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def _load(self) -> None:
        """Load records from CSV, creating it with headers if absent."""
        if not self._file.exists():
            self._file.parent.mkdir(parents=True, exist_ok=True)
            with open(self._file, "w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=_FIELDNAMES)
                writer.writeheader()
            return

        with open(self._file, "r", newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                key = row.get("merchant_normalized", "").strip()
                if key:
                    self._records[key] = row

    def _save_all(self) -> None:
        """Rewrite the entire CSV."""
        with open(self._file, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=_FIELDNAMES)
            writer.writeheader()
            for record in self._records.values():
                writer.writerow({k: record.get(k, "") for k in _FIELDNAMES})

    def _append_row(self, row: Dict) -> None:
        """Append a single row to CSV (faster than full rewrite for new entries)."""
        write_header = not self._file.exists() or self._file.stat().st_size == 0
        with open(self._file, "a", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=_FIELDNAMES)
            if write_header:
                writer.writeheader()
            writer.writerow({k: row.get(k, "") for k in _FIELDNAMES})

    # ------------------------------------------------------------------
    # Lookup
    # ------------------------------------------------------------------

    def lookup(
        self, merchant_normalized: str
    ) -> Optional[Tuple[str, str, float, str]]:
        """
        Look up a merchant by normalized name.

        1. Exact match (confidence from stored record)
        2. Fuzzy match via rapidfuzz (threshold 85, confidence 0.75)

        Returns (category, deductible_status, confidence, decision_source)
        or None if not found.
        """
        if not self._records:
            return None

        # 1. Exact match
        record = self._records.get(merchant_normalized)
        if record:
            return (
                record.get("category", "Other expenses"),
                record.get("deductible_status", "full"),
                float(record.get("confidence", 0.98)),
                record.get("decision_source", "memory"),
            )

        # 2. Fuzzy match
        keys = list(self._records.keys())
        if not keys:
            return None

        result = process.extractOne(
            merchant_normalized,
            keys,
            scorer=fuzz.token_sort_ratio,
            score_cutoff=_FUZZY_THRESHOLD,
        )
        if result:
            best_key, score, _ = result
            record = self._records[best_key]
            return (
                record.get("category", "Other expenses"),
                record.get("deductible_status", "full"),
                0.75,  # fuzzy match confidence
                record.get("decision_source", "memory_fuzzy"),
            )

        return None

    # ------------------------------------------------------------------
    # Save / update
    # ------------------------------------------------------------------

    def save_decision(
        self,
        merchant_normalized: str,
        category: str,
        deductible_status: str,
        confidence: float,
        decision_source: str,
        deductible_amount_rule: Optional[Dict] = None,
    ) -> None:
        """
        Save or update a categorization decision for a merchant.
        """
        rule_json = json.dumps(deductible_amount_rule) if deductible_amount_rule else ""
        row = {
            "merchant_normalized": merchant_normalized,
            "category": category,
            "deductible_status": deductible_status,
            "deductible_amount_rule": rule_json,
            "confidence": str(confidence),
            "decision_source": decision_source,
        }

        is_new = merchant_normalized not in self._records
        self._records[merchant_normalized] = row

        if is_new:
            self._append_row(row)
        else:
            # Update in place — rewrite
            self._save_all()

    def all_merchants(self) -> List[str]:
        """Return list of all known merchant names."""
        return list(self._records.keys())


# Module-level singleton
_memory: Optional[MerchantMemory] = None


def get_memory() -> MerchantMemory:
    """Return the module-level MerchantMemory singleton."""
    global _memory
    if _memory is None:
        _memory = MerchantMemory()
    return _memory
