"""Merge verified stadium_name values into data/teams.json (omit key when unknown)."""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TEAMS_PATH = ROOT / "data" / "teams.json"

# Documented / distinctive home football venues only (no generic placeholders).
STADIUM_NAMES: dict[str, str] = {
    "Martinsburg": "Cobourn Field at David M. Walker Stadium · Martinsburg, WV",
    "Morgantown": "Pony Lewis Field · Morgantown, WV",
    "Huntington": "Mitch Vingle Field · Huntington, WV",
    "Jefferson": "James C. Price Stadium · Charles Town, WV",
    "George Washington": "Tomlinson Stadium · Charleston, WV",
    "Wheeling Park": "Wheeling Park Stadium · Wheeling, WV",
    "University": "University High School Stadium · Morgantown, WV",
    "Spring Mills": "Cardinal Stadium · Falling Waters, WV",
    "Musselman": "Appleman Field · Inwood, WV",
    "Parkersburg": "Stadium Field · Parkersburg, WV",
    "Beckley": "Pete Culicerto Field at Van Meter Stadium · Beckley, WV",
    "Parkersburg South": "Erickson All-Sports Stadium · Parkersburg, WV",
    "Preston": "T.R. Whiteman Memorial Stadium · Kingwood, WV",
    "Cabell Midland": "Tom Harmon Field · Ona, WV",
    "Hurricane": "Hoops Family Fields · Hurricane, WV",
    "John Marshall": "Monarch Stadium · Glen Dale, WV",
    "Capital": "Capital High School Stadium · Charleston, WV",
    "Greenbrier East": "Spartan Stadium · Lewisburg, WV",
    "Spring Valley": "Timberwolf Stadium · Huntington, WV",
    "South Charleston": "Black Eagle Stadium · South Charleston, WV",
    "St. Albans": "Dick Reynolds Field · St. Albans, WV",
    "Bridgeport": "Wayne Jamison Field · Bridgeport, WV",
    "Nitro": "Larry Friend Field · Nitro, WV",
    "Winfield": "Wayne P. Holder Stadium · Winfield, WV",
    "Herbert Hoover": "Husky Stadium · Elkview, WV",
    "Fairmont Senior": "East-West Stadium · Fairmont, WV",
    "East Fairmont": "East-West Stadium · Fairmont, WV",
    "North Marion": "Husky Field · Farmington, WV",
    "Keyser": "Alumni Field · Keyser, WV",
    "Frankfort": "Falcon Stadium · Ridgeley, WV",
    "Weir": "Red Rider Stadium · Weirton, WV",
    "Wheeling Central": "Wheeling Island Stadium · Wheeling, WV",
    "Bluefield": "Mitchell Stadium · Bluefield, WV",
    "Independence": "Brushfork Stadium · Coal City, WV",
    "Chapmanville": "Larry Farley Field · Chapmanville, WV",
    "Williamstown": "Yellowjacket Stadium · Williamstown, WV",
    "Doddridge Co": "Doddridge County Complex · West Union, WV",
    "Greenbrier West": "Warrior Stadium · Charmco, WV",
    "Tyler Consolidated": "Tyler Consolidated High School Stadium · Sistersville, WV",
}


def main() -> None:
    raw = TEAMS_PATH.read_text(encoding="utf-8")
    data = json.loads(raw)
    applied = 0
    for team in data.get("teams", []):
        name = team.get("name")
        if name in STADIUM_NAMES:
            team["stadium_name"] = STADIUM_NAMES[name]
            applied += 1
        else:
            team.pop("stadium_name", None)

    # Rebuild file: keep top-level keys and one team object per line (matches existing style).
    out: list[str] = ["{"]
    out.append(f'  "_schema": {json.dumps(data["_schema"])},')
    if "_playoff_system_schema" in data:
        out.append(f'  "_playoff_system_schema": {json.dumps(data["_playoff_system_schema"])},')
    out.append(f'  "playoff_system": {json.dumps(data["playoff_system"])},')
    out.append('  "teams": [')
    teams = data["teams"]
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
    print(f"Applied stadium_name to {applied} of {len(teams)} teams.")


if __name__ == "__main__":
    main()
