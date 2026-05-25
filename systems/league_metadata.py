"""
League identity metadata (US state / league id) carried in teams JSON and save state.

Top-level keys on the league JSON (alongside ``playoff_system`` and ``teams``):

- ``state`` — display name, e.g. ``"West Virginia"``
- ``league_id`` — short stable id, e.g. ``"wv"`` (defaults to ``playoff_system``)
- ``email_pack`` — which coach-inbox starter templates to use (defaults to ``league_id``)

Stamped onto ``league_save.json`` when a dynasty is created; legacy saves are
backfilled on load from ``playoff_system`` when these fields are missing.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from systems.playoff_systems import DEFAULT_PLAYOFF_SYSTEM_ID, ensure_playoff_system_in_state
from systems.teams_loader import playoff_system_id_from_config

DEFAULT_LEAGUE_ID = DEFAULT_PLAYOFF_SYSTEM_ID
DEFAULT_STATE_NAME = "West Virginia"
DEFAULT_EMAIL_PACK = DEFAULT_PLAYOFF_SYSTEM_ID

# playoff_system id -> (league_id, state display name, email_pack) when JSON omits fields
_PLAYOFF_DEFAULTS: Dict[str, tuple[str, str, str]] = {
    "wv": ("wv", "West Virginia", "wv"),
    "wv16": ("wv_3class", "West Virginia (3-Class)", "wv"),
    "oh": ("oh_d5", "Ohio", "oh"),
    "oh_d5": ("oh_d5", "Ohio", "oh"),
}


def _clean_str(value: Any) -> Optional[str]:
    if value is None:
        return None
    s = str(value).strip()
    return s if s else None


def league_metadata_from_config(config: Optional[Dict[str, Any]]) -> Dict[str, str]:
    """Read league identity from a teams/league JSON dict."""
    if not isinstance(config, dict):
        config = {}
    playoff_id = playoff_system_id_from_config(config)
    defaults = _PLAYOFF_DEFAULTS.get(playoff_id, (playoff_id, playoff_id.upper(), playoff_id))

    league_id = _clean_str(config.get("league_id")) or defaults[0]
    state_name = _clean_str(config.get("state")) or defaults[1]
    email_pack = _clean_str(config.get("email_pack")) or _clean_str(config.get("league_id")) or defaults[2]
    email_pack = email_pack.lower()
    league_id = league_id.lower()

    return {
        "league_id": league_id,
        "state": state_name,
        "email_pack": email_pack,
    }


def apply_league_metadata_to_state(state: Dict[str, Any], metadata: Dict[str, str]) -> None:
    """Write league identity fields onto save state."""
    if not isinstance(state, dict) or not isinstance(metadata, dict):
        return
    for key in ("league_id", "state", "email_pack"):
        val = metadata.get(key)
        if isinstance(val, str) and val.strip():
            if key == "email_pack" or key == "league_id":
                state[key] = val.strip().lower()
            else:
                state[key] = val.strip()


def ensure_league_metadata_in_state(state: Dict[str, Any]) -> Dict[str, str]:
    """
    Ensure ``league_id``, ``state``, and ``email_pack`` exist on save state.

    Legacy saves without these fields are upgraded using ``playoff_system``.
    """
    if not isinstance(state, dict):
        return {
            "league_id": DEFAULT_LEAGUE_ID,
            "state": DEFAULT_STATE_NAME,
            "email_pack": DEFAULT_EMAIL_PACK,
        }

    playoff_id = ensure_playoff_system_in_state(state)
    defaults = _PLAYOFF_DEFAULTS.get(playoff_id, (playoff_id, playoff_id.upper(), playoff_id))

    league_id = _clean_str(state.get("league_id")) or defaults[0]
    state_name = _clean_str(state.get("state")) or defaults[1]
    email_pack = _clean_str(state.get("email_pack")) or league_id or defaults[2]

    league_id = league_id.lower()
    email_pack = email_pack.lower()

    state["league_id"] = league_id
    state["state"] = state_name
    state["email_pack"] = email_pack

    return {"league_id": league_id, "state": state_name, "email_pack": email_pack}


def email_pack_from_state(state: Dict[str, Any]) -> str:
    """Resolve inbox starter pack id for this save (mutates state if fields missing)."""
    meta = ensure_league_metadata_in_state(state)
    return meta["email_pack"]
