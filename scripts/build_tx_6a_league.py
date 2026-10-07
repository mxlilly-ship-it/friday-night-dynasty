#!/usr/bin/env python3
"""Build data/tx_6a_league.json from the Texas 6A 2026-28 school list.

The spreadsheet has school, nickname, and UIL district only. Prestige,
community, facilities, culture, boosters, enrollment, stadiums, and rivals
are filled here. District number is the scheduling region.

Source workbook (not in git):
  Desktop/Screenshots/Texas_6A_FND_2026_28.xlsx
"""
from __future__ import annotations

import json
import zlib
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Tuple

from openpyxl import load_workbook

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_XLSX = Path(r"C:\Users\mxlil\Desktop\Screenshots\Texas_6A_FND_2026_28.xlsx")
OUT_PATH = ROOT / "data" / "tx_6a_league.json"

# Prestige 1-15. Unlisted 6A schools land at 7, with a small stable wobble.
PRESTIGE: Dict[str, int] = {
    "Duncanville": 15,
    "Galena Park North Shore": 15,
    "Austin Westlake": 15,
    "Allen": 14,
    "Southlake Carroll": 14,
    "Austin Lake Travis": 14,
    "Denton Guyer": 14,
    "Aledo": 14,
    "North Crowley": 14,
    "Katy": 14,
    "Dallas Jesuit": 13,
    "Prosper": 13,
    "Humble Atascocita": 13,
    "Euless Trinity": 13,
    "Longview": 13,
    "Odessa Permian": 13,
    "Spring Westfield": 13,
    "Klein Cain": 13,
    "Katy Paetow": 13,
    "Alvin Shadow Creek": 13,
    "Austin Vandegrift": 13,
    "Conroe The Woodlands": 13,
    "Coppell": 12,
    "Rockwall": 12,
    "Rockwall Heath": 12,
    "Tyler Legacy": 12,
    "South Grand Prairie": 12,
    "Spring Dekaney": 12,
    "Katy Tompkins": 12,
    "Katy Cinco Ranch": 12,
    "Katy Seven Lakes": 12,
    "Bridgeland": 12,
    "Cypress Ranch": 12,
    "Conroe Woodlands College Park": 12,
    "Houston Strake Jesuit": 12,
    "Houston Memorial": 12,
    "Dripping Springs": 12,
    "Humble Summer Creek": 12,
    "Cibolo Steele": 12,
    "Converse Judson": 12,
    "Fort Bend Ridge Point": 12,
    "Manvel": 12,
    "Mount Belvieu Barbers Hill": 12,
    "Lewisville Hebron": 11,
    "Lewisville Flower Mound": 11,
    "Lewisville Marcus": 11,
    "Plano": 11,
    "Plano East": 11,
    "Plano West": 11,
    "Mansfield": 11,
    "Pearland": 11,
    "Houston Stratford": 11,
    "Fort Bend Hightower": 11,
    "Richmond Foster": 11,
    "Lamar Fulshear": 11,
    "Crosby": 11,
    "Waco Midway": 11,
    "Midland Lee": 11,
    "Cedar Park": 11,
    "Leander": 11,
    "Comal Pieper": 11,
    "Northside Harlan": 11,
    "Prosper Walnut Grove": 11,
    "Prosper Rock Hill": 11,
    "Denton Braswell": 11,
    "Keller": 10,
    "Northwest Eaton": 10,
    "McKinney": 10,
    "McKinney Boyd": 10,
    "Forney": 10,
    "Mesquite Horn": 10,
    "Crowley": 10,
    "Waxahachie": 10,
    "Red Oak": 10,
    "Klein Collins": 10,
    "Klein Oak": 10,
    "Tomball Memorial": 10,
    "Cypress Woods": 10,
    "Cypress Park": 10,
    "League City Clear Springs": 10,
    "League City Clear Creek": 10,
    "Humble Kingwood": 10,
    "Fort Bend Travis": 10,
    "Fort Bend Clements": 10,
    "Katy Taylor": 10,
    "Katy Jordan": 10,
    "Austin Bowie": 10,
    "Buda Hays": 10,
    "Round Rock": 10,
    "Schertz Clemens": 10,
    "San Antonio Reagan": 10,
    "Edinburg North": 10,
    "Edinburg Vela": 10,
    "Harlingen": 10,
    "PSJA North": 10,
    "El Paso Eastwood": 10,
    "El Paso Franklin": 9,
    "El Paso Eastlake": 9,
    "El Paso Pebble Hills": 9,
    "Odessa": 9,
    "Arlington Martin": 9,
    "Weatherford": 9,
    "Northwest": 9,
    "Little Elm": 9,
    "Princeton": 9,
    "Richardson Lake Highlands": 9,
    "Richardson Pearce": 9,
    "Wylie East": 9,
    "North Forney": 9,
    "Royse City": 9,
    "Mansfield Lake Ridge": 9,
    "Lake Belton": 9,
    "Conroe Grand Oaks": 9,
    "Conroe Oak Ridge": 9,
    "Klein": 9,
    "Magnolia": 9,
    "Magnolia West": 9,
    "Tomball": 9,
    "Cypress Creek": 9,
    "Jersey Village": 9,
    "League City Clear Falls": 9,
    "Houston Clear Lake": 9,
    "Friendswood Clear Brook": 9,
    "Alvin": 9,
    "Pearland Dawson": 9,
    "Houston Heights": 9,
    "Houston Lamar": 9,
    "Fort Bend Austin": 9,
    "Fort Bend Bush": 9,
    "Fort Bend Elkins": 9,
    "Richmond George Ranch": 9,
    "Cedar Park Vista Ridge": 9,
    "Georgetown East View": 9,
    "Leander Rouse": 9,
    "Hutto": 9,
    "Round Rock Cedar Ridge": 9,
    "Buda Johnson": 9,
    "Comal Canyon": 9,
    "Northside Brennan": 9,
    "Northside O'Connor": 9,
    "Laredo United": 9,
    "San Antonio Southwest": 9,
    "Southwest Legacy": 9,
}

FACTORY = {
    "Duncanville",
    "Galena Park North Shore",
    "Austin Westlake",
    "Allen",
    "Southlake Carroll",
    "Austin Lake Travis",
    "Denton Guyer",
    "Aledo",
    "North Crowley",
    "Katy",
    "Odessa Permian",
    "Spring Westfield",
    "Dallas Jesuit",
    "Humble Atascocita",
}

AFFLUENT = {
    "Coppell",
    "Plano",
    "Plano East",
    "Plano West",
    "Houston Memorial",
    "Houston Stratford",
    "Houston Bellaire",
    "Conroe The Woodlands",
    "Conroe Woodlands College Park",
    "Katy Cinco Ranch",
    "Katy Seven Lakes",
    "Katy Tompkins",
    "Katy Jordan",
    "Bridgeland",
    "Austin Vandegrift",
    "Dripping Springs",
    "Lewisville Flower Mound",
    "Lewisville Hebron",
    "Lewisville Marcus",
    "Rockwall",
    "Rockwall Heath",
    "Prosper",
    "Prosper Rock Hill",
    "Prosper Walnut Grove",
    "Humble Kingwood",
    "Friendswood Clear Brook",
    "Houston Clear Lake",
    "League City Clear Creek",
    "League City Clear Falls",
    "League City Clear Springs",
    "Houston Strake Jesuit",
    "Southlake Carroll",
    "Allen",
    "Austin Westlake",
    "Austin Lake Travis",
    "Cedar Park",
    "Round Rock Westwood",
    "Fort Bend Clements",
    "Fort Bend Ridge Point",
}

BLUE_COLLAR = {
    "Houston Aldine",
    "Channelview",
    "Deer Park",
    "Pasadena Dobie",
    "Pasadena Memorial",
    "Pasadena Rayburn",
    "Alief Elsik",
    "Alief Hastings",
    "Alief Taylor",
    "Spring",
    "Spring Dekaney",
    "Spring Westfield",
    "Crosby",
    "Sheldon King",
    "Midland",
    "Midland Lee",
    "Odessa",
    "La Joya",
    "Weslaco",
    "Pharr-San Juan-Alamo",
    "PSJA North",
    "Brownsville Veterans Memorial",
    "San Benito",
    "Harlingen",
    "Los Fresnos",
    "Del Rio",
    "Eagle Pass",
    "Laredo Alexander",
    "Laredo Johnson",
    "Laredo United",
    "Laredo United South",
    "Galena Park North Shore",
    "Houston Eisenhower",
    "Houston Nimitz",
    "Houston MacArthur",
    "Houston Benjamin Davis",
}

URBAN_PREFIXES = (
    "Houston ",
    "Dallas ",
    "San Antonio ",
    "El Paso ",
    "Laredo ",
    "Irving",
    "Fort Worth ",
)
URBAN_EXACT = {"Austin", "Odessa", "Midland", "Waco Midway", "Harlingen", "Edinburg", "Brownsville Veterans Memorial"}

RURAL = {
    "Granbury",
    "Weatherford",
    "Royse City",
    "Willis",
    "Waller",
    "Hutto",
    "Del Valle",
    "San Marcos",
    "Copperas Cove",
    "Los Fresnos",
    "Eagle Pass",
}

ENROLLMENT: Dict[str, int] = {
    "Allen": 6900,
    "Plano East": 5400,
    "Plano": 4500,
    "Conroe The Woodlands": 4300,
    "Conroe": 4000,
    "Dallas Skyline": 4600,
    "Alief Elsik": 4200,
    "Spring Westfield": 4000,
    "Klein": 3800,
    "Cy-Fair": 3600,
    "Katy": 3700,
    "Duncanville": 4300,
    "Galena Park North Shore": 4500,
    "Humble Atascocita": 4200,
    "Austin Westlake": 2800,
    "Austin Lake Travis": 3200,
    "Southlake Carroll": 3400,
    "Coppell": 3100,
    "Dallas Jesuit": 1100,
    "Houston Strake Jesuit": 1100,
}

STADIUM: Dict[str, str] = {
    "Allen": "Eagle Stadium",
    "Southlake Carroll": "Dragon Stadium",
    "Odessa Permian": "Ratliff Stadium",
    "Odessa": "Ratliff Stadium",
    "Austin Westlake": "Chaparral Stadium",
    "Austin Lake Travis": "Cavalier Stadium",
    "Duncanville": "Panther Stadium",
    "Katy": "Legacy Stadium",
    "Katy Cinco Ranch": "Legacy Stadium",
    "Katy Seven Lakes": "Legacy Stadium",
    "Katy Tompkins": "Legacy Stadium",
    "Katy Taylor": "Legacy Stadium",
    "Katy Mayde Creek": "Legacy Stadium",
    "Katy Morton Ranch": "Legacy Stadium",
    "Katy Jordan": "Legacy Stadium",
    "Katy Paetow": "Legacy Stadium",
    "Galena Park North Shore": "Galena Park ISD Stadium",
    "Denton Guyer": "John Clark Stadium",
    "Aledo": "Bearcat Stadium",
}

# Famous pairs. Both schools get each other when both are in the file.
RIVAL_PAIRS: List[Tuple[str, str]] = [
    ("Midland", "Midland Lee"),
    ("Odessa", "Odessa Permian"),
    ("Odessa Permian", "Midland Lee"),
    ("Allen", "Plano East"),
    ("Allen", "Prosper"),
    ("Southlake Carroll", "Denton Guyer"),
    ("Austin Westlake", "Austin Lake Travis"),
    ("Katy", "Katy Cinco Ranch"),
    ("Katy", "Katy Tompkins"),
    ("Duncanville", "North Crowley"),
    ("Duncanville", "Galena Park North Shore"),
    ("Conroe The Woodlands", "Conroe Woodlands College Park"),
    ("Rockwall", "Rockwall Heath"),
    ("Longview", "Tyler Legacy"),
    ("Plano", "Plano East"),
    ("Plano East", "Plano West"),
    ("Lewisville Hebron", "Lewisville Flower Mound"),
    ("Denton Guyer", "Denton Braswell"),
    ("Spring Dekaney", "Spring Westfield"),
    ("Humble Atascocita", "Humble Summer Creek"),
    ("Galena Park North Shore", "Humble Atascocita"),
    ("Pearland", "Alvin Shadow Creek"),
    ("League City Clear Creek", "League City Clear Springs"),
    ("Laredo United", "Laredo United South"),
    ("El Paso Eastwood", "El Paso Franklin"),
    ("Dallas Jesuit", "Houston Strake Jesuit"),
    ("Austin Vandegrift", "Cedar Park"),
    ("Cibolo Steele", "Converse Judson"),
    ("Euless Trinity", "South Grand Prairie"),
]


def _stable(name: str) -> int:
    return zlib.adler32(name.encode("utf-8"))


def _community(name: str) -> str:
    if name in FACTORY:
        return "football factory"
    if name in AFFLUENT:
        return "affluent"
    if name in BLUE_COLLAR:
        return "blue-collar"
    if name in RURAL:
        return "rural"
    if name in URBAN_EXACT or name.startswith(URBAN_PREFIXES):
        return "urban"
    return "suburban"


def _prestige(name: str) -> int:
    if name in PRESTIGE:
        return PRESTIGE[name]
    wobble = (_stable(name) % 3) - 1  # -1, 0, +1
    return max(5, min(9, 7 + wobble))


def _grades(prestige: int, community: str) -> Tuple[int, int, int]:
    base = max(3, min(10, round(prestige * 10 / 15)))
    culture = facilities = boosters = base
    if community == "affluent":
        facilities = min(10, base + 1)
        boosters = min(10, base + 1)
    elif community == "football factory":
        facilities = min(10, base + 1)
        culture = min(10, base + 1)
        boosters = min(10, base + 1)
    elif community == "blue-collar":
        facilities = max(3, base - 1)
        culture = min(10, base + 1)
    elif community == "urban":
        facilities = max(3, base - 1)
    elif community == "rural":
        facilities = max(3, base - 1)
        culture = min(10, base + 1)
        boosters = max(3, base - 1)
    return culture, boosters, facilities


def _enrollment(name: str) -> int:
    if name in ENROLLMENT:
        return ENROLLMENT[name]
    return 2300 + (_stable(name) % 1400)


def _abbr(name: str, used: set) -> str:
    parts = [p for p in name.replace("-", " ").replace("'", "").split() if p]
    raw = "".join(p[0] for p in parts[-3:]).upper()
    if len(raw) < 2:
        raw = (parts[-1][:3] if parts else "TX").upper()
    raw = raw[:4]
    candidate = raw
    n = 2
    while candidate in used:
        candidate = (raw[:3] + str(n))[:4]
        n += 1
    used.add(candidate)
    return candidate


def _load_rows(path: Path) -> List[Tuple[str, str, int]]:
    wb = load_workbook(path, read_only=True, data_only=True)
    ws = wb["Texas 6A Schools"]
    rows: List[Tuple[str, str, int]] = []
    for i, row in enumerate(ws.iter_rows(values_only=True)):
        if i == 0:
            continue
        name = str(row[0]).strip()
        nick = str(row[1]).strip()
        if nick == "Oilres":
            nick = "Oilers"
        rows.append((name, nick, int(row[2])))
    return rows


def build(path: Path) -> dict:
    rows = _load_rows(path)
    by_district: Dict[int, List[str]] = defaultdict(list)
    for name, _nick, dist in rows:
        by_district[dist].append(name)

    manual: Dict[str, List[str]] = defaultdict(list)
    names = {n for n, _, _ in rows}
    for a, b in RIVAL_PAIRS:
        if a in names and b in names:
            manual[a].append(b)
            manual[b].append(a)

    used_abbr: set = set()
    teams = []
    for name, nick, dist in rows:
        prestige = _prestige(name)
        community = _community(name)
        culture, boosters, facilities = _grades(prestige, community)
        mates = [m for m in by_district[dist] if m != name]
        rivals: List[str] = []
        for rival in manual[name] + mates:
            if rival not in rivals:
                rivals.append(rival)
            if len(rivals) >= 3:
                break
        stadium = STADIUM.get(name) or f"{nick} Stadium"
        teams.append(
            {
                "name": name,
                "nickname": nick,
                "abbreviation": _abbr(name, used_abbr),
                "prestige": prestige,
                "classification": "6A",
                "region": f"District {dist}",
                "culture_grade": culture,
                "booster_support": boosters,
                "community": community,
                "enrollment": _enrollment(name),
                "facilities_grade": facilities,
                "stadium_name": stadium,
                "rivals": rivals,
            }
        )

    return {
        "_schema": "name, nickname, prestige (1-15), classification, region (UIL district), culture_grade, booster_support, community, enrollment, facilities_grade, abbreviation, stadium_name, rivals",
        "_description": (
            "Texas UIL 6A, 2026-28 alignment. 249 schools, 32 districts. "
            "Each district plays a round-robin, then non-district games are added until every team has 10. "
            "Playoffs are the top 64 teams in 6A by wins, then point differential (top64). "
            "Prestige, facilities, and community are estimates from program reputation, not official UIL ratings."
        ),
        "league_id": "tx_6a",
        "state": "Texas 6A",
        "email_pack": "fnd",
        "playoff_system": "top64",
        "teams": teams,
    }


def main() -> None:
    data = build(DEFAULT_XLSX)
    OUT_PATH.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    from collections import Counter

    pres = Counter(t["prestige"] for t in data["teams"])
    print(f"wrote {OUT_PATH} teams={len(data['teams'])}")
    print("prestige", dict(sorted(pres.items())))


if __name__ == "__main__":
    main()
