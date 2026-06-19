#!/usr/bin/env python3
"""
Copy WV / FND school crests from the master Game Logos folder into data/logos/
and refresh any user-uploaded overrides under saves/*/_logos/.

Run after updating images in your Game Logos folder:

  python scripts/sync_wv_team_logos.py
  python scripts/sync_wv_team_logos.py --all-teams
"""
from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from backend.data_paths import default_logo_import_source, default_logos_dir, saves_base_dir  # noqa: E402
from backend.services.league_service import (  # noqa: E402
    _LOGO_EXTENSIONS,
    _safe_logo_name,
)
from import_default_logos import _match_stem  # noqa: E402
from systems.team_asset_lookup import team_asset_name_lookup  # noqa: E402

# Schools that share names with the WV Game Logos folder (user-requested set).
WV_NAMED_TEAMS = [
    "Huntington",
    "Morgantown",
    "Parkersburg",
    "Nitro",
    "St. Albans",
    "Beckley",
    "Oak Hill",
    "Elkins",
    "Ripley",
    "Grafton",
    "Shady Spring",
    "Winfield",
]


def _resolve_source_file(src_dir: Path, team: str, team_names: list[str], lookup: dict[str, str]) -> Path | None:
    safe = _safe_logo_name(team)
    for path in sorted(src_dir.iterdir()):
        if not path.is_file() or path.suffix.lower() not in _LOGO_EXTENSIONS:
            continue
        if _match_stem(path.stem, team_names, lookup) == team:
            return path
        if path.stem == team or path.stem == safe:
            return path
    return None


def _copy_team_logo(src_file: Path, team: str, dest_dir: Path) -> Path:
    dest = dest_dir / f"{_safe_logo_name(team)}{src_file.suffix.lower()}"
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src_file, dest)
    return dest


def main() -> None:
    parser = argparse.ArgumentParser(description="Sync team logos from Game Logos folder")
    parser.add_argument(
        "--source",
        type=Path,
        help="Logo folder (default: data/game_logos_source.txt or Desktop Game Logos)",
    )
    parser.add_argument(
        "--all-teams",
        action="store_true",
        help="Sync every school in data/teams.json, not only the WV-named list",
    )
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    src = args.source
    if src is None:
        configured = default_logo_import_source()
        if not configured:
            raise SystemExit(
                "No logo source folder. Set data/game_logos_source.txt or pass --source."
            )
        src = Path(configured)
    src = src.expanduser().resolve()
    if not src.is_dir():
        raise SystemExit(f"Not a directory: {src}")

    lookup = team_asset_name_lookup()
    team_names = sorted(set(lookup.values()))
    targets = team_names if args.all_teams else [t for t in WV_NAMED_TEAMS if t in team_names]

    out_dir = Path(default_logos_dir())
    user_logo_dirs = sorted(Path(saves_base_dir()).glob("*/_logos"))

    print(f"Source: {src}")
    print(f"Default logos: {out_dir}")
    print(f"User override dirs: {len(user_logo_dirs)}")

    copied = 0
    missing: list[str] = []
    for team in targets:
        src_file = _resolve_source_file(src, team, team_names, lookup)
        if not src_file:
            missing.append(team)
            print(f"  missing source for {team}")
            continue
        dests = [out_dir, *user_logo_dirs]
        for dest_dir in dests:
            dest = dest_dir / f"{_safe_logo_name(team)}{src_file.suffix.lower()}"
            if args.dry_run:
                print(f"  {src_file.name} -> {dest}")
            else:
                _copy_team_logo(src_file, team, dest_dir)
        copied += 1
        if not args.dry_run:
            print(f"  {team} <- {src_file.name}")

    print(f"\nDone: {copied} team(s) synced, {len(missing)} missing from source.")
    if missing:
        print("Missing:", ", ".join(missing))
    if copied and not args.dry_run:
        print("Restart the API if it is running.")


if __name__ == "__main__":
    main()
