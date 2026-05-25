#!/usr/bin/env python3
"""Build data/wv_3class_league.json from the WV 3-Class spreadsheet CSV."""

from __future__ import annotations

import csv
import json
from pathlib import Path

from systems.league_metadata import league_metadata_from_config
from systems.playoff_systems import PLAYOFF_SYSTEMS

ROOT = Path(__file__).resolve().parents[1]
CSV_PATH = Path(r"c:\Users\mxlil\Downloads\WV 3 Class Game File - Sheet1.csv")
OUT_PATH = ROOT / "data" / "wv_3class_league.json"

# Disambiguate duplicate abbreviations from the sheet (John Marshall / James Monroe both JM, etc.)
_ABBREV_OVERRIDES: dict[str, str] = {
    "James Monroe": "JMON",
    "Lincoln": "LNCH",
}


def _community(raw: str) -> str:
    s = (raw or "").strip().lower().replace("_", "-")
    if s == "blue_collar":
        return "blue-collar"
    if s == "football_factory":
        return "football factory"
    return s or "suburban"


# CSV South has 8 / North has 6 for 3A; move Capital to North for 7×4 scheduling.
_3A_NORTH_FROM_SOUTH = frozenset({"Capital"})


def _rebalance_3a_regions(teams: list[dict]) -> None:
    for t in teams:
        if (t.get("classification") or "").strip() != "3A":
            continue
        if (t.get("name") or "").strip() in _3A_NORTH_FROM_SOUTH:
            t["region"] = "North"


def row_to_team(row: dict[str, str]) -> dict:
    name = (row.get("Team") or "").strip()
    nickname = (row.get("Mascot") or "").strip()
    abbr = _ABBREV_OVERRIDES.get(name) or (row.get("Abbreviation") or "").strip()
    return {
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


def main() -> None:
    if not CSV_PATH.is_file():
        raise SystemExit(f"CSV not found: {CSV_PATH}")

    teams: list[dict] = []
    with CSV_PATH.open(newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if not (row.get("Team") or "").strip():
                continue
            teams.append(row_to_team(row))

    by_class: dict[str, int] = {}
    for t in teams:
        c = t.get("classification") or "?"
        by_class[c] = by_class.get(c, 0) + 1

    # 3A: even 7 per region (28 total) so schedule template 4 yields 10 games (6 in-region + 4 cross).
    _rebalance_3a_regions(teams)

    config = {
        "_schema": (
            "name, nickname, prestige (1-15), classification (1A/2A/3A), region, "
            "culture_grade (1-10), booster_support (1-10), community, enrollment, facilities_grade; optional abbreviation"
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

    export = {
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
    }

    OUT_PATH.write_text(json.dumps(export, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Wrote {OUT_PATH} ({len(teams)} teams)")
    print("Counts by class:", by_class)


if __name__ == "__main__":
    main()
