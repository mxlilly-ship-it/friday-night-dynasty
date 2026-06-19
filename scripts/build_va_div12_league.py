#!/usr/bin/env python3
"""Build Virginia Div 1 & 2 league JSON from spreadsheet CSV (Ohio D5-style playoffs)."""

from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

from systems.league_metadata import league_metadata_from_config
from systems.playoff_systems import PLAYOFF_SYSTEMS

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CSV = Path(r"e:\Film Library\High School Game Film\INDY\2024\VA Div 1 2 File - OH.csv")
DESKTOP_OUT = Path.home() / "Desktop" / "va_div12_league.json"
DATA_OUT = ROOT / "data" / "va_div12_league.json"

# Disambiguate duplicate abbreviations in the source sheet.
_ABBREV_OVERRIDES: dict[str, str] = {
    "Northampton": "NHT",
    "Northwood": "NWD",
    "Greensville CO": "GSC",
    "Gate City": "GCT",
    "Bruton": "BRT",
    "Central Woodstock": "CWS",
    "Central Wise": "CWV",
    "Grayson Co": "GRYC",
    "Graham": "GRHM",
    "Martinsville": "MVL",
    "Marion": "MRN",
}


def _norm_team(name: str) -> str:
    return " ".join((name or "").strip().split())


def _community(raw: str) -> str:
    s = (raw or "").strip().lower().replace("_", "-")
    if s == "blue_collar":
        return "blue-collar"
    if s == "football_factory":
        return "football factory"
    return s or "suburban"


def row_to_team(row: dict[str, str]) -> dict:
    name = _norm_team(row.get("Team") or "")
    abbr = _ABBREV_OVERRIDES.get(name) or (row.get("Abbreviation") or "").strip()
    fg_raw = (row.get("facilities_grade") or "").strip()
    facilities = int(fg_raw) if fg_raw else 5
    return {
        "name": name,
        "nickname": (row.get("Mascot") or "").strip(),
        "abbreviation": abbr,
        "prestige": int(row.get("Prestige") or 5),
        "classification": (row.get("Classification") or "").strip(),
        "region": (row.get("Region") or "").strip(),
        "culture_grade": int(row.get("culture_grade") or 5),
        "booster_support": int(row.get("booster_support") or 5),
        "community": _community(row.get("community") or ""),
        "enrollment": int(row.get("enrollment") or 0),
        "facilities_grade": facilities,
    }


def build_league(csv_path: Path) -> dict:
    if not csv_path.is_file():
        raise SystemExit(f"CSV not found: {csv_path}")

    teams: list[dict] = []
    with csv_path.open(newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if not _norm_team(row.get("Team") or ""):
                continue
            teams.append(row_to_team(row))

    names = [t["name"] for t in teams]
    dupes = sorted({n for n in names if names.count(n) > 1})
    if dupes:
        raise SystemExit(f"Duplicate team names: {dupes}")

    by_class: dict[str, int] = {}
    by_class_region: dict[tuple[str, str], int] = {}
    for t in teams:
        cls = t["classification"]
        reg = t["region"]
        by_class[cls] = by_class.get(cls, 0) + 1
        by_class_region[(cls, reg)] = by_class_region.get((cls, reg), 0) + 1

    config = {
        "_schema": (
            "name, nickname, prestige (1-15), classification, region, "
            "culture_grade (1-10), booster_support (1-10), community, enrollment, "
            "facilities_grade; optional abbreviation, stadium_name, rivals"
        ),
        "_description": (
            "Virginia Divisions 1 & 2. Four regions (A–D) per class. Regular season: "
            "up to 8 in-region games + 2 out-of-region games (10 weeks). Playoffs: "
            "top 8 per region (regional quarterfinals → regional final), then Final Four "
            "and state championship — same structure as Ohio D5 (regional_8x4)."
        ),
        "league_id": "va_div12",
        "state": "Virginia (Div 1 & 2)",
        "email_pack": "oh",
        "playoff_system": "regional_8x4",
        "teams": teams,
    }

    meta = league_metadata_from_config(config)
    ps = PLAYOFF_SYSTEMS[config["playoff_system"]]

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
        "_team_counts_by_class_region": {
            f"{cls} / {reg}": n for (cls, reg), n in sorted(by_class_region.items())
        },
    }


def main() -> None:
    csv_path = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_CSV
    export = build_league(csv_path)
    text = json.dumps(export, indent=2, ensure_ascii=False) + "\n"

    DATA_OUT.write_text(text, encoding="utf-8")
    DESKTOP_OUT.write_text(text, encoding="utf-8")

    teams = export["teams"]
    print(f"Wrote {DESKTOP_OUT}")
    print(f"Wrote {DATA_OUT}")
    print(f"Teams: {len(teams)}")
    print("By class:", export["_team_counts_by_class"])
    print("Playoff system:", export["playoff_system"])


if __name__ == "__main__":
    main()
