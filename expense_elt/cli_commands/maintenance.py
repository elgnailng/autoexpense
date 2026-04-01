from __future__ import annotations

import re
import shutil
from collections import defaultdict
from pathlib import Path
from typing import Optional

import typer

from cli_commands.common import console, error, header, success

APP_ROOT = Path(__file__).resolve().parent.parent



def reset_command(level: str, yes: bool) -> None:
    normalized_level = level.lower()
    if normalized_level not in ("soft", "medium", "hard"):
        error(f"Unknown level '{level}'. Use soft, medium, or hard.")
        raise typer.Exit(1)

    header(f"Reset Pipeline Data - {normalized_level.upper()}")

    console.print(f"\n[bold]Level {normalized_level.upper()} will delete:[/bold]")
    if normalized_level == "soft":
        console.print("  Database, output CSVs, logs")
        console.print("  [dim]Keeping: merchant memory, config history, rules, deduction rules[/dim]")
    elif normalized_level == "medium":
        console.print("  Database, output CSVs, logs, merchant memory, config history")
        console.print("  [dim]Keeping: rules.yaml, deduction_rules.yaml[/dim]")
    else:
        console.print("  Everything (full factory reset)")

    if not yes:
        confirm = typer.confirm("\nProceed?")
        if not confirm:
            console.print("[yellow]Aborted.[/yellow]")
            raise typer.Exit(0)

    from services.reset_service import execute_reset

    result = execute_reset(level=normalized_level)

    if result["backed_up"]:
        console.print(f"[cyan]Backed up {len(result['backed_up'])} file(s) to config/backups/[/cyan]")

    success(result["message"])
    console.print("Run [bold]python main.py run[/bold] to rebuild.")



def restore_command(backup_id: Optional[str], yes: bool) -> None:
    backup_dir = APP_ROOT / "config" / "backups"
    if not backup_dir.exists() or not any(backup_dir.iterdir()):
        error("No backups found in config/backups/.")
        raise typer.Exit(1)

    restore_targets = {
        "rules.yaml": APP_ROOT / "config" / "rules.yaml",
        "deduction_rules.yaml": APP_ROOT / "config" / "deduction_rules.yaml",
        "merchant_memory.csv": APP_ROOT / "state" / "merchant_memory.csv",
        "config_history.jsonl": APP_ROOT / "config" / "config_history.jsonl",
    }

    stamp_pattern = re.compile(r"^(\d{8}_\d{6})_(.+)$")
    backup_sets: dict[str, dict[str, Path]] = defaultdict(dict)

    for backup_file in sorted(backup_dir.iterdir()):
        if not backup_file.is_file():
            continue
        match = stamp_pattern.match(backup_file.name)
        if match:
            stamp, original = match.group(1), match.group(2)
            if original in restore_targets:
                backup_sets[stamp][original] = backup_file

    if not backup_sets:
        error("No valid backup sets found in config/backups/.")
        raise typer.Exit(1)

    sorted_stamps = sorted(backup_sets.keys(), reverse=True)

    if backup_id is None:
        header("Available Backups")
        for index, stamp in enumerate(sorted_stamps, 1):
            files = backup_sets[stamp]
            display_ts = f"{stamp[:4]}-{stamp[4:6]}-{stamp[6:8]} {stamp[9:11]}:{stamp[11:13]}:{stamp[13:15]}"
            console.print(f"  [bold cyan]{index}.[/bold cyan] {display_ts}  [dim]({stamp})[/dim]")
            for name in sorted(files.keys()):
                console.print(f"      * {name}")
        console.print("\nRestore with: [bold]python main.py restore <timestamp>[/bold]")
        console.print(f"Example:      [bold]python main.py restore {sorted_stamps[0]}[/bold]")
        return

    resolved_backup_id = backup_id
    if resolved_backup_id.isdigit():
        idx = int(resolved_backup_id) - 1
        if idx < 0 or idx >= len(sorted_stamps):
            error(f"Invalid index {backup_id}. Choose 1-{len(sorted_stamps)}.")
            raise typer.Exit(1)
        resolved_backup_id = sorted_stamps[idx]

    if resolved_backup_id not in backup_sets:
        error(f"No backup found with timestamp '{resolved_backup_id}'.")
        console.print("Run [bold]python main.py restore[/bold] to list available backups.")
        raise typer.Exit(1)

    files = backup_sets[resolved_backup_id]
    display_ts = f"{resolved_backup_id[:4]}-{resolved_backup_id[4:6]}-{resolved_backup_id[6:8]} {resolved_backup_id[9:11]}:{resolved_backup_id[11:13]}:{resolved_backup_id[13:15]}"

    header(f"Restore Backup - {display_ts}")
    console.print("[bold]Files to restore:[/bold]")
    for name, source_path in sorted(files.items()):
        destination = restore_targets[name]
        exists = "[yellow]overwrite[/yellow]" if destination.exists() else "[green]create[/green]"
        console.print(f"  {name} -> {destination.relative_to(APP_ROOT)} ({exists})")

    if not yes:
        confirm = typer.confirm("\nProceed?")
        if not confirm:
            console.print("[yellow]Aborted.[/yellow]")
            raise typer.Exit(0)

    restored = 0
    for name, source_path in sorted(files.items()):
        destination = restore_targets[name]
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source_path, destination)
        restored += 1
        console.print(f"  [green]Restored[/green] {name}")

    success(f"Restored {restored} file(s) from backup {display_ts}.")
    console.print("Run [bold]python main.py categorize[/bold] to re-apply restored rules.")
