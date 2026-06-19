#!/usr/bin/env python3
"""Build WV 3-class league JSON from spreadsheet CSV + stadium names from data/wv_stadiums.csv."""

from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

from systems.league_metadata import league_metadata_from_config
from systems.playoff_systems import PLAYOFF_SYSTEMS

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CSV = Path(r"e:\Film Library\High School Game Film\INDY\2024\WV 3 Class Game File - Sheet1.csv")
STADIUMS_CSV = ROOT / "data" / "wv_stadiums.csv"
OUT_PATH = ROOT / "data" / "wv_3class_league.json"
DESKTOP_OUT = Path.home() / "Desktop" / "wv_3class_league.json"

# Disambiguate duplicate abbreviations from the sheet (John Marshall / James Monroe both JM, etc.)
_ABBREV_OVERRIDES: dict[str, str] = {
    "James Monroe": "JMON",
    "Lincoln": "LNCH",
}

# CSV South has 8 / North has 6 for 3A; move Capital to North for 7×4 scheduling.
_3A_NORTH_FROM_SOUTH = frozenset({"Capital"})


def _norm_team(name: str) -> str:
    return " ".join((name or "").strip().split())


def load_stadium_names(path: Path) -> dict[str, str]:
    """Team name -> stadium_name (keys normalized)."""
    names: dict[str, str] = {}
    with path.open(encoding="utf-8-sig", newline="") as f:
        reader = csv.reader(f)
        for row in reader:
            if len(row) < 2:
                continue
            team = _norm_team(row[0])
            stadium = (row[1] or "").strip()
            if not team or team.lower() == "team" or not stadium:
                continue
            names[team] = stadium
    return names


def _community(raw: str) -> str:
    s = (raw or "").strip().lower().replace("_", "-")
    if s == "blue_collar":
        return "blue-collar"
    if s == "football_factory":
        return "football factory"
    return s or "suburban"


def _rebalance_3a_regions(teams: list[dict]) -> None:
    for t in teams:
        if (t.get("classification") or "").strip() != "3A":
            continue
        if (t.get("name") or "").strip() in _3A_NORTH_FROM_SOUTH:
            t["region"] = "North"


def row_to_team(row: dict[str, str], stadium_names: dict[str, str]) -> dict:
    name = _norm_team(row.get("Team") or "")
    nickname = (row.get("Mascot") or "").strip()
    abbr = _ABBREV_OVERRIDES.get(name) or (row.get("Abbreviation") or "").strip()
    team: dict = {
        "name": name,
        "nickname": nickname,
        "abbreviation": abbr,
        "prestige": int(row.get("Prestige") or 5),
        "classification": (row.get("Classification") or "").strip(),
        "region": (row.get("Region") or "").strip(),
        "culture_grade": int(row.get("culture_grade") or 5),
        "booster_support": int(row.get("booster_support") or 5),
        "community": _community(row.get("community") or ""),
        "enrollment": int(row.get("enrollment") or 0),
        "facilities_grade": int(row.get("facilities_grade") or 5),
    }
    stadium = stadium_names.get(name)
    if stadium:
        team["stadium_name"] = stadium
    return team


def build_league(csv_path: Path) -> dict:
    if not csv_path.is_file():
        raise SystemExit(f"CSV not found: {csv_path}")
    if not STADIUMS_CSV.is_file():
        raise SystemExit(f"Stadium CSV not found: {STADIUMS_CSV}")

    stadium_names = load_stadium_names(STADIUMS_CSV)
    teams: list[dict] = []
    with csv_path.open(newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if not _norm_team(row.get("Team") or ""):
                continue
            teams.append(row_to_team(row, stadium_names))

    _rebalance_3a_regions(teams)

    by_class: dict[str, int] = {}
    for t in teams:
        c = t.get("classification") or "?"
        by_class[c] = by_class.get(c, 0) + 1

    missing_stadium = sorted(t["name"] for t in teams if not t.get("stadium_name"))
    if missing_stadium:
        print(f"Warning: {len(missing_stadium)} teams without stadium_name:")
        for n in missing_stadium:
            print(f"  - {n}")

    config = {
        "_schema": (
            "name, nickname, prestige (1-15), classification (1A/2A/3A), region, "
            "culture_grade (1-10), booster_support (1-10), community, enrollment, "
            "facilities_grade; optional abbreviation, stadium_name, rivals"
        ),
        "_description": "West Virginia 3-class system (1A, 2A, 3A). Sixteen-team statewide bracket per class (1-16 seeding).",
        "league_id": "wv_3class",
        "state": "West Virginia (3-Class)",
        "email_pack": "wv",
        "playoff_system": "wv16",
        "teams": teams,
    }

    meta = league_metadata_from_config(config)
    playoff_id = config["playoff_system"]
    ps = PLAYOFF_SYSTEMS[playoff_id]

    return {
        **config,
        "league_id": meta["league_id"],
        "state": meta["state"],
        "email_pack": meta["email_pack"],
        "playoff_system_config": {
            "id": ps.id,
            "label": ps.label,
            "description": ps.description,
            "bracket_size": ps.bracket_size,
            "per_classification": ps.per_classification,
            "min_teams": ps.min_teams,
            "seeding_mode": ps.seeding_mode,
            "regions_per_class": ps.regions_per_class,
            "teams_per_region": ps.teams_per_region,
        },
        "_team_counts_by_class": by_class,
        "_stadium_names_matched": sum(1 for t in teams if t.get("stadium_name")),
    }


def main() -> None:
    csv_path = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_CSV
    export = build_league(csv_path)
    text = json.dumps(export, indent=2, ensure_ascii=False) + "\n"

    OUT_PATH.write_text(text, encoding="utf-8")
    DESKTOP_OUT.write_text(text, encoding="utf-8")

    teams = export["teams"]
    matched = export.pop("_stadium_names_matched", 0)
    print(f"Wrote {OUT_PATH} ({len(teams)} teams)")
    print(f"Wrote {DESKTOP_OUT}")
    print(f"Stadium names matched: {matched}/{len(teams)}")
    print("Counts by class:", export["_team_counts_by_class"])


if __name__ == "__main__":
    main()
