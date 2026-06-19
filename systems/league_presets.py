"""
Built-in league JSON presets (not the default teams file).

Each preset points at a file under ``data/``. The new-save UI lists these via
``/league-presets`` and loads full config from ``/league-presets/{id}``.
"""

from __future__ import annotations

import json
import os
from typing import Any, Dict, List, Optional

from systems.win_path_io import open_text_with_path_fallback, path_exists_any

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

LEAGUE_PRESETS: List[Dict[str, str]] = [
    {
        "id": "wv",
        "label": "West Virginia (archived)",
        "description": "Original 108-school WV league — 8-team playoff per class.",
        "filename": "wv_league.json",
    },
    {
        "id": "wv_3class",
        "label": "West Virginia 3-Class",
        "description": "1A / 2A / 3A — 16-team playoff per class (1-16 seeding, no regional brackets).",
        "filename": "wv_3class_league.json",
    },
]


def _data_path(filename: str) -> str:
    return os.path.join(_PROJECT_ROOT, "data", filename)


def list_league_presets() -> List[Dict[str, str]]:
    """Metadata for selectable league bundles (files must exist on disk)."""
    out: List[Dict[str, str]] = []
    for p in LEAGUE_PRESETS:
        path = _data_path(p["filename"])
        if path_exists_any(path):
            out.append(
                {
                    "id": p["id"],
                    "label": p["label"],
                    "description": p.get("description", ""),
                }
            )
    return out


def load_league_preset(preset_id: str) -> Optional[Dict[str, Any]]:
    """Load full league JSON for a preset id, or None if unknown / missing."""
    sid = (preset_id or "").strip().lower()
    for p in LEAGUE_PRESETS:
        if p["id"].lower() != sid:
            continue
        path = os.path.abspath(_data_path(p["filename"]))
        if not path_exists_any(path):
            return None
        with open_text_with_path_fallback(path, "r") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else None
    return None
