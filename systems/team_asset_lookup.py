"""Map normalized filename stems to canonical team names (from teams.json)."""

from __future__ import annotations

from typing import Dict, Optional

from systems.teams_loader import load_teams_from_json


def _norm_key(s: str) -> str:
    return "".join(c for c in str(s or "").strip().lower() if c.isalnum())


def team_asset_name_lookup(path: Optional[str] = None) -> Dict[str, str]:
    """
    Normalized team name or abbreviation -> canonical ``name`` from league JSON.
    Used for default logo filenames (e.g. ``HNT.png`` or ``Huntington.png``).
    """
    out: Dict[str, str] = {}
    for cfg in load_teams_from_json(path):
        if not isinstance(cfg, dict):
            continue
        name = str(cfg.get("name") or "").strip()
        if not name:
            continue
        nk = _norm_key(name)
        if nk:
            out[nk] = name
        abbr = str(cfg.get("abbreviation") or "").strip()
        if abbr:
            ak = _norm_key(abbr)
            if ak:
                out[ak] = name
    return out
