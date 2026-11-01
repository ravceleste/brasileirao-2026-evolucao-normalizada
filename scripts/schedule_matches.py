#!/usr/bin/env python3
"""Generate a local schedule for checks after upcoming matches finish."""

from __future__ import annotations

import json
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from update import AuditError, ROOT, canonical_team, fetch_feed


FIXTURES_PATH = ROOT / "data" / "fixtures_2026.json"
TEAMS_PATH = ROOT / "data" / "brasileirao_2026.json"
CHECKS_PATH = ROOT / "data" / "match_check_schedule.json"
BR_TZ = ZoneInfo("America/Sao_Paulo")
CHECK_AFTER_KICKOFF = timedelta(hours=2, minutes=15)
CHECK_INTERVAL_MINUTES = 15
LOOKAHEAD = timedelta(days=14)
FINAL_STATUSES = {"STATUS_FULL_TIME", "STATUS_FINAL"}
IGNORED_STATUSES = {"STATUS_CANCELED", "STATUS_CANCELLED"}


def _status(event: dict) -> dict:
    competition = (event.get("competitions") or [{}])[0]
    return competition.get("status", {}).get("type", {})


def _fixture_teams(event: dict) -> tuple[str, str] | None:
    competition = (event.get("competitions") or [{}])[0]
    by_side = {
        team.get("homeAway"): team
        for team in competition.get("competitors", [])
    }
    if set(by_side) != {"home", "away"}:
        return None
    try:
        return (
            canonical_team(by_side["home"]["team"]["displayName"]),
            canonical_team(by_side["away"]["team"]["displayName"]),
        )
    except (KeyError, TypeError):
        return None


def build_check_schedule(feed: dict, fixtures: dict, teams: set[str], now: datetime) -> dict:
    if now.tzinfo is None:
        raise ValueError("now precisa conter um fuso horário.")

    known_fixtures = {
        (item["home"], item["away"])
        for item in fixtures["fixtures"]
    }
    grouped: dict[str, dict] = {}
    seen_ids: set[str] = set()
    now_utc = now.astimezone(timezone.utc)

    for event in feed.get("events", []):
        if event.get("season", {}).get("year") != 2026:
            continue
        event_id = str(event.get("id", ""))
        if not event_id:
            raise AuditError("Partida programada sem ID no feed da ESPN.")
        if event_id in seen_ids:
            raise AuditError(f"ID duplicado no calendário ESPN: {event_id}.")
        seen_ids.add(event_id)

        status = _status(event)
        if status.get("completed") or status.get("name") in FINAL_STATUSES | IGNORED_STATUSES:
            continue

        try:
            kickoff = datetime.fromisoformat(event["date"].replace("Z", "+00:00"))
        except (KeyError, TypeError, ValueError) as exc:
            raise AuditError(f"Data programada inválida para a partida {event_id}.") from exc
        if kickoff.tzinfo is None:
            raise AuditError(f"Horário sem fuso para a partida {event_id}.")
        kickoff = kickoff.astimezone(timezone.utc)
        check_at = kickoff + CHECK_AFTER_KICKOFF
        # The fixed GitHub cron wakes every 15 minutes. Round each target up
        # to its next slot so the workflow only fetches results after this time.
        remainder = check_at.minute % CHECK_INTERVAL_MINUTES
        if remainder or check_at.second or check_at.microsecond:
            check_at = check_at.replace(second=0, microsecond=0) + timedelta(
                minutes=CHECK_INTERVAL_MINUTES - remainder
            )
        if check_at <= now_utc or check_at > now_utc + LOOKAHEAD:
            continue

        pair = _fixture_teams(event)
        if pair is None:
            raise AuditError(f"Partida programada {event_id} sem mandante/visitante.")
        home, away = pair
        if home not in teams or away not in teams or home == away:
            raise AuditError(f"Partida programada {event_id} inclui clube inválido: {pair}.")
        if pair not in known_fixtures:
            raise AuditError(f"Confronto programado fora da tabela CBF: {pair}.")

        local_check = check_at.astimezone(BR_TZ)
        cron = f"{local_check.minute} {local_check.hour} {local_check.day} {local_check.month} *"
        entry = grouped.setdefault(
            cron,
            {"check_at": local_check.isoformat(), "event_ids": []},
        )
        entry["event_ids"].append(event_id)

    for entry in grouped.values():
        entry["event_ids"].sort()
    return {
        "timezone": "America/Sao_Paulo",
        "check_after_kickoff_minutes": int(CHECK_AFTER_KICKOFF.total_seconds() // 60),
        "checks": dict(sorted(grouped.items(), key=lambda item: item[1]["check_at"])),
    }


def main() -> None:
    fixtures = json.loads(FIXTURES_PATH.read_text(encoding="utf-8"))
    data = json.loads(TEAMS_PATH.read_text(encoding="utf-8"))
    teams = set(data.get("teams", {}))
    if len(teams) != 20:
        raise AuditError("O JSON precisa conter exatamente os 20 clubes.")

    feed = fetch_feed()
    schedule = build_check_schedule(feed, fixtures, teams, datetime.now(timezone.utc))
    CHECKS_PATH.write_text(
        json.dumps(schedule, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"Agendamentos pós-jogo gerados: {len(schedule['checks'])} horários.")


if __name__ == "__main__":
    try:
        main()
    except AuditError as exc:
        raise SystemExit(f"AUDITORIA REPROVADA: {exc}") from exc
