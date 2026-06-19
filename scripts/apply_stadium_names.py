"""Merge stadium_name values from data/wv_stadiums.csv into data/teams.json."""
from __future__ import annotations

import csv
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TEAMS_PATH = ROOT / "data" / "teams.json"
STADIUMS_CSV = ROOT / "data" / "wv_stadiums.csv"


def load_stadium_names_from_csv(path: Path) -> dict[str, str]:
    names: dict[str, str] = {}
    with path.open(encoding="utf-8-sig", newline="") as f:
        reader = csv.reader(f)
        for row in reader:
            if len(row) < 2:
                continue
            team = row[0].strip()
            stadium = row[1].strip()
            if not team or team.lower() == "team":
                continue
            if not stadium:
                continue
            names[team] = stadium
    return names


def main() -> None:
    if not STADIUMS_CSV.is_file():
        raise SystemExit(f"Missing stadium CSV: {STADIUMS_CSV}")

    stadium_names = load_stadium_names_from_csv(STADIUMS_CSV)
    data = json.loads(TEAMS_PATH.read_text(encoding="utf-8"))
    teams = data.get("teams") or []

    applied = 0
    missing: list[str] = []
    for team in teams:
        name = str(team.get("name") or "").strip()
        if name in stadium_names:
            team["stadium_name"] = stadium_names[name]
            applied += 1
        else:
            team.pop("stadium_name", None)
            missing.append(name)

    out: list[str] = ["{"]
    out.append(f'  "_schema": {json.dumps(data["_schema"])},')
    if "_playoff_system_schema" in data:
        out.append(f'  "_playoff_system_schema": {json.dumps(data["_playoff_system_schema"])},')
    out.append(f'  "playoff_system": {json.dumps(data["playoff_system"])},')
    out.append('  "teams": [')
    for i, team in enumerate(teams):
        line = "    " + json.dumps(team, ensure_ascii=False)
        if i < len(teams) - 1:
            line += ","
        out.append(line)
        if i < len(teams) - 1:
            out.append("")
    out.append("  ]")
    out.append("}")
    out.append("")
    TEAMS_PATH.write_text("\n".join(out), encoding="utf-8")

    csv_only = sorted(set(stadium_names) - {str(t.get("name") or "").strip() for t in teams})
    print(f"Applied stadium_name to {applied} of {len(teams)} teams from {STADIUMS_CSV.name}.")
    if missing:
        print(f"No CSV row for {len(missing)} teams in teams.json: {', '.join(missing)}")
    if csv_only:
        print(f"CSV rows not used ({len(csv_only)}): {', '.join(csv_only)}")


if __name__ == "__main__":
    main()
