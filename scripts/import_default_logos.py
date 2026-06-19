#!/usr/bin/env python3
"""
Copy logo images from a folder into data/logos/ for built-in default crests.

Does not generate images — point this at your existing logo folder.

Filenames are matched to schools by team name or abbreviation from data/teams.json
(e.g. Huntington.png, HNT.png, huntington_logo.webp).

Usage:
  python scripts/import_default_logos.py "PATH\\TO\\YOUR\\LOGO\\FOLDER"

Or sync the WV-named schools from data/game_logos_source.txt:

  python scripts/sync_wv_team_logos.py
"""
from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.services.league_service import (  # noqa: E402
    _LOGO_EXTENSIONS,
    _safe_logo_name,
    _stem_variants_for_logo_match,
    match_logo_filename_to_team,
)
from systems.team_asset_lookup import team_asset_name_lookup  # noqa: E402

OUT_DIR = ROOT / "data" / "logos"

# Filename stem in source folder -> canonical team name (typos / alternate labels).
FILENAME_ALIASES: dict[str, str] = {
    "cannonsburg": "Canonsburg",
    "prestonburg": "Prestonsburg",
    "ripley east": "Ripley County",
    "paden": "Paden City Ridge",
}


def _match_stem(stem: str, team_names: list[str], lookup: dict[str, str]) -> str | None:
    alias = FILENAME_ALIASES.get(stem.strip().lower())
    if alias and alias in team_names:
        return alias
    team = match_logo_filename_to_team(team_names, stem)
    if team:
        return team
    for variant in _stem_variants_for_logo_match(stem):
        key = "".join(c for c in variant.lower() if c.isalnum())
        if key and key in lookup:
            return lookup[key]
    return None


def main() -> None:
    parser = argparse.ArgumentParser(description="Import default team logos into data/logos/")
    parser.add_argument("source", type=Path, help="Folder containing logo image files")
    parser.add_argument("--dry-run", action="store_true", help="Print matches without copying")
    args = parser.parse_args()

    src = args.source.expanduser().resolve()
    if not src.is_dir():
        raise SystemExit(f"Not a directory: {src}")

    lookup = team_asset_name_lookup()
    team_names = sorted(set(lookup.values()))
    if not team_names:
        raise SystemExit("No teams in data/teams.json")

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    matched = 0
    skipped = 0
    for path in sorted(src.iterdir()):
        if not path.is_file():
            continue
        if path.suffix.lower() not in _LOGO_EXTENSIONS:
            continue
        stem = path.stem
        team = _match_stem(stem, team_names, lookup)
        if not team:
            print(f"  skip (no match): {path.name}")
            skipped += 1
            continue
        dest = OUT_DIR / f"{_safe_logo_name(team)}{path.suffix.lower()}"
        if args.dry_run:
            print(f"  {path.name} -> {dest.name} ({team})")
        else:
            shutil.copy2(path, dest)
            print(f"  {path.name} -> {dest.name}")
        matched += 1

    print(f"\nDone: {matched} matched, {skipped} skipped, {len(team_names)} teams in league.")
    if matched and not args.dry_run:
        print(f"Default logos folder: {OUT_DIR}")
        print("Restart the API if it is running so new files are served.")


if __name__ == "__main__":
    main()
