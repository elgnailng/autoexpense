"""Reusable reset logic — used by both CLI and API."""

from __future__ import annotations

import shutil
from datetime import datetime
from pathlib import Path
from typing import Dict, List

_HERE = Path(__file__).parent.parent.resolve()


def execute_reset(level: str = "soft") -> Dict:
    """
    Wipe pipeline data at the specified level.

    Returns:
        {
            "level": str,
            "deleted_count": int,
            "backed_up": list[str],
            "message": str,
        }
    """
    level = level.lower()
    if level not in ("soft", "medium", "hard"):
        raise ValueError(f"Unknown reset level '{level}'. Use soft, medium, or hard.")

    # --- Define what each level deletes ---
    soft_targets = {
        "Database": _HERE / "state" / "transactions.duckdb",
        "Database WAL": _HERE / "state" / "transactions.duckdb.wal",
    }
    medium_targets = {
        "Merchant memory": _HERE / "state" / "merchant_memory.csv",
        "Config history": _HERE / "config" / "config_history.jsonl",
    }
    hard_targets = {
        "Keyword rules": _HERE / "config" / "rules.yaml",
        "Deduction rules": _HERE / "config" / "deduction_rules.yaml",
    }

    targets: Dict[str, Path] = {**soft_targets}
    if level in ("medium", "hard"):
        targets.update(medium_targets)
    if level == "hard":
        targets.update(hard_targets)

    log_files = list((_HERE / "logs").glob("*.log")) if (_HERE / "logs").exists() else []
    csv_files = list((_HERE / "output").glob("*.csv")) if (_HERE / "output").exists() else []

    # --- Backup config files ---
    backup_dir = _HERE / "config" / "backups"
    backupable = {
        "rules.yaml": _HERE / "config" / "rules.yaml",
        "deduction_rules.yaml": _HERE / "config" / "deduction_rules.yaml",
        "merchant_memory.csv": _HERE / "state" / "merchant_memory.csv",
        "config_history.jsonl": _HERE / "config" / "config_history.jsonl",
    }
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backed_up: List[str] = []
    for name, path in backupable.items():
        if path.exists():
            backup_dir.mkdir(parents=True, exist_ok=True)
            dest = backup_dir / f"{stamp}_{name}"
            shutil.copy2(path, dest)
            backed_up.append(dest.name)

    # --- Delete ---
    deleted = 0
    for label, path in targets.items():
        if path.exists():
            path.unlink()
            deleted += 1

    for f in log_files:
        f.unlink()
        deleted += 1

    for f in csv_files:
        f.unlink()
        deleted += 1

    message = f"Reset ({level}) complete. Deleted {deleted} file(s)."
    if backed_up:
        message += f" Backed up {len(backed_up)} file(s)."

    return {
        "level": level,
        "deleted_count": deleted,
        "backed_up": backed_up,
        "message": message,
    }
