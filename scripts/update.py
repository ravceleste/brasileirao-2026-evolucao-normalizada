#!/usr/bin/env python3
"""Refresh the static Brasileirão trajectories from ESPN's public JSON feed."""

from __future__ import annotations

import json
import os
import tempfile
import urllib.error
import urllib.request
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
DATA_PATH = ROOT / "data" / "brasileirao_2026.json"
FIXTURES_PATH = ROOT / "data" / "fixtures_2026.json"
FEED_URL = (
    "https://site.api.espn.com/apis/site/v2/sports/soccer/bra.1/"
    "scoreboard?dates=2026&limit=1000"
)
BR_TZ = ZoneInfo("America/Sao_Paulo")

ALIASES = {
    "Athletico Paranaense": "Athletico-PR",
    "Atlético Paranaense": "Athletico-PR",
    "Red Bull Bragantino": "Bragantino",
    "Vasco da Gama": "Vasco",
}


class AuditError(RuntimeError):
    pass


def fetch_feed() -> dict:
    request = urllib.request.Request(
        FEED_URL,
        headers={"User-Agent": "Brasileirao-2026-static-chart/1.0"},
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            payload = json.load(response)
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        raise AuditError(f"Falha ao consultar o placar JSON da ESPN: {exc}") from exc
    if not payload.get("events") or payload.get("leagues", [{}])[0].get("id") != "630":
        raise AuditError("A resposta não corresponde ao Brasileirão Série A 2026.")
    return payload


def canonical_team(name: str) -> str:
    return ALIASES.get(name, name)


def build_matches(feed: dict, schedule: dict, expected_teams: set[str]) -> list[dict]:
    fixture_round = {
        (item["home"], item["away"]): item["round"]
        for item in schedule["fixtures"]
    }
    if len(fixture_round) != 380:
        raise AuditError("O calendário CBF precisa conter 380 confrontos únicos.")

    matches: list[dict] = []
    seen_ids: set[str] = set()
    seen_fixtures: set[tuple[str, str]] = set()
    appearances: Counter[str] = Counter()

    for event in feed["events"]:
        if event.get("season", {}).get("year") != 2026:
            continue
        competition = (event.get("competitions") or [{}])[0]
        status = competition.get("status", {}).get("type", {})
        if status.get("name") not in {"STATUS_FULL_TIME", "STATUS_FINAL"}:
            continue

        event_id = str(event.get("id", ""))
        if not event_id or event_id in seen_ids:
            raise AuditError(f"Partida sem ID ou ID duplicado: {event_id!r}.")
        seen_ids.add(event_id)

        competitors = competition.get("competitors", [])
        by_side = {team.get("homeAway"): team for team in competitors}
        if set(by_side) != {"home", "away"}:
            raise AuditError(f"Partida {event_id} sem mandante e visitante distintos.")
        home_team = canonical_team(by_side["home"]["team"]["displayName"])
        away_team = canonical_team(by_side["away"]["team"]["displayName"])
        if home_team not in expected_teams or away_team not in expected_teams:
            raise AuditError(
                f"Partida {event_id} inclui clube fora da Série A: "
                f"{home_team} x {away_team}."
            )
        if home_team == away_team:
            raise AuditError(f"Partida {event_id} tem o mesmo clube nos dois lados.")

        fixture = (home_team, away_team)
        if fixture not in fixture_round:
            raise AuditError(f"Confronto não encontrado na tabela básica da CBF: {fixture}.")
        if fixture in seen_fixtures:
            raise AuditError(f"Confronto duplicado no feed: {home_team} x {away_team}.")
        seen_fixtures.add(fixture)

        try:
            goals_home = int(by_side["home"]["score"])
            goals_away = int(by_side["away"]["score"])
        except (KeyError, TypeError, ValueError) as exc:
            raise AuditError(f"Placar inválido na partida {event_id}.") from exc
        if goals_home < 0 or goals_away < 0:
            raise AuditError(f"Placar negativo na partida {event_id}.")

        try:
            played_at = datetime.fromisoformat(event["date"].replace("Z", "+00:00"))
        except (KeyError, ValueError) as exc:
            raise AuditError(f"Data inválida na partida {event_id}.") from exc
        if played_at.tzinfo is None:
            raise AuditError(f"Data sem fuso horário na partida {event_id}.")
        local_date = played_at.astimezone(BR_TZ).date().isoformat()
        round_number = fixture_round[fixture]

        matches.append(
            {
                "id": event_id,
                "played_at": played_at.astimezone(timezone.utc).isoformat(),
                "date": local_date,
                "official_round": round_number,
                "home_team": home_team,
                "away_team": away_team,
                "home_goals": goals_home,
                "away_goals": goals_away,
            }
        )
        appearances[home_team] += 1
        appearances[away_team] += 1

    if not matches:
        raise AuditError("A fonte não retornou partidas encerradas.")
    if len(matches) != len(seen_fixtures) or any(
        appearances[team] > 38 for team in expected_teams
    ):
        raise AuditError("A auditoria de quantidade de jogos falhou.")
    return sorted(matches, key=lambda match: (match["played_at"], match["id"]))


def make_data(current: dict, matches: list[dict]) -> dict:
    expected_teams = set(current["teams"])
    by_team: dict[str, list[dict]] = defaultdict(list)
    for match in matches:
        by_team[match["home_team"]].append(
            {
                "match": match,
                "opponent": match["away_team"],
                "gf": match["home_goals"],
                "ga": match["away_goals"],
                "home": True,
            }
        )
        by_team[match["away_team"]].append(
            {
                "match": match,
                "opponent": match["home_team"],
                "gf": match["away_goals"],
                "ga": match["home_goals"],
                "home": False,
            }
        )

    result = json.loads(json.dumps(current))
    for team_name in expected_teams:
        records = sorted(
            by_team[team_name],
            key=lambda record: (record["match"]["played_at"], record["match"]["id"]),
        )
        points = [{
            "game": 0,
            "norm": 0,
            "official_points": 0,
            "date": None,
            "opponent": None,
            "gf": None,
            "ga": None,
            "home": None,
            "official_round": None,
        }]
        official_points = 0
        norm = 0
        previous_instant = None
        for number, record in enumerate(records, start=1):
            match = record["match"]
            instant = match["played_at"]
            if previous_instant and instant < previous_instant:
                raise AuditError(f"Cronologia fora de ordem para {team_name}.")
            previous_instant = instant

            gf, ga = record["gf"], record["ga"]
            official_delta = 3 if gf > ga else 1 if gf == ga else 0
            norm_delta = 2 if gf > ga else 0 if gf == ga else -1
            if norm_delta not in {-1, 0, 2}:
                raise AuditError(f"Variação de índice inválida para {team_name}.")
            official_points += official_delta
            norm += norm_delta
            if norm - points[-1]["norm"] not in {-1, 0, 2}:
                raise AuditError(f"Variação de índice inválida para {team_name}.")
            points.append(
                {
                    "game": number,
                    "norm": norm,
                    "official_points": official_points,
                    "date": match["date"],
                    "opponent": record["opponent"],
                    "gf": gf,
                    "ga": ga,
                    "home": record["home"],
                    "official_round": match["official_round"],
                }
            )

        if norm != official_points - len(records):
            raise AuditError(f"Pontos e índice final não fecham para {team_name}.")
        result["teams"][team_name].update(
            {
                "games": len(records),
                "officialPoints": official_points,
                "finalNorm": norm,
                "points": points,
            }
        )

    if set(by_team) != expected_teams:
        raise AuditError("O conjunto de participantes não corresponde às 20 equipes.")
    result["matchCount"] = len(matches)
    result["maxGames"] = max(len(by_team[name]) for name in expected_teams)
    result["lastDate"] = max(match["date"] for match in matches)
    result["source"] = "ESPN public JSON scoreboard; round numbers from CBF basic schedule"
    result["sourceUpdatedAt"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    return result


def main() -> None:
    current = json.loads(DATA_PATH.read_text(encoding="utf-8"))
    schedule = json.loads(FIXTURES_PATH.read_text(encoding="utf-8"))
    expected_teams = set(current.get("teams", {}))
    if len(expected_teams) != 20:
        raise AuditError("O JSON precisa conter exatamente os 20 clubes.")

    feed = fetch_feed()
    matches = build_matches(feed, schedule, expected_teams)
    candidate = make_data(current, matches)

    # A temporary provider outage or incomplete response must never erase valid data.
    if candidate["matchCount"] < current.get("matchCount", 0):
        raise AuditError(
            f"A fonte retornou {candidate['matchCount']} jogos, menos que os "
            f"{current['matchCount']} já publicados. JSON preservado."
        )

    candidate.pop("sourceUpdatedAt", None)
    current.pop("sourceUpdatedAt", None)
    if candidate == current:
        print(f"Sem alteração: {candidate['matchCount']} jogos encerrados.")
        return

    candidate["sourceUpdatedAt"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    fd, temp_name = tempfile.mkstemp(prefix="brasileirao-", suffix=".json", dir=DATA_PATH.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as output:
            json.dump(candidate, output, ensure_ascii=False, separators=(",", ":"))
            output.write("\n")
        os.replace(temp_name, DATA_PATH)
    finally:
        if os.path.exists(temp_name):
            os.unlink(temp_name)
    print(
        f"Atualizado: {candidate['matchCount']} jogos, dados até "
        f"{candidate['lastDate']}; auditorias aprovadas."
    )


if __name__ == "__main__":
    try:
        main()
    except AuditError as exc:
        raise SystemExit(f"AUDITORIA REPROVADA: {exc}") from exc
