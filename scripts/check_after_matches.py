#!/usr/bin/env python3
"""Fetch scores only when a post-match check is due; never poll during games."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
CHECKS_PATH = ROOT / "data" / "match_check_schedule.json"
UPDATE_SCRIPT = ROOT / "scripts" / "update.py"
RETRY_DELAYS = (15 * 60, 30 * 60)
DUE_WINDOW = timedelta(minutes=15)
BR_TZ = ZoneInfo("America/Sao_Paulo")


def run_update(required_ids: list[str] | None) -> tuple[int, bool | None]:
    command = [sys.executable, str(UPDATE_SCRIPT)]
    if required_ids:
        command.extend(["--require-final-ids", ",".join(required_ids)])
    result = subprocess.run(command, cwd=ROOT, capture_output=True, text=True)
    if result.stdout:
        print(result.stdout, end="")
    if result.stderr:
        print(result.stderr, end="", file=sys.stderr)

    targets_line = next(
        (line for line in result.stdout.splitlines() if line.startswith("TARGETS_FINAL=")),
        None,
    )
    targets_final = None if targets_line is None else targets_line.split("=", 1)[1] == "true"
    return result.returncode, targets_final


def scheduled_event_ids(now: datetime) -> list[str]:
    if not CHECKS_PATH.exists():
        return []
    schedule = json.loads(CHECKS_PATH.read_text(encoding="utf-8"))
    due_ids: set[str] = set()
    for entry in schedule.get("checks", {}).values():
        try:
            check_at = datetime.fromisoformat(entry["check_at"])
        except (KeyError, TypeError, ValueError):
            continue
        if check_at.tzinfo is None:
            continue
        age = now - check_at.astimezone(BR_TZ)
        if timedelta(0) <= age < DUE_WINDOW:
            due_ids.update(str(event_id) for event_id in entry.get("event_ids", []))
    return sorted(due_ids)


def main() -> int:
    # Manual runs still refresh once. Scheduled runs are hourly quarter-hour
    # wakeups, but only a local due-time match causes a result-feed request.
    if not os.environ.get("GITHUB_EVENT_SCHEDULE") and os.environ.get("GITHUB_EVENT_NAME") == "workflow_dispatch":
        code, _ = run_update(None)
        return code

    event_ids = scheduled_event_ids(datetime.now(BR_TZ))
    if not event_ids:
        print("Nenhuma checagem pós-jogo prevista neste horário; sem consulta à fonte.")
        return 0

    for attempt in range(3):
        code, all_targets_final = run_update(event_ids)
        if code == 0 and all_targets_final is True:
            print("Todas as partidas deste horário estão encerradas.")
            return 0
        if code not in {0, 2}:
            return code
        if attempt == 2:
            print(
                "A fonte ainda não marcou todas as partidas como encerradas; "
                "a conferência diária de recuperação fará nova tentativa."
            )
            return 0
        delay = RETRY_DELAYS[attempt]
        print(f"Resultado final ainda incompleto; nova tentativa em {delay // 60} minutos.")
        time.sleep(delay)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
