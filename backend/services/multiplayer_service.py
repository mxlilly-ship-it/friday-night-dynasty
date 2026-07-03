"""Multiplayer league registry and league dashboard payloads."""

from __future__ import annotations

import hashlib
import json
import os
import re
import secrets
import time
import uuid
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple
from zoneinfo import ZoneInfo

from backend.data_paths import leagues_base_dir
from backend.platform_config import is_platform_owner_email
from backend.storage.db import db
from systems.save_system import coach_from_dict, coach_to_dict
from systems.win_path_io import open_text_with_path_fallback

LEAGUE_SAVE_FILENAME = "league_save.json"


def _now() -> int:
    return int(time.time())


def _hash_pin(pin: str) -> str:
    return hashlib.sha256(pin.strip().encode("utf-8")).hexdigest()


def generate_team_pin() -> str:
    return f"{secrets.randbelow(1_000_000):06d}"


def _league_dir(league_id: str) -> str:
    return os.path.join(leagues_base_dir(), league_id)


def _league_save_path(save_dir: str) -> str:
    return os.path.join(save_dir, LEAGUE_SAVE_FILENAME)


def _load_league_row(league_id: str) -> Optional[Dict[str, Any]]:
    with db() as conn:
        row = conn.execute("SELECT * FROM leagues WHERE id=?", (league_id,)).fetchone()
    return dict(row) if row else None


def _user_email(user_id: str) -> str:
    with db() as conn:
        row = conn.execute("SELECT email, username FROM users WHERE id=?", (user_id,)).fetchone()
    if not row:
        return ""
    return str(row["email"] or row["username"] or "").strip()


def account_identity_for_user(user_id: str) -> Dict[str, Any]:
    """Email/username used for platform-owner checks (for diagnostics)."""
    with db() as conn:
        row = conn.execute("SELECT email, username FROM users WHERE id=?", (user_id,)).fetchone()
    if not row:
        return {"email": "", "username": ""}
    return {
        "email": str(row["email"] or "").strip(),
        "username": str(row["username"] or "").strip(),
    }


def is_platform_owner_user(user_id: str) -> bool:
    identity = account_identity_for_user(user_id)
    for field in (identity.get("email"), identity.get("username")):
        if is_platform_owner_email(str(field or "")):
            return True
    return False


def _team_initials(name: str) -> str:
    parts = re.findall(r"[A-Za-z0-9]+", name or "")
    if not parts:
        return "??"
    if len(parts) == 1:
        return parts[0][:2].upper()
    return (parts[0][:1] + parts[1][:1]).upper()


def _record_label(team: Dict[str, Any], standings: Dict[str, Any]) -> str:
    name = str(team.get("name") or "")
    row = standings.get(name) if isinstance(standings, dict) else None
    if isinstance(row, dict):
        w = int(row.get("wins", 0) or 0)
        l = int(row.get("losses", 0) or 0)
        return f"{w}-{l}"
    return "0-0"


def _division_key(team: Dict[str, Any]) -> str:
    cls = str(team.get("classification") or "League").strip() or "League"
    region = str(team.get("region") or "").strip()
    if region:
        return f"{cls} · Region {region}"
    return cls


def _stage_key_from_state(state: Dict[str, Any]) -> str:
    phase = str(state.get("season_phase") or "regular").strip().lower()
    if phase == "regular":
        wk = int(state.get("current_week", 1) or 1)
        return f"regular:week:{wk}"
    if phase == "preseason":
        stages = state.get("preseason_stages") or []
        idx = int(state.get("preseason_stage_index", 0) or 0)
        label = str(stages[idx]) if isinstance(stages, list) and 0 <= idx < len(stages) else "preseason"
        return f"preseason:{label}"
    if phase == "offseason":
        stages = state.get("offseason_stages") or []
        idx = int(state.get("offseason_stage_index", 0) or 0)
        label = str(stages[idx]) if isinstance(stages, list) and 0 <= idx < len(stages) else "offseason"
        return f"offseason:{label}"
    if phase == "playoffs":
        return "playoffs:round"
    return f"{phase}:stage"


def _load_state(save_dir: str) -> Dict[str, Any]:
    path = _league_save_path(save_dir)
    with open_text_with_path_fallback(path, "r") as f:
        return json.load(f)


def _save_state(save_dir: str, state: Dict[str, Any]) -> None:
    path = _league_save_path(save_dir)
    with open_text_with_path_fallback(path, "w") as f:
        json.dump(state, f, indent=2)


def sync_pending_invites_for_user(user_id: str) -> None:
    """Accept pending email invites — adds user as unassigned league member."""
    email = _user_email(user_id).strip().lower()
    if not email or "@" not in email:
        return
    now = _now()
    with db() as conn:
        invites = conn.execute(
            """
            SELECT id, league_id FROM league_invites
            WHERE lower(trim(email))=? AND status='pending'
            """,
            (email,),
        ).fetchall()
        for inv in invites:
            league_id = str(inv["league_id"])
            exists = conn.execute(
                """
                SELECT 1 FROM league_members
                WHERE league_id=? AND user_id=? AND status != 'removed'
                """,
                (league_id, user_id),
            ).fetchone()
            if not exists:
                conn.execute(
                    """
                    INSERT INTO league_members (
                      id, league_id, user_id, team_name, role, status,
                      control_mode, coach_setup_complete, joined_at
                    ) VALUES (?,?,?,?,?,?,?,?,?)
                    """,
                    (
                        str(uuid.uuid4()),
                        league_id,
                        user_id,
                        None,
                        "coach",
                        "unassigned",
                        "human",
                        0,
                        now,
                    ),
                )
            conn.execute(
                "UPDATE league_invites SET status='accepted' WHERE id=?",
                (str(inv["id"]),),
            )


def invite_user_to_league(league_id: str, actor_user_id: str, email: str) -> Dict[str, Any]:
    league_row = _require_commish_write(league_id, actor_user_id)
    clean = email.strip().lower()
    if not clean or "@" not in clean:
        raise ValueError("valid email required")
    existing_user = lookup_user_by_email(clean)
    now = _now()
    invite_id = str(uuid.uuid4())
    with db() as conn:
        pending = conn.execute(
            """
            SELECT id FROM league_invites
            WHERE league_id=? AND lower(trim(email))=? AND status='pending'
            """,
            (league_id, clean),
        ).fetchone()
        if pending:
            raise ValueError(f"{clean} already has a pending invite")
        if existing_user:
            member = conn.execute(
                """
                SELECT status FROM league_members
                WHERE league_id=? AND user_id=? AND status != 'removed'
                """,
                (league_id, str(existing_user["user_id"])),
            ).fetchone()
            if member:
                raise ValueError(f"{clean} is already in this league")
        conn.execute(
            """
            INSERT INTO league_invites (id, league_id, email, status, created_by_user_id, created_at)
            VALUES (?,?,?,?,?,?)
            """,
            (invite_id, league_id, clean, "pending", actor_user_id, now),
        )
        conn.execute(
            """
            INSERT INTO league_activity_log (id, league_id, actor_user_id, action, detail_json, created_at)
            VALUES (?,?,?,?,?,?)
            """,
            (
                str(uuid.uuid4()),
                league_id,
                actor_user_id,
                "invite_sent",
                json.dumps({"text": f"Invited {clean}", "icon": "✉️"}),
                now,
            ),
        )

    email_sent = False
    try:
        from backend.email_notify import send_league_invite_email

        inviter = _user_email(actor_user_id) or "Your commissioner"
        email_sent = send_league_invite_email(
            to_email=clean,
            league_name=str(league_row.get("name") or "League"),
            inviter_label=inviter,
        )
    except Exception:
        email_sent = False
    return {
        "invite_id": invite_id,
        "email": clean,
        "status": "pending",
        "email_sent": email_sent,
    }


def apply_member_coach_setup(
    league_id: str,
    user_id: str,
    team_name: str,
    coach_config: Dict[str, Any],
) -> Dict[str, Any]:
    """Apply a human coach profile to their assigned team in the shared league save."""
    from models.coach import apply_coach_config_dict

    league_row = _load_league_row(league_id)
    if not league_row:
        raise ValueError("league not found")
    save_dir = str(league_row.get("save_dir") or "")
    if not save_dir:
        raise ValueError("league save missing")

    with db() as conn:
        mem = conn.execute(
            """
            SELECT team_name, status FROM league_members
            WHERE league_id=? AND user_id=? AND team_name=? AND status='active'
            """,
            (league_id, user_id, team_name),
        ).fetchone()
    if not mem:
        raise PermissionError("team not assigned to you")

    state = _load_state(save_dir)
    teams = state.get("teams") or []
    target: Optional[Dict[str, Any]] = None
    for row in teams:
        if isinstance(row, dict) and str(row.get("name") or "") == team_name:
            target = row
            break
    if not target:
        raise ValueError("team not found in league save")

    coach_dict = target.get("coach") if isinstance(target.get("coach"), dict) else {}
    coach = coach_from_dict(coach_dict)
    apply_coach_config_dict(coach, coach_config)
    # League creation locks CPU teams' playbooks for the current year; human coaches must be able to pick.
    coach.last_preferred_playbook_change_year = 0
    target["coach"] = coach_to_dict(coach)

    coach_name = str(coach_config.get("name") or coach.name or "").strip()
    if coach_name:
        mp_coaches = state.get("multiplayer_coach_names")
        if not isinstance(mp_coaches, dict):
            mp_coaches = {}
        mp_coaches[team_name] = coach_name
        state["multiplayer_coach_names"] = mp_coaches

    _save_state(save_dir, state)
    now = _now()
    with db() as conn:
        conn.execute(
            """
            UPDATE league_members SET coach_setup_complete=1
            WHERE league_id=? AND user_id=? AND team_name=?
            """,
            (league_id, user_id, team_name),
        )
        conn.execute(
            "UPDATE leagues SET state_version=state_version+1, updated_at=? WHERE id=?",
            (now, league_id),
        )
    return {"ok": True, "team_name": team_name, "coach_name": coach_name}


def lookup_user_by_email(email: str) -> Optional[Dict[str, Any]]:
    """Find a registered user by email or username (exact match, case-insensitive)."""
    clean = str(email or "").strip().lower()
    if not clean:
        return None
    with db() as conn:
        row = conn.execute(
            """
            SELECT id, email, username FROM users
            WHERE lower(trim(coalesce(email, ''))) = ?
               OR lower(trim(username)) = ?
            LIMIT 1
            """,
            (clean, clean),
        ).fetchone()
    if not row:
        return None
    return {
        "user_id": str(row["id"]),
        "email": str(row["email"] or row["username"] or "").strip(),
        "username": str(row["username"] or "").strip(),
    }


def resolve_commissioner_user_id(
    owner_user_id: str,
    *,
    commissioner_user_id: Optional[str] = None,
    commissioner_email: Optional[str] = None,
) -> str:
    if commissioner_user_id:
        cid = str(commissioner_user_id).strip()
        with db() as conn:
            row = conn.execute("SELECT id FROM users WHERE id=?", (cid,)).fetchone()
        if not row:
            raise ValueError("commissioner user not found")
        return cid
    if commissioner_email and str(commissioner_email).strip():
        found = lookup_user_by_email(commissioner_email)
        if not found:
            raise ValueError(
                f"No account found for {str(commissioner_email).strip()}. "
                "They must sign in to FND once before you can appoint them commissioner."
            )
        return str(found["user_id"])
    return owner_user_id


def _verify_commish_game_access(league_id: str, user_id: str) -> Dict[str, Any]:
    league_row = _load_league_row(league_id)
    if not league_row:
        raise ValueError("league not found")
    if str(league_row.get("commissioner_user_id") or "") != user_id:
        raise PermissionError("commissioner only")
    return league_row


def _verify_commish_view_access(league_id: str, user_id: str) -> Tuple[Dict[str, Any], bool]:
    """Commissioner write access, or platform-owner read-only browse."""
    league_row = _load_league_row(league_id)
    if not league_row:
        raise ValueError("league not found")
    is_commish = str(league_row.get("commissioner_user_id") or "") == user_id
    is_owner = is_platform_owner_user(user_id)
    if not is_commish and not is_owner:
        raise PermissionError("commissioner only")
    return league_row, bool(is_owner and not is_commish)


def _require_commish_write(league_id: str, user_id: str) -> Dict[str, Any]:
    return _verify_commish_game_access(league_id, user_id)


_TEAM_GAMEPLAN_PREF_KEYS = (
    "gameplan_last_confirmed",
    "gameplan_week_to_week",
    "offense_gameplan_library",
    "defense_gameplan_library",
)


def _gameplan_v2_key_belongs_to_team(key: str, team_name: str) -> bool:
    """True when a coach_gameplans_v2 key is for a matchup involving team_name."""
    key = str(key or "").strip()
    team_name = str(team_name or "").strip()
    if not key or not team_name:
        return False
    if key.startswith("bye:week:"):
        parts = key.split(":")
        return len(parts) >= 4 and parts[3] == team_name
    matchup = ""
    if key.startswith("week:"):
        parts = key.split(":", 3)
        matchup = parts[3] if len(parts) > 3 else ""
    elif key.startswith("playoff:"):
        matchup = key.split(":", 1)[1] if ":" in key else ""
    if matchup and " vs " in matchup:
        home, away = matchup.split(" vs ", 1)
        return team_name in (home.strip(), away.strip())
    return False


def _filter_coach_gameplans_v2_for_team(store: Any, team_name: str) -> Dict[str, Any]:
    if not isinstance(store, dict):
        return {}
    team_name = str(team_name or "").strip()
    return {
        k: v
        for k, v in store.items()
        if _gameplan_v2_key_belongs_to_team(str(k), team_name)
    }


def _merge_coach_gameplans_v2_for_team(
    base_store: Any,
    incoming_store: Any,
    team_name: str,
) -> Dict[str, Any]:
    import copy

    merged = copy.deepcopy(base_store) if isinstance(base_store, dict) else {}
    if not isinstance(incoming_store, dict):
        return merged
    team_name = str(team_name or "").strip()
    for key, value in incoming_store.items():
        if _gameplan_v2_key_belongs_to_team(str(key), team_name):
            merged[str(key)] = copy.deepcopy(value)
    return merged


def _persist_team_gameplan_prefs(
    canonical: Dict[str, Any],
    team_name: str,
    incoming: Dict[str, Any],
) -> None:
    import copy

    team_name = str(team_name or "").strip()
    if not team_name or str(incoming.get("user_team") or "") != team_name:
        return
    prefs_root = canonical.get("multiplayer_team_gameplan_prefs")
    if not isinstance(prefs_root, dict):
        prefs_root = {}
    team_prefs = prefs_root.get(team_name)
    if not isinstance(team_prefs, dict):
        team_prefs = {}
    for key in _TEAM_GAMEPLAN_PREF_KEYS:
        if key in incoming:
            team_prefs[key] = copy.deepcopy(incoming[key])
    prefs_root[team_name] = team_prefs
    canonical["multiplayer_team_gameplan_prefs"] = prefs_root
    for key in _TEAM_GAMEPLAN_PREF_KEYS:
        canonical.pop(key, None)


def apply_coach_gameplan_privacy_for_team(state: Dict[str, Any], team_name: str) -> Dict[str, Any]:
    """
    Strip other coaches' gameplans from a working copy sent to one human coach.
    Per-coach libraries / carry-forward prefs are hydrated from multiplayer_team_gameplan_prefs.
    """
    import copy

    team_name = str(team_name or "").strip()
    if not team_name:
        return state

    prefs_root = state.get("multiplayer_team_gameplan_prefs")
    if not isinstance(prefs_root, dict):
        prefs_root = {}

    team_prefs = prefs_root.get(team_name)
    if not isinstance(team_prefs, dict):
        team_prefs = {}
        store = state.get("coach_gameplans_v2")
        only_mine = (
            all(_gameplan_v2_key_belongs_to_team(str(k), team_name) for k in store)
            if isinstance(store, dict) and store
            else True
        )
        if only_mine:
            for key in _TEAM_GAMEPLAN_PREF_KEYS:
                if key in state:
                    team_prefs[key] = copy.deepcopy(state[key])

    for key in _TEAM_GAMEPLAN_PREF_KEYS:
        if key in team_prefs:
            state[key] = copy.deepcopy(team_prefs[key])
        else:
            state.pop(key, None)

    state["coach_gameplans_v2"] = _filter_coach_gameplans_v2_for_team(
        state.get("coach_gameplans_v2"),
        team_name,
    )
    return state


def _merge_coach_state_into_canonical(
    canonical: Dict[str, Any],
    incoming: Dict[str, Any],
    team_name: str,
) -> Dict[str, Any]:
    """Merge a coach working copy into the shared league save without overwriting league calendar."""
    import copy

    out = copy.deepcopy(canonical)
    team_name = str(team_name or "").strip()
    if not team_name:
        raise ValueError("team_name required")

    inc_teams: Dict[str, Dict[str, Any]] = {}
    for row in incoming.get("teams") or []:
        if isinstance(row, dict) and row.get("name"):
            inc_teams[str(row["name"])] = row
    if team_name in inc_teams:
        kept: List[Dict[str, Any]] = []
        replaced = False
        for row in out.get("teams") or []:
            if isinstance(row, dict) and str(row.get("name") or "") == team_name:
                kept.append(copy.deepcopy(inc_teams[team_name]))
                replaced = True
            elif isinstance(row, dict):
                kept.append(copy.deepcopy(row))
        if not replaced:
            kept.append(copy.deepcopy(inc_teams[team_name]))
        out["teams"] = kept

    inc_gp = incoming.get("coach_gameplans_v2")
    if isinstance(inc_gp, dict) and inc_gp:
        out["coach_gameplans_v2"] = _merge_coach_gameplans_v2_for_team(
            out.get("coach_gameplans_v2"),
            inc_gp,
            team_name,
        )

    _persist_team_gameplan_prefs(out, team_name, incoming)

    if isinstance(incoming.get("coach_inbox"), dict):
        out["coach_inbox"] = copy.deepcopy(incoming["coach_inbox"])

    if str(incoming.get("user_team") or "") == team_name:
        if isinstance(incoming.get("season_goals"), dict):
            out["season_goals"] = copy.deepcopy(incoming["season_goals"])
        for key in (
            "preseason_scrimmages",
            "preseason_scrimmage_opponents",
        ):
            if key in incoming:
                out[key] = copy.deepcopy(incoming[key])

    inc_names = incoming.get("multiplayer_coach_names")
    if isinstance(inc_names, dict):
        names = out.get("multiplayer_coach_names")
        if not isinstance(names, dict):
            names = {}
        names = copy.deepcopy(names)
        if team_name in inc_names:
            names[team_name] = inc_names[team_name]
        out["multiplayer_coach_names"] = names

    for bank_key in ("offseason_coach_dev_banks",):
        inc_bank = incoming.get(bank_key)
        if isinstance(inc_bank, dict) and team_name in inc_bank:
            base_bank = out.get(bank_key)
            if not isinstance(base_bank, dict):
                base_bank = {}
            base_bank = copy.deepcopy(base_bank)
            base_bank[team_name] = copy.deepcopy(inc_bank[team_name])
            out[bank_key] = base_bank

    if str(incoming.get("user_team") or "") == team_name:
        for key in ("offseason_coach_dev_bank", "offseason_improvements_bank"):
            if key in incoming:
                out[key] = copy.deepcopy(incoming[key])

    out["multiplayer_league"] = True
    mp = out.get("multiplayer") if isinstance(out.get("multiplayer"), dict) else {}
    mp = dict(mp)
    inc_mp = incoming.get("multiplayer") if isinstance(incoming.get("multiplayer"), dict) else {}
    if inc_mp.get("league_id"):
        mp["league_id"] = inc_mp["league_id"]
    mp["multiplayer_league"] = True
    out["multiplayer"] = mp
    return out


def _commissioner_acting_team(league_id: str, user_id: str, state: Dict[str, Any]) -> str:
    with db() as conn:
        row = conn.execute(
            """
            SELECT team_name FROM league_members
            WHERE league_id=? AND user_id=? AND status='active'
            """,
            (league_id, user_id),
        ).fetchone()
    if row and row["team_name"]:
        return str(row["team_name"])
    ut = str(state.get("user_team") or "").strip()
    if ut:
        return ut
    for row in state.get("teams") or []:
        if isinstance(row, dict) and row.get("name"):
            return str(row["name"])
    return ""


def get_league_commish_game_bundle(league_id: str, user_id: str) -> Dict[str, Any]:
    """Load full league save for commissioner to sim/advance the league."""
    import copy

    from systems.league_history import load_league_history
    from systems.save_system import league_history_path, records_path

    league_row = _verify_commish_game_access(league_id, user_id)
    save_dir = str(league_row.get("save_dir") or "")
    from backend.services.league_service import ensure_multiplayer_opening_schedule

    canonical = _load_state(save_dir)
    canonical["multiplayer_league"] = True
    mp_meta = canonical.get("multiplayer") if isinstance(canonical.get("multiplayer"), dict) else {}
    mp_meta = dict(mp_meta)
    mp_meta["league_id"] = league_id
    canonical["multiplayer"] = mp_meta
    if ensure_multiplayer_opening_schedule(canonical):
        _save_state(save_dir, canonical)
        with db() as conn:
            conn.execute(
                "UPDATE leagues SET state_version=state_version+1, updated_at=? WHERE id=?",
                (_now(), league_id),
            )

    state = copy.deepcopy(canonical)
    acting = _commissioner_acting_team(league_id, user_id, state)
    if acting:
        state["user_team"] = acting
    state["multiplayer_league"] = True
    state["multiplayer"] = {
        "league_id": league_id,
        "commish_mode": True,
        "team_name": acting or None,
        "multiplayer_league": True,
    }

    league_history: Dict[str, Any] = {"seasons": []}
    records: Dict[str, Any] = {}
    try:
        league_history = load_league_history(league_history_path(save_dir))
    except Exception:
        pass
    try:
        rpath = records_path(save_dir)
        if os.path.isfile(rpath):
            with open_text_with_path_fallback(rpath, "r") as f:
                records = json.load(f)
    except Exception:
        pass

    return {
        "league_id": league_id,
        "commish_mode": True,
        "state": state,
        "league_history": league_history,
        "records": records,
        "state_version": int(league_row.get("state_version") or 0),
    }


def save_league_commish_game_state(
    league_id: str,
    user_id: str,
    state: Dict[str, Any],
) -> Dict[str, Any]:
    """Persist full league save after commissioner sim/advance."""
    import copy

    league_row = _verify_commish_game_access(league_id, user_id)
    save_dir = str(league_row.get("save_dir") or "")
    incoming = copy.deepcopy(state) if isinstance(state, dict) else {}
    mp = incoming.get("multiplayer")
    if not isinstance(mp, dict):
        mp = {}
    mp["league_id"] = league_id
    mp["commish_mode"] = True
    incoming["multiplayer"] = mp
    _save_state(save_dir, incoming)
    now = _now()
    with db() as conn:
        conn.execute(
            "UPDATE leagues SET state_version=state_version+1, updated_at=? WHERE id=?",
            (now, league_id),
        )
    return {"ok": True, "state_version": int(league_row.get("state_version") or 0) + 1}


def _verify_team_game_access(league_id: str, user_id: str, team_name: str) -> Dict[str, Any]:
    league_row = _load_league_row(league_id)
    if not league_row:
        raise ValueError("league not found")
    team_name = str(team_name or "").strip()
    if not team_name:
        raise ValueError("team_name required")
    with db() as conn:
        row = conn.execute(
            """
            SELECT team_name, status, coach_setup_complete FROM league_members
            WHERE league_id=? AND user_id=? AND status='active'
            """,
            (league_id, user_id),
        ).fetchone()
    if not row or str(row["team_name"] or "") != team_name:
        raise PermissionError("not your team")
    if not int(row["coach_setup_complete"] or 0):
        raise PermissionError("coach setup required")
    return league_row


def _unlock_human_playbooks_during_select(state: Dict[str, Any], team_name: str) -> bool:
    """Clear CPU playbook locks so human coaches can choose schemes in Playbook Select."""
    phase = str(state.get("season_phase") or "").strip().lower()
    if phase != "preseason":
        return False
    stages = state.get("preseason_stages") or []
    idx = int(state.get("preseason_stage_index") or 0)
    if not isinstance(stages, list) or idx < 0 or idx >= len(stages):
        return False
    if str(stages[idx]) != "Playbook Select":
        return False
    team_name = str(team_name or "").strip()
    if not team_name:
        return False
    for row in state.get("teams") or []:
        if not isinstance(row, dict) or str(row.get("name") or "") != team_name:
            continue
        coach = row.get("coach") if isinstance(row.get("coach"), dict) else None
        if not coach:
            return False
        last = int(coach.get("last_preferred_playbook_change_year") or 0)
        if last <= 0:
            return False
        coach["last_preferred_playbook_change_year"] = 0
        row["coach"] = coach
        return True
    return False


def get_league_game_bundle(league_id: str, user_id: str, team_name: str) -> Dict[str, Any]:
    """Load league save scoped to the coach's team (same shape as GET /saves/{id})."""
    import copy

    from systems.league_history import load_league_history
    from systems.save_system import league_history_path, records_path

    league_row = _verify_team_game_access(league_id, user_id, team_name)
    save_dir = str(league_row.get("save_dir") or "")
    from backend.services.league_service import ensure_multiplayer_opening_schedule

    canonical = _load_state(save_dir)
    canonical["multiplayer_league"] = True
    mp_meta = canonical.get("multiplayer") if isinstance(canonical.get("multiplayer"), dict) else {}
    mp_meta = dict(mp_meta)
    mp_meta["league_id"] = league_id
    canonical["multiplayer"] = mp_meta
    changed = ensure_multiplayer_opening_schedule(canonical)
    if _unlock_human_playbooks_during_select(canonical, team_name):
        changed = True
    if changed:
        _save_state(save_dir, canonical)
        with db() as conn:
            conn.execute(
                "UPDATE leagues SET state_version=state_version+1, updated_at=? WHERE id=?",
                (_now(), league_id),
            )

    state = copy.deepcopy(canonical)
    state["user_team"] = team_name
    mp_names = state.get("multiplayer_coach_names")
    if isinstance(mp_names, dict) and mp_names.get(team_name):
        state["user_coach_name"] = str(mp_names[team_name])
    else:
        for row in state.get("teams") or []:
            if isinstance(row, dict) and str(row.get("name") or "") == team_name:
                coach = row.get("coach") if isinstance(row.get("coach"), dict) else {}
                nm = str(coach.get("name") or "").strip()
                if nm:
                    state["user_coach_name"] = nm
                break
    state["multiplayer"] = {"league_id": league_id, "team_name": team_name, "multiplayer_league": True}
    state["multiplayer_league"] = True

    apply_coach_gameplan_privacy_for_team(state, team_name)

    league_history: Dict[str, Any] = {"seasons": []}
    records: Dict[str, Any] = {}
    try:
        league_history = load_league_history(league_history_path(save_dir))
    except Exception:
        pass
    try:
        rpath = records_path(save_dir)
        if os.path.isfile(rpath):
            with open_text_with_path_fallback(rpath, "r") as f:
                records = json.load(f)
    except Exception:
        pass

    return {
        "league_id": league_id,
        "team_name": team_name,
        "state": state,
        "league_history": league_history,
        "records": records,
        "state_version": int(league_row.get("state_version") or 0),
    }


def save_league_game_state(
    league_id: str,
    user_id: str,
    team_name: str,
    state: Dict[str, Any],
) -> Dict[str, Any]:
    """Persist coach's working copy of the shared league save."""
    import copy

    league_row = _verify_team_game_access(league_id, user_id, team_name)
    save_dir = str(league_row.get("save_dir") or "")
    incoming = copy.deepcopy(state) if isinstance(state, dict) else {}
    apply_coach_gameplan_privacy_for_team(incoming, team_name)
    canonical = _load_state(save_dir)
    merged = _merge_coach_state_into_canonical(canonical, incoming, team_name)
    merged["user_team"] = team_name
    mp = merged.get("multiplayer")
    if not isinstance(mp, dict):
        mp = {}
    mp["league_id"] = league_id
    mp["team_name"] = team_name
    merged["multiplayer"] = mp
    _save_state(save_dir, merged)
    now = _now()
    with db() as conn:
        conn.execute(
            "UPDATE leagues SET state_version=state_version+1, updated_at=? WHERE id=?",
            (now, league_id),
        )
    return {"ok": True, "state_version": int(league_row.get("state_version") or 0) + 1}


def _teams_meta_from_state(state: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    out: Dict[str, Dict[str, Any]] = {}
    for row in state.get("teams") or []:
        if isinstance(row, dict) and row.get("name"):
            out[str(row["name"])] = row
    return out


def league_schools_for_user(league_id: str, user_id: str) -> List[Dict[str, Any]]:
    """Team list from league save (for coach setup school picker / prestige)."""
    league_row = _load_league_row(league_id)
    if not league_row:
        raise ValueError("league not found")
    with db() as conn:
        mem = conn.execute(
            """
            SELECT 1 FROM league_members
            WHERE league_id=? AND user_id=? AND status != 'removed'
            """,
            (league_id, user_id),
        ).fetchone()
    if not mem and not is_platform_owner_user(user_id):
        raise PermissionError("not a league member")
    save_dir = str(league_row.get("save_dir") or "")
    state = _load_state(save_dir)
    schools: List[Dict[str, Any]] = []
    for row in state.get("teams") or []:
        if not isinstance(row, dict) or not row.get("name"):
            continue
        schools.append(
            {
                "name": row.get("name"),
                "prestige": row.get("prestige"),
                "classification": row.get("classification"),
                "region": row.get("region"),
            }
        )
    schools.sort(key=lambda s: str(s.get("name") or "").lower())
    return schools


def _advance_countdown_iso(league_row: Dict[str, Any]) -> Optional[str]:
    if str(league_row.get("advance_mode") or "manual").lower() != "auto":
        return None
    tz_name = str(league_row.get("timezone") or "America/New_York")
    dow = league_row.get("advance_deadline_dow")
    time_local = str(league_row.get("advance_deadline_time_local") or "23:59").strip()
    if dow is None:
        return None
    try:
        tz = ZoneInfo(tz_name)
    except Exception:
        tz = ZoneInfo("America/New_York")
    try:
        hour, minute = [int(x) for x in time_local.split(":", 1)]
    except Exception:
        hour, minute = 23, 59
    now = datetime.now(tz)
    target_dow = int(dow) % 7
    days_ahead = (target_dow - now.weekday()) % 7
    candidate = now.replace(hour=hour, minute=minute, second=0, microsecond=0) + timedelta(days=days_ahead)
    if candidate <= now:
        candidate += timedelta(days=7)
    return candidate.isoformat()


def _format_countdown(deadline_iso: Optional[str]) -> Optional[str]:
    if not deadline_iso:
        return None
    try:
        deadline = datetime.fromisoformat(deadline_iso)
        if deadline.tzinfo is None:
            deadline = deadline.replace(tzinfo=ZoneInfo("UTC"))
        now = datetime.now(deadline.tzinfo)
        delta = deadline - now
        if delta.total_seconds() <= 0:
            return "Due now"
        days = delta.days
        hours, rem = divmod(int(delta.total_seconds()) - days * 86400, 3600)
        minutes = rem // 60
        if days > 0:
            return f"{days}d {hours}h {minutes}m"
        if hours > 0:
            return f"{hours}h {minutes}m"
        return f"{minutes}m"
    except Exception:
        return None


        return None


def _most_recent_advance_deadline(league_row: Dict[str, Any]) -> Optional[datetime]:
    """Most recent scheduled auto-advance instant (may be in the past)."""
    if str(league_row.get("advance_mode") or "manual").lower() != "auto":
        return None
    dow = league_row.get("advance_deadline_dow")
    if dow is None:
        return None
    tz_name = str(league_row.get("timezone") or "America/New_York")
    time_local = str(league_row.get("advance_deadline_time_local") or "23:59").strip()
    try:
        tz = ZoneInfo(tz_name)
    except Exception:
        tz = ZoneInfo("America/New_York")
    try:
        hour, minute = [int(x) for x in time_local.split(":", 1)]
    except Exception:
        hour, minute = 23, 59
    now = datetime.now(tz)
    target_dow = int(dow) % 7
    days_back = (now.weekday() - target_dow) % 7
    candidate = now.replace(hour=hour, minute=minute, second=0, microsecond=0) - timedelta(days=days_back)
    if candidate > now:
        candidate -= timedelta(days=7)
    return candidate


def try_auto_advance_league(league_id: str) -> bool:
    """If auto-advance deadline passed, advance once as commissioner."""
    league_row = _load_league_row(league_id)
    if not league_row:
        return False
    deadline = _most_recent_advance_deadline(league_row)
    if deadline is None:
        return False
    now = datetime.now(deadline.tzinfo)
    if now < deadline:
        return False
    last_at = int(league_row.get("last_auto_advance_at") or 0)
    if last_at >= int(deadline.timestamp()):
        return False
    commish_id = str(league_row.get("commissioner_user_id") or "")
    if not commish_id:
        return False
    try:
        commish_advance_league(league_id, commish_id)
    except Exception:
        return False
    with db() as conn:
        conn.execute(
            "UPDATE leagues SET last_auto_advance_at=?, updated_at=? WHERE id=?",
            (int(now.timestamp()), _now(), league_id),
        )
    return True


def run_auto_advance_for_league_ids(league_ids: List[str]) -> None:
    for league_id in league_ids:
        try:
            try_auto_advance_league(league_id)
        except Exception:
            continue


def vacate_team_member(league_id: str, actor_user_id: str, target_user_id: str) -> Dict[str, Any]:
    _require_commish_write(league_id, actor_user_id)
    with db() as conn:
        row = conn.execute(
            """
            SELECT team_name FROM league_members
            WHERE league_id=? AND user_id=? AND status='active' AND team_name IS NOT NULL
            """,
            (league_id, target_user_id),
        ).fetchone()
        if not row or not row["team_name"]:
            raise ValueError("member has no team to vacate")
        team_name = str(row["team_name"])
        conn.execute(
            """
            UPDATE league_members
            SET team_name=NULL, status='unassigned', pin_hash=NULL, pin_updated_at=NULL,
                coach_setup_complete=0, control_mode='human'
            WHERE league_id=? AND user_id=?
            """,
            (league_id, target_user_id),
        )
        conn.execute(
            "DELETE FROM league_submit_status WHERE league_id=? AND user_id=?",
            (league_id, target_user_id),
        )
    now = _now()
    with db() as conn:
        conn.execute(
            """
            INSERT INTO league_activity_log (id, league_id, actor_user_id, action, detail_json, created_at)
            VALUES (?,?,?,?,?,?)
            """,
            (
                str(uuid.uuid4()),
                league_id,
                actor_user_id,
                "vacate_team",
                json.dumps({"text": f"Vacated {team_name}", "icon": "🚪"}),
                now,
            ),
        )
    return {"ok": True, "team_name": team_name, "user_id": target_user_id}


def remove_league_member(league_id: str, actor_user_id: str, target_user_id: str) -> Dict[str, Any]:
    league_row = _require_commish_write(league_id, actor_user_id)
    if str(league_row.get("commissioner_user_id") or "") == target_user_id:
        raise ValueError("cannot remove the commissioner")
    with db() as conn:
        row = conn.execute(
            """
            SELECT m.team_name, u.email, u.username FROM league_members m
            LEFT JOIN users u ON u.id = m.user_id
            WHERE m.league_id=? AND m.user_id=? AND m.status != 'removed'
            """,
            (league_id, target_user_id),
        ).fetchone()
        if not row:
            raise ValueError("member not found")
        conn.execute(
            """
            UPDATE league_members
            SET status='removed', team_name=NULL, pin_hash=NULL, pin_updated_at=NULL
            WHERE league_id=? AND user_id=?
            """,
            (league_id, target_user_id),
        )
        conn.execute(
            "DELETE FROM league_submit_status WHERE league_id=? AND user_id=?",
            (league_id, target_user_id),
        )
    label = str(row["team_name"] or row["email"] or row["username"] or target_user_id)
    now = _now()
    with db() as conn:
        conn.execute(
            """
            INSERT INTO league_activity_log (id, league_id, actor_user_id, action, detail_json, created_at)
            VALUES (?,?,?,?,?,?)
            """,
            (
                str(uuid.uuid4()),
                league_id,
                actor_user_id,
                "remove_member",
                json.dumps({"text": f"Removed {label}", "icon": "✖"}),
                now,
            ),
        )
    return {"ok": True, "user_id": target_user_id}


def revoke_league_invite(league_id: str, actor_user_id: str, invite_id: str) -> Dict[str, Any]:
    _require_commish_write(league_id, actor_user_id)
    with db() as conn:
        row = conn.execute(
            "SELECT email FROM league_invites WHERE id=? AND league_id=? AND status='pending'",
            (invite_id, league_id),
        ).fetchone()
        if not row:
            raise ValueError("pending invite not found")
        conn.execute(
            "UPDATE league_invites SET status='revoked' WHERE id=? AND league_id=?",
            (invite_id, league_id),
        )
    return {"ok": True, "invite_id": invite_id, "email": str(row["email"])}


def list_leagues_for_user(user_id: str) -> List[Dict[str, Any]]:
    is_owner = is_platform_owner_user(user_id)
    with db() as conn:
        if is_owner:
            rows = conn.execute(
                """
                SELECT id, name, status, commissioner_user_id, updated_at, save_dir
                FROM leagues ORDER BY updated_at DESC
                """
            ).fetchall()
        else:
            rows = conn.execute(
                """
                SELECT DISTINCT l.id, l.name, l.status, l.commissioner_user_id, l.updated_at, l.save_dir
                FROM leagues l
                INNER JOIN league_members m ON m.league_id = l.id
                WHERE m.user_id = ? AND m.status != 'removed'
                ORDER BY l.updated_at DESC
                """,
                (user_id,),
            ).fetchall()
        row_payloads: List[Dict[str, Any]] = []
        for r in rows:
            league_id = r["id"]
            mem_rows = conn.execute(
                """
                SELECT team_name, role, status, control_mode, coach_setup_complete
                FROM league_members
                WHERE league_id=? AND user_id=? AND status != 'removed'
                """,
                (league_id, user_id),
            ).fetchall()
            is_commish = str(r["commissioner_user_id"] or "") == user_id or any(
                str(m["role"] or "") == "commissioner" for m in mem_rows
            )
            if is_owner and not mem_rows:
                is_commish = True
            teams = [
                {
                    "team_name": m["team_name"],
                    "status": m["status"],
                    "control_mode": m["control_mode"],
                    "role": m["role"],
                    "coach_setup_complete": bool(m["coach_setup_complete"]),
                }
                for m in mem_rows
                if m["team_name"]
            ]
            unassigned = any(not m["team_name"] for m in mem_rows)
            row_payloads.append(
                {
                    "league_id": league_id,
                    "name": r["name"],
                    "status": r["status"],
                    "is_commissioner": is_commish,
                    "is_platform_owner_view": is_owner,
                    "can_run_league": str(r["commissioner_user_id"] or "") == user_id,
                    "teams": teams,
                    "unassigned": unassigned,
                    "save_dir": str(r["save_dir"] or ""),
                    "updated_at": int(r["updated_at"]),
                }
            )

    out: List[Dict[str, Any]] = []
    for item in row_payloads:
        badges: List[str] = []
        if item["is_platform_owner_view"] and not item["can_run_league"]:
            badges.append("Admin")
        if item["is_commissioner"]:
            badges.append("Commissioner")
        submitted = False
        your_turn = False
        week_label = None
        teams = item["teams"]
        if teams:
            try:
                state = _load_state(item["save_dir"]) if item["save_dir"] else {}
                stage_key = _stage_key_from_state(state) if state else ""
                submitted_set = (
                    _submitted_teams(item["league_id"], stage_key) if stage_key else set()
                )
                phase = str(state.get("season_phase") or "regular").strip().lower()
                current_week = int(state.get("current_week", 1) or 1)
                weeks = state.get("weeks") or []
                total_weeks = len(weeks) if isinstance(weeks, list) and weeks else 12
                week_label = f"Week {current_week}"
                if phase == "regular":
                    week_label = f"Week {current_week} of {total_weeks}"
                elif phase == "preseason":
                    week_label = "Preseason"
                elif phase == "offseason":
                    week_label = "Offseason"
                elif phase == "playoffs":
                    week_label = "Playoffs"
                elif phase == "schedule_planning":
                    week_label = "Schedule planning"
                team_names = [str(t["team_name"]) for t in teams if t.get("team_name")]
                submitted = all(t in submitted_set for t in team_names) if team_names else False
                your_turn = any(
                    t not in submitted_set
                    and any(
                        str(m.get("team_name") or "") == t and m.get("coach_setup_complete")
                        for m in teams
                    )
                    for t in team_names
                )
                if submitted:
                    badges.append("Submitted")
                elif your_turn:
                    badges.append("Your turn")
                elif any(not t.get("coach_setup_complete") for t in teams):
                    badges.append("Setup needed")
            except Exception:
                pass
        elif item.get("unassigned"):
            badges.append("Awaiting team")
        out.append(
            {
                "league_id": item["league_id"],
                "name": item["name"],
                "status": item["status"],
                "is_commissioner": item["is_commissioner"],
                "is_platform_owner_view": item["is_platform_owner_view"],
                "can_run_league": item["can_run_league"],
                "teams": teams,
                "updated_at": item["updated_at"],
                "badges": badges,
                "submitted": submitted,
                "your_turn": your_turn,
                "week_label": week_label,
            }
        )
    commish_ids = [str(x["league_id"]) for x in out if x.get("can_run_league")]
    run_auto_advance_for_league_ids(commish_ids)
    return out


def verify_team_pin(league_id: str, user_id: str, team_name: str, pin: str) -> bool:
    with db() as conn:
        row = conn.execute(
            """
            SELECT pin_hash FROM league_members
            WHERE league_id=? AND user_id=? AND team_name=? AND status='active'
            """,
            (league_id, user_id, team_name),
        ).fetchone()
    if not row or not row["pin_hash"]:
        return False
    return row["pin_hash"] == _hash_pin(pin)


def _submitted_teams(league_id: str, stage_key: str) -> set[str]:
    with db() as conn:
        rows = conn.execute(
            "SELECT team_name FROM league_submit_status WHERE league_id=? AND stage_key=?",
            (league_id, stage_key),
        ).fetchall()
    return {str(r["team_name"]) for r in rows if r["team_name"]}


def _human_teams(league_id: str) -> List[Dict[str, Any]]:
    with db() as conn:
        rows = conn.execute(
            """
            SELECT team_name, control_mode, status, user_id
            FROM league_members
            WHERE league_id=? AND status='active' AND team_name IS NOT NULL AND control_mode='human'
            """,
            (league_id,),
        ).fetchall()
    return [dict(r) for r in rows]


def build_league_dashboard(
    league_id: str,
    user_id: str,
    *,
    acting_team_name: Optional[str] = None,
) -> Dict[str, Any]:
    league_row = _load_league_row(league_id)
    if not league_row:
        raise ValueError("league not found")

    is_owner = is_platform_owner_user(user_id)
    is_commish = str(league_row.get("commissioner_user_id") or "") == user_id
    if is_commish:
        try_auto_advance_league(league_id)
        league_row = _load_league_row(league_id) or league_row
    if not is_commish and not is_owner:
        with db() as conn:
            row = conn.execute(
                """
                SELECT 1 FROM league_members
                WHERE league_id=? AND user_id=? AND status != 'removed'
                LIMIT 1
                """,
                (league_id, user_id),
            ).fetchone()
        if not row:
            raise ValueError("not a league member")

    state = _load_state(str(league_row["save_dir"]))
    teams_meta = _teams_meta_from_state(state)
    standings = state.get("standings") if isinstance(state.get("standings"), dict) else {}
    stage_key = _stage_key_from_state(state)
    submitted = _submitted_teams(league_id, stage_key)
    human_members = _human_teams(league_id)

    # Divisions
    divisions: Dict[str, List[str]] = {}
    for name, meta in teams_meta.items():
        key = _division_key(meta)
        divisions.setdefault(key, []).append(name)
    for names in divisions.values():
        names.sort(key=lambda n: (-int((standings.get(n) or {}).get("wins", 0) or 0), n))

    division_count = len(divisions)
    team_count = len(teams_meta)

    # Week info
    phase = str(state.get("season_phase") or "regular").strip().lower()
    current_week = int(state.get("current_week", 1) or 1)
    weeks = state.get("weeks") or []
    total_weeks = len(weeks) if isinstance(weeks, list) and weeks else 12
    week_label = f"Week {current_week} of {total_weeks}"
    if phase == "preseason":
        stages = state.get("preseason_stages") or []
        idx = int(state.get("preseason_stage_index", 0) or 0)
        week_label = f"Preseason — {stages[idx] if idx < len(stages) else 'Complete'}"
    elif phase == "offseason":
        stages = state.get("offseason_stages") or []
        idx = int(state.get("offseason_stage_index", 0) or 0)
        week_label = f"Offseason — {stages[idx] if idx < len(stages) else 'Complete'}"
    elif phase == "playoffs":
        week_label = "Playoffs"

    # Submission progress — human teams + auto/cpu count as submitted for progress
    human_team_names = {str(m["team_name"]) for m in human_members}
    submitted_humans = len([t for t in human_team_names if t in submitted])
    auto_teams = {
        str(m["team_name"])
        for m in human_members
        if str(m.get("control_mode") or "") == "auto" and m.get("team_name")
    }
    with db() as conn:
        auto_rows = conn.execute(
            """
            SELECT team_name FROM league_members
            WHERE league_id=? AND status='active' AND control_mode IN ('auto', 'cpu', 'vacant') AND team_name IS NOT NULL
            """,
            (league_id,),
        ).fetchall()
    cpu_submitted_count = len(auto_rows) + len(auto_teams)
    accountable = len(human_team_names) + len(auto_rows)
    submitted_total = submitted_humans + len(auto_rows) + len([t for t in auto_teams if t not in submitted])
    submitted_total = min(accountable if accountable else team_count, submitted_humans + len(auto_rows))
    progress_denominator = accountable if accountable else team_count
    progress_pct = int(round(100 * submitted_total / progress_denominator)) if progress_denominator else 0

    division_submissions = []
    for div_name, team_names in sorted(divisions.items()):
        div_humans = [t for t in team_names if t in human_team_names]
        div_submitted = [t for t in team_names if t in submitted or t not in human_team_names]
        division_submissions.append(
            {
                "division": div_name,
                "submitted_count": len(div_submitted),
                "total_count": len(team_names),
                "teams": [
                    {
                        "name": t,
                        "submitted": t in submitted or t not in human_team_names,
                        "is_human": t in human_team_names,
                    }
                    for t in team_names
                ],
            }
        )

    acting = acting_team_name or None
    your_submitted = acting in submitted if acting else False
    unsubmit_locked = _is_unsubmit_locked(league_row)
    your_status = {
        "submitted": your_submitted,
        "can_unsubmit": your_submitted and not unsubmit_locked,
        "label": "You're submitted" if your_submitted else "Not submitted yet",
        "sub_label": (
            f"Locked for {week_label}"
            if your_submitted and unsubmit_locked
            else (f"Locked for {week_label}" if your_submitted else f"Complete prep for {week_label}")
        ),
    }

    # Featured game
    featured_game = None
    if acting and phase == "regular" and weeks:
        wk_idx = max(0, current_week - 1)
        if wk_idx < len(weeks):
            for g in weeks[wk_idx] or []:
                if not isinstance(g, dict):
                    continue
                home = str(g.get("home") or "")
                away = str(g.get("away") or "")
                if acting not in (home, away):
                    continue
                is_home = acting == home
                opp = away if is_home else home
                featured_game = {
                    "week": current_week,
                    "your_team": acting,
                    "opponent": opp,
                    "is_home": is_home,
                    "your_record": _record_label(teams_meta.get(acting, {"name": acting}), standings),
                    "opponent_record": _record_label(teams_meta.get(opp, {"name": opp}), standings),
                    "your_initials": _team_initials(acting),
                    "opponent_initials": _team_initials(opp),
                    "division": _division_key(teams_meta.get(acting, {})),
                    "tags": [],
                }
                rivals = teams_meta.get(acting, {}).get("rivals") or []
                if isinstance(rivals, list) and opp in rivals:
                    featured_game["tags"].append("Rivalry")
                break

    # Full slate
    slate_games: List[Dict[str, Any]] = []
    if phase == "regular" and weeks:
        wk_idx = max(0, current_week - 1)
        if wk_idx < len(weeks):
            for g in weeks[wk_idx] or []:
                if not isinstance(g, dict):
                    continue
                home = str(g.get("home") or "")
                away = str(g.get("away") or "")
                if not home or not away:
                    continue
                div = _division_key(teams_meta.get(home, {}))
                notable = False
                tags: List[str] = []
                rh = teams_meta.get(home, {}).get("rivals") or []
                if isinstance(rh, list) and away in rh:
                    notable = True
                    tags.append("Rivalry")
                hw = int((standings.get(home) or {}).get("wins", 0) or 0)
                aw = int((standings.get(away) or {}).get("wins", 0) or 0)
                if hw >= 5 and aw >= 5:
                    notable = True
                    tags.append("Top teams")
                slate_games.append(
                    {
                        "home": home,
                        "away": away,
                        "home_initials": _team_initials(home),
                        "away_initials": _team_initials(away),
                        "division": div,
                        "notable": notable,
                        "tags": tags,
                    }
                )

    # Standings by division
    standings_by_division = []
    for div_name, team_names in sorted(divisions.items()):
        rows = []
        for i, tname in enumerate(team_names, start=1):
            rows.append(
                {
                    "rank": i,
                    "team": tname,
                    "record": _record_label(teams_meta.get(tname, {"name": tname}), standings),
                    "is_you": tname == acting,
                }
            )
        standings_by_division.append({"division": div_name, "rows": rows})

    full_league_standings = []
    sorted_teams = sorted(
        teams_meta.keys(),
        key=lambda n: (
            -int((standings.get(n) or {}).get("wins", 0) or 0),
            int((standings.get(n) or {}).get("losses", 0) or 0),
            n,
        ),
    )
    for i, tname in enumerate(sorted_teams, start=1):
        full_league_standings.append(
            {
                "rank": i,
                "team": tname,
                "record": _record_label(teams_meta.get(tname, {"name": tname}), standings),
                "division": _division_key(teams_meta.get(tname, {})),
                "is_you": tname == acting,
            }
        )

    # Activity: coach actions (submit/invite/etc.) first, then recent results
    activity: List[Dict[str, Any]] = []
    with db() as conn:
        log_rows = conn.execute(
            """
            SELECT action, detail_json, created_at FROM league_activity_log
            WHERE league_id=? ORDER BY created_at DESC LIMIT 12
            """,
            (league_id,),
        ).fetchall()
    for lr in log_rows:
        detail = {}
        try:
            detail = json.loads(lr["detail_json"] or "{}")
        except Exception:
            pass
        activity.append(
            {
                "icon": str(detail.get("icon") or "📋"),
                "text": str(detail.get("text") or lr["action"]),
                "time_label": _activity_time_label(int(lr["created_at"] or 0)),
                "created_at": int(lr["created_at"] or 0),
            }
        )

    week_results = state.get("week_results") or []
    if current_week > 1 and isinstance(week_results, list):
        prev_idx = current_week - 2
        if 0 <= prev_idx < len(week_results):
            for gi, g in enumerate(weeks[prev_idx] if prev_idx < len(weeks) else []):
                if gi >= len(week_results[prev_idx]):
                    break
                slot = week_results[prev_idx][gi]
                if not isinstance(slot, dict) or not slot.get("played"):
                    continue
                home = str(g.get("home") or "")
                away = str(g.get("away") or "")
                hs = int(slot.get("home_score", 0) or 0)
                aws = int(slot.get("away_score", 0) or 0)
                if hs == aws:
                    continue
                winner = home if hs > aws else away
                loser = away if hs > aws else home
                wscore = max(hs, aws)
                lscore = min(hs, aws)
                activity.append(
                    {
                        "icon": "🏈",
                        "text": f"{winner} defeated {loser} {wscore}–{lscore}",
                        "time_label": f"Week {current_week - 1}",
                        "created_at": 0,
                    }
                )
    activity = activity[:12]

    chat_messages = list_league_chat_messages(league_id, user_id, limit=40)

    deadline_iso = _advance_countdown_iso(league_row)
    league_name = str(league_row.get("name") or "League")
    crest = "".join(p[0] for p in league_name.split()[:2]).upper()[:2] or "LG"

    return {
        "league_id": league_id,
        "league_name": league_name,
        "league_crest": crest,
        "league_subtitle": f"{team_count} Teams · {division_count} Divisions",
        "week_label": week_label,
        "season_phase": phase,
        "stage_key": stage_key,
        "countdown_label": "Advances in" if deadline_iso else None,
        "countdown_value": _format_countdown(deadline_iso),
        "advance_deadline_iso": deadline_iso,
        "progress": {
            "submitted": submitted_total,
            "total": progress_denominator,
            "percent": progress_pct,
        },
        "your_status": your_status,
        "division_submissions": division_submissions,
        "featured_game": featured_game,
        "slate_games": slate_games,
        "standings_by_division": standings_by_division,
        "full_league_standings": full_league_standings,
        "activity": activity,
        "chat_enabled": True,
        "chat_messages": chat_messages,
        "is_commissioner": is_commish or is_owner,
        "is_read_only_admin": is_owner,
        "can_run_league": bool(is_commish),
        "acting_team_name": acting,
        "state_version": int(league_row.get("state_version") or 0),
    }


def create_admin_league(
    owner_user_id: str,
    *,
    name: str,
    user_team: str,
    coach_config: Dict[str, Any],
    start_year: Optional[int] = None,
    teams_data: Optional[Dict[str, Any]] = None,
    allow_user_coach_firing: bool = False,
    transfers_disabled: bool = False,
    commissioner_user_id: Optional[str] = None,
    commissioner_email: Optional[str] = None,
    timezone: str = "America/New_York",
) -> Dict[str, Any]:
    """Platform owner creates a multiplayer league (same options as single-player new dynasty)."""
    from backend.services.league_service import create_save

    if not is_platform_owner_user(owner_user_id):
        raise PermissionError("only platform owner can create leagues")

    if teams_data is not None:
        team_rows = teams_data.get("teams") if isinstance(teams_data.get("teams"), list) else []
        if not team_rows:
            raise ValueError("teams_data must include a teams array")
        if len(team_rows) > 120:
            raise ValueError("multiplayer leagues support at most 120 teams")
    user_team = str(user_team or "").strip()
    if not user_team:
        raise ValueError("user_team required")

    league_id = str(uuid.uuid4())
    save_dir = _league_dir(league_id)
    os.makedirs(save_dir, exist_ok=True)

    bootstrap_name = f"__mp_bootstrap_{league_id[:8]}"
    create_kwargs: Dict[str, Any] = {
        "start_year": start_year,
        "allow_user_coach_firing": allow_user_coach_firing,
        "transfers_disabled": transfers_disabled,
    }
    if teams_data is not None:
        create_kwargs["teams_data"] = teams_data
    bootstrap = create_save(
        owner_user_id,
        bootstrap_name,
        user_team,
        coach_config or {},
        **create_kwargs,
    )
    save_id = bootstrap.get("save_id")
    with db() as conn:
        row = conn.execute("SELECT save_dir FROM saves WHERE id=?", (save_id,)).fetchone()
    bootstrap_dir = str(row["save_dir"] or "") if row else ""
    if not bootstrap_dir or not os.path.isdir(bootstrap_dir):
        raise RuntimeError("failed to bootstrap league save")

    import shutil

    for entry in os.listdir(bootstrap_dir):
        shutil.move(os.path.join(bootstrap_dir, entry), os.path.join(save_dir, entry))
    shutil.rmtree(bootstrap_dir, ignore_errors=True)

    # Remove bootstrap index row
    with db() as conn:
        conn.execute("DELETE FROM saves WHERE id=?", (save_id,))

    # Multiplayer: no opening schedule picker — auto-build the shared calendar and start preseason.
    from backend.services.league_service import ensure_multiplayer_opening_schedule

    state = _load_state(save_dir)
    state["multiplayer_league"] = True
    state["multiplayer"] = {"league_id": league_id}
    state["user_team"] = user_team
    ensure_multiplayer_opening_schedule(state)
    _save_state(save_dir, state)

    now = _now()
    commish_id = resolve_commissioner_user_id(
        owner_user_id,
        commissioner_user_id=commissioner_user_id,
        commissioner_email=commissioner_email,
    )
    commish_pin = generate_team_pin()
    commish_lookup = lookup_user_by_email(_user_email(commish_id)) or {}
    commish_display = str(
        commish_lookup.get("email") or commish_lookup.get("username") or commish_id
    ).strip()
    rules = {
        "transfers_enabled": not bool(transfers_disabled),
        "carousel_enabled": True,
        "allow_user_coach_firing": bool(allow_user_coach_firing),
    }
    with db() as conn:
        conn.execute(
            """
            INSERT INTO leagues (
              id, name, save_dir, status, created_by_user_id, commissioner_user_id,
              timezone, rules_json, created_at, updated_at
            ) VALUES (?,?,?,?,?,?,?,?,?,?)
            """,
            (
                league_id,
                name.strip(),
                save_dir,
                "active",
                owner_user_id,
                commish_id,
                timezone,
                json.dumps(rules),
                now,
                now,
            ),
        )
        conn.execute(
            """
            INSERT INTO league_members (
              id, league_id, user_id, team_name, role, status, control_mode,
              pin_hash, pin_updated_at, coach_setup_complete, joined_at
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                str(uuid.uuid4()),
                league_id,
                commish_id,
                user_team,
                "commissioner",
                "active",
                "human",
                _hash_pin(commish_pin),
                now,
                1,
                now,
            ),
        )
        conn.execute(
            """
            INSERT INTO league_activity_log (id, league_id, actor_user_id, action, detail_json, created_at)
            VALUES (?,?,?,?,?,?)
            """,
            (
                str(uuid.uuid4()),
                league_id,
                owner_user_id,
                "league_created",
                json.dumps({"text": f"League «{name.strip()}» created", "icon": "🏟️"}),
                now,
            ),
        )

    return {
        "league_id": league_id,
        "name": name.strip(),
        "save_dir": save_dir,
        "commissioner_user_id": commish_id,
        "commissioner_email": commish_display,
        "commissioner_team": user_team,
        "commissioner_pin": commish_pin,
    }


def delete_admin_league(owner_user_id: str, league_id: str) -> Dict[str, Any]:
    """Platform owner permanently deletes a multiplayer league and its save files."""
    if not is_platform_owner_user(owner_user_id):
        raise PermissionError("only platform owner can delete leagues")
    league_row = _load_league_row(league_id)
    if not league_row:
        raise ValueError("league not found")
    save_dir = str(league_row.get("save_dir") or "").strip()
    league_name = str(league_row.get("name") or league_id)
    with db() as conn:
        conn.execute("DELETE FROM league_chat_messages WHERE league_id=?", (league_id,))
        conn.execute("DELETE FROM league_activity_log WHERE league_id=?", (league_id,))
        conn.execute("DELETE FROM league_submit_status WHERE league_id=?", (league_id,))
        conn.execute("DELETE FROM league_invites WHERE league_id=?", (league_id,))
        conn.execute("DELETE FROM league_members WHERE league_id=?", (league_id,))
        conn.execute("DELETE FROM leagues WHERE id=?", (league_id,))
    if save_dir:
        import shutil

        try:
            if os.path.isdir(save_dir):
                shutil.rmtree(save_dir, ignore_errors=True)
        except Exception:
            pass
        # Also remove empty parent league folder if this was leagues/<id>
        parent = os.path.dirname(save_dir.rstrip("\\/"))
        try:
            if parent and os.path.isdir(parent) and not os.listdir(parent):
                os.rmdir(parent)
        except Exception:
            pass
    return {"ok": True, "league_id": league_id, "name": league_name}


def assign_team_to_member(
    league_id: str,
    actor_user_id: str,
    target_user_id: str,
    team_name: str,
    *,
    pin: Optional[str] = None,
) -> Dict[str, Any]:
    league_row = _require_commish_write(league_id, actor_user_id)
    team_name = str(team_name or "").strip()
    if not team_name:
        raise ValueError("team_name required")
    pin_value = (pin or generate_team_pin()).strip()
    if not re.fullmatch(r"\d{6}", pin_value):
        raise ValueError("PIN must be 6 digits")

    save_dir = str(league_row.get("save_dir") or "")
    state = _load_state(save_dir)
    team_names = {
        str(r.get("name") or "")
        for r in (state.get("teams") or [])
        if isinstance(r, dict) and r.get("name")
    }
    if team_name not in team_names:
        raise ValueError(f"{team_name} is not a team in this league")
    if len(team_names) > 120:
        raise ValueError("league exceeds the 120-team maximum")

    now = _now()
    with db() as conn:
        taken = conn.execute(
            """
            SELECT user_id FROM league_members
            WHERE league_id=? AND team_name=? AND status='active' AND user_id != ?
            """,
            (league_id, team_name, target_user_id),
        ).fetchone()
        if taken:
            raise ValueError(f"{team_name} is already assigned to another coach")
        existing = conn.execute(
            """
            SELECT id, team_name FROM league_members
            WHERE league_id=? AND user_id=? AND status != 'removed'
            """,
            (league_id, target_user_id),
        ).fetchone()
        if existing:
            conn.execute(
                """
                UPDATE league_members
                SET team_name=?, status='active', pin_hash=?, pin_updated_at=?,
                    control_mode='human', coach_setup_complete=0
                WHERE league_id=? AND user_id=? AND status != 'removed'
                """,
                (team_name, _hash_pin(pin_value), now, league_id, target_user_id),
            )
        else:
            conn.execute(
                """
                INSERT INTO league_members (
                  id, league_id, user_id, team_name, role, status, control_mode,
                  pin_hash, pin_updated_at, coach_setup_complete, joined_at
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?)
                """,
                (
                    str(uuid.uuid4()),
                    league_id,
                    target_user_id,
                    team_name,
                    "coach",
                    "active",
                    "human",
                    _hash_pin(pin_value),
                    now,
                    0,
                    now,
                ),
            )
    return {"team_name": team_name, "pin": pin_value, "user_id": target_user_id}


def assign_team_by_email(
    league_id: str,
    actor_user_id: str,
    email: str,
    team_name: str,
    *,
    pin: Optional[str] = None,
) -> Dict[str, Any]:
    found = lookup_user_by_email(email)
    if not found:
        raise ValueError(
            f"No account found for {email.strip()}. They must sign in to FND once before you can assign a team."
        )
    return assign_team_to_member(
        league_id,
        actor_user_id,
        str(found["user_id"]),
        team_name,
        pin=pin,
    )


def reset_member_pin(
    league_id: str,
    actor_user_id: str,
    target_user_id: str,
    *,
    pin: Optional[str] = None,
) -> Dict[str, Any]:
    _require_commish_write(league_id, actor_user_id)
    with db() as conn:
        row = conn.execute(
            """
            SELECT team_name FROM league_members
            WHERE league_id=? AND user_id=? AND status='active' AND team_name IS NOT NULL
            """,
            (league_id, target_user_id),
        ).fetchone()
    if not row or not row["team_name"]:
        raise ValueError("member has no assigned team")
    return assign_team_to_member(
        league_id,
        actor_user_id,
        target_user_id,
        str(row["team_name"]),
        pin=pin,
    )


def update_league_settings(
    league_id: str,
    actor_user_id: str,
    *,
    advance_mode: Optional[str] = None,
    advance_deadline_dow: Optional[int] = None,
    advance_deadline_time_local: Optional[str] = None,
    submit_lockout_minutes: Optional[int] = None,
    timezone: Optional[str] = None,
) -> Dict[str, Any]:
    league_row = _load_league_row(league_id)
    if not league_row:
        raise ValueError("league not found")
    if str(league_row.get("commissioner_user_id") or "") != actor_user_id:
        raise PermissionError("commissioner only")

    mode = str(advance_mode or league_row.get("advance_mode") or "manual").strip().lower()
    if mode not in ("manual", "auto"):
        raise ValueError("advance_mode must be manual or auto")
    dow = advance_deadline_dow if advance_deadline_dow is not None else league_row.get("advance_deadline_dow")
    time_local = (
        advance_deadline_time_local
        if advance_deadline_time_local is not None
        else league_row.get("advance_deadline_time_local")
    )
    lockout = (
        int(submit_lockout_minutes)
        if submit_lockout_minutes is not None
        else int(league_row.get("submit_lockout_minutes") or 5)
    )
    tz = str(timezone or league_row.get("timezone") or "America/New_York").strip()
    now = _now()
    with db() as conn:
        conn.execute(
            """
            UPDATE leagues
            SET advance_mode=?, advance_deadline_dow=?, advance_deadline_time_local=?,
                submit_lockout_minutes=?, timezone=?, updated_at=?
            WHERE id=?
            """,
            (mode, dow, str(time_local or "23:59"), lockout, tz, now, league_id),
        )
    return {
        "advance_mode": mode,
        "advance_deadline_dow": dow,
        "advance_deadline_time_local": str(time_local or "23:59"),
        "submit_lockout_minutes": lockout,
        "timezone": tz,
    }


def _mp_week_sim_context(league_id: str, state: Dict[str, Any]) -> Tuple[set[str], set[str]]:
    stage_key = _stage_key_from_state(state)
    submitted = _submitted_teams(league_id, stage_key)
    human = {str(m["team_name"]) for m in _human_teams(league_id) if m.get("team_name")}
    return human, submitted


def apply_league_coach_prep(
    league_id: str,
    user_id: str,
    team_name: str,
    prep: Dict[str, Any],
) -> Dict[str, Any]:
    """Save coach prep for the current stage without advancing the shared league."""
    import copy

    from backend.services.league_service import apply_coach_prep_state

    league_row = _verify_team_game_access(league_id, user_id, team_name)
    save_dir = str(league_row.get("save_dir") or "")
    canonical = _load_state(save_dir)
    working = copy.deepcopy(canonical)
    working["user_team"] = team_name
    working = apply_coach_prep_state(working, prep if isinstance(prep, dict) else {})
    merged = _merge_coach_state_into_canonical(canonical, working, team_name)
    merged["user_team"] = team_name
    mp = merged.get("multiplayer")
    if not isinstance(mp, dict):
        mp = {}
    mp["league_id"] = league_id
    mp["team_name"] = team_name
    merged["multiplayer"] = mp
    _save_state(save_dir, merged)
    now = _now()
    with db() as conn:
        conn.execute(
            "UPDATE leagues SET state_version=state_version+1, updated_at=? WHERE id=?",
            (now, league_id),
        )
    return get_league_game_bundle(league_id, user_id, team_name)


def commish_advance_league(league_id: str, user_id: str) -> Dict[str, Any]:
    """Sim/advance one league step (commissioner)."""
    from backend.services.league_service import (
        _advance_playoff_one_round_state,
        advance_offseason_state,
        advance_preseason_state,
        sim_week_state,
    )
    from systems.league_history import load_league_history
    from systems.save_system import league_history_path

    league_row = _verify_commish_game_access(league_id, user_id)
    save_dir = str(league_row.get("save_dir") or "")
    state = _load_state(save_dir)
    phase = str(state.get("season_phase") or "regular").strip().lower()

    league_history: Dict[str, Any] = {"seasons": []}
    try:
        league_history = load_league_history(league_history_path(save_dir))
    except Exception:
        pass

    mp_human, mp_submitted = _mp_week_sim_context(league_id, state)
    state.pop("user_team", None)

    if phase == "preseason":
        out = advance_preseason_state(state, {})
        state = out.get("state") if isinstance(out, dict) and isinstance(out.get("state"), dict) else state
        action_label = "Preseason advanced"
    elif phase == "regular":
        state = sim_week_state(state, mp_human_teams=mp_human, mp_submitted_teams=mp_submitted)
        action_label = f"Week {int(state.get('current_week', 1))} simulated"
    elif phase == "playoffs":
        state = _advance_playoff_one_round_state(state)
        action_label = "Playoff round advanced"
    elif phase == "offseason":
        state = advance_offseason_state(state, {}, league_history=league_history)
        action_label = "Offseason advanced"
    elif phase == "schedule_planning":
        from backend.services.league_service import advance_schedule_planning_league_state

        state = advance_schedule_planning_league_state(state, league_history=league_history)
        action_label = "Schedule planning completed (auto picks)"
    else:
        raise ValueError(f"Cannot advance league from season_phase={phase!r}")

    _save_state(save_dir, state)
    now = _now()
    with db() as conn:
        conn.execute(
            "UPDATE leagues SET state_version=state_version+1, updated_at=? WHERE id=?",
            (now, league_id),
        )
        conn.execute(
            """
            INSERT INTO league_activity_log (id, league_id, actor_user_id, action, detail_json, created_at)
            VALUES (?,?,?,?,?,?)
            """,
            (
                str(uuid.uuid4()),
                league_id,
                user_id,
                "commish_advance",
                json.dumps({"text": action_label, "icon": "⏩"}),
                now,
            ),
        )
        if phase == "regular":
            unsubmitted = sorted(mp_human - mp_submitted)
            if unsubmitted:
                conn.execute(
                    """
                    INSERT INTO league_activity_log (id, league_id, actor_user_id, action, detail_json, created_at)
                    VALUES (?,?,?,?,?,?)
                    """,
                    (
                        str(uuid.uuid4()),
                        league_id,
                        user_id,
                        "cpu_week",
                        json.dumps(
                            {
                                "text": f"CPU week for: {', '.join(unsubmitted)}",
                                "icon": "🤖",
                            }
                        ),
                        now,
                    ),
                )

    return {
        "ok": True,
        "season_phase": str(state.get("season_phase") or ""),
        "current_week": int(state.get("current_week", 1) or 1),
        "message": action_label,
    }


def build_commish_dashboard(league_id: str, user_id: str) -> Dict[str, Any]:
    league_row, read_only = _verify_commish_view_access(league_id, user_id)
    if not read_only:
        try_auto_advance_league(league_id)
        league_row = _load_league_row(league_id) or league_row
    save_dir = str(league_row.get("save_dir") or "")
    state = _load_state(save_dir)
    teams_meta = _teams_meta_from_state(state)
    all_teams = sorted(teams_meta.keys(), key=lambda n: n.lower())
    stage_key = _stage_key_from_state(state)
    submitted = _submitted_teams(league_id, stage_key)

    phase = str(state.get("season_phase") or "regular").strip().lower()
    current_week = int(state.get("current_week", 1) or 1)
    weeks = state.get("weeks") or []
    total_weeks = len(weeks) if isinstance(weeks, list) and weeks else 12
    week_label = f"Week {current_week} of {total_weeks}"
    if phase == "preseason":
        stages = state.get("preseason_stages") or []
        idx = int(state.get("preseason_stage_index", 0) or 0)
        week_label = f"Preseason — {stages[idx] if idx < len(stages) else 'Complete'}"
    elif phase == "offseason":
        stages = state.get("offseason_stages") or []
        idx = int(state.get("offseason_stage_index", 0) or 0)
        week_label = f"Offseason — {stages[idx] if idx < len(stages) else 'Complete'}"
    elif phase == "playoffs":
        week_label = "Playoffs"

    with db() as conn:
        member_rows = conn.execute(
            """
            SELECT m.user_id, m.team_name, m.role, m.status, m.control_mode, m.coach_setup_complete,
                   u.email, u.username
            FROM league_members m
            LEFT JOIN users u ON u.id = m.user_id
            WHERE m.league_id=? AND m.status != 'removed'
            ORDER BY m.joined_at ASC
            """,
            (league_id,),
        ).fetchall()
        invite_rows = conn.execute(
            """
            SELECT id, email, status, created_at FROM league_invites
            WHERE league_id=? AND status='pending'
            ORDER BY created_at DESC
            """,
            (league_id,),
        ).fetchall()

    assigned_teams = {
        str(r["team_name"])
        for r in member_rows
        if r["team_name"] and str(r["status"]) == "active"
    }
    vacant_teams = [t for t in all_teams if t not in assigned_teams]

    members: List[Dict[str, Any]] = []
    for r in member_rows:
        team = str(r["team_name"] or "")
        email = str(r["email"] or r["username"] or "").strip()
        members.append(
            {
                "user_id": str(r["user_id"]),
                "email": email,
                "team_name": team or None,
                "role": str(r["role"] or "coach"),
                "status": str(r["status"] or ""),
                "control_mode": str(r["control_mode"] or "human"),
                "coach_setup_complete": bool(r["coach_setup_complete"]),
                "submitted": bool(team and team in submitted),
            }
        )

    pending_invites = [
        {
            "invite_id": str(inv["id"]),
            "email": str(inv["email"]),
            "status": str(inv["status"]),
            "created_at": int(inv["created_at"]),
        }
        for inv in invite_rows
    ]

    human_team_names = {
        str(r["team_name"]) for r in member_rows if r["team_name"] and str(r["status"]) == "active"
    }
    submitted_humans = len([t for t in human_team_names if t in submitted])
    progress_denominator = max(len(human_team_names), 1)
    progress_pct = int(round(100 * submitted_humans / progress_denominator))

    league_name = str(league_row.get("name") or "League")
    deadline_iso = _advance_countdown_iso(league_row)

    acting_team: Optional[str] = None
    coach_setup_complete = False
    for r in member_rows:
        if str(r["user_id"]) == user_id and r["team_name"] and str(r["status"]) == "active":
            acting_team = str(r["team_name"])
            coach_setup_complete = bool(r["coach_setup_complete"])
            break
    your_submitted = bool(acting_team and acting_team in submitted)
    unsubmit_locked = _is_unsubmit_locked(league_row)
    your_status = {
        "submitted": your_submitted,
        "can_unsubmit": your_submitted and not unsubmit_locked,
        "label": "You're submitted" if your_submitted else "Not submitted yet",
        "sub_label": (
            f"Locked for {week_label}"
            if your_submitted and unsubmit_locked
            else (f"Locked for {week_label}" if your_submitted else f"Complete prep for {week_label}")
        ),
    }

    return {
        "league_id": league_id,
        "league_name": league_name,
        "week_label": week_label,
        "season_phase": phase,
        "stage_key": stage_key,
        "progress": {
            "submitted": submitted_humans,
            "total": len(human_team_names),
            "percent": progress_pct,
        },
        "settings": {
            "advance_mode": str(league_row.get("advance_mode") or "manual"),
            "advance_deadline_dow": league_row.get("advance_deadline_dow"),
            "advance_deadline_time_local": str(league_row.get("advance_deadline_time_local") or "23:59"),
            "submit_lockout_minutes": int(league_row.get("submit_lockout_minutes") or 5),
            "timezone": str(league_row.get("timezone") or "America/New_York"),
            "advance_deadline_iso": deadline_iso,
            "countdown_value": _format_countdown(deadline_iso),
        },
        "members": members,
        "pending_invites": pending_invites,
        "vacant_teams": vacant_teams,
        "all_teams": all_teams,
        "state_version": int(league_row.get("state_version") or 0),
        "is_read_only_admin": read_only,
        "can_manage": not read_only,
        "acting_team_name": acting_team,
        "coach_setup_complete": coach_setup_complete,
        "your_status": your_status,
    }


def _is_unsubmit_locked(league_row: Dict[str, Any]) -> bool:
    """True when coaches can no longer unsubmit (lockout window before auto-advance)."""
    if str(league_row.get("advance_mode") or "manual").lower() != "auto":
        return False
    deadline_iso = _advance_countdown_iso(league_row)
    if not deadline_iso:
        return False
    lockout_minutes = int(league_row.get("submit_lockout_minutes") or 5)
    try:
        deadline = datetime.fromisoformat(deadline_iso)
        if deadline.tzinfo is None:
            deadline = deadline.replace(tzinfo=ZoneInfo("UTC"))
        now = datetime.now(deadline.tzinfo)
        lockout_start = deadline - timedelta(minutes=lockout_minutes)
        return now >= lockout_start
    except Exception:
        return False


def _verify_active_team_member(league_id: str, user_id: str, team_name: str) -> None:
    with db() as conn:
        row = conn.execute(
            """
            SELECT 1 FROM league_members
            WHERE league_id=? AND user_id=? AND team_name=? AND status='active'
            LIMIT 1
            """,
            (league_id, user_id, team_name),
        ).fetchone()
    if not row:
        raise PermissionError("not assigned to this team")


def submit_league_week(league_id: str, user_id: str, team_name: str) -> Dict[str, Any]:
    league_row = _load_league_row(league_id)
    if not league_row:
        raise ValueError("league not found")
    _verify_active_team_member(league_id, user_id, team_name)
    save_dir = str(league_row.get("save_dir") or "")
    state = _load_state(save_dir)
    stage_key = _stage_key_from_state(state)
    now = _now()
    with db() as conn:
        conn.execute(
            """
            INSERT INTO league_submit_status (league_id, user_id, team_name, stage_key, submitted_at)
            VALUES (?,?,?,?,?)
            ON CONFLICT(league_id, user_id, team_name, stage_key)
            DO UPDATE SET submitted_at=excluded.submitted_at
            """,
            (league_id, user_id, team_name, stage_key, now),
        )
        conn.execute(
            """
            INSERT INTO league_activity_log (id, league_id, actor_user_id, action, detail_json, created_at)
            VALUES (?,?,?,?,?,?)
            """,
            (
                str(uuid.uuid4()),
                league_id,
                user_id,
                "submit_week",
                json.dumps({"text": f"{team_name} submitted for {stage_key}", "icon": "✅"}),
                now,
            ),
        )
    return {"ok": True, "team_name": team_name, "stage_key": stage_key, "submitted_at": now}


def unsubmit_league_week(league_id: str, user_id: str, team_name: str) -> Dict[str, Any]:
    league_row = _load_league_row(league_id)
    if not league_row:
        raise ValueError("league not found")
    _verify_active_team_member(league_id, user_id, team_name)
    if _is_unsubmit_locked(league_row):
        lockout = int(league_row.get("submit_lockout_minutes") or 5)
        raise ValueError(
            f"Cannot unsubmit within {lockout} minutes of the advance deadline."
        )
    save_dir = str(league_row.get("save_dir") or "")
    state = _load_state(save_dir)
    stage_key = _stage_key_from_state(state)
    with db() as conn:
        conn.execute(
            """
            DELETE FROM league_submit_status
            WHERE league_id=? AND user_id=? AND team_name=? AND stage_key=?
            """,
            (league_id, user_id, team_name, stage_key),
        )
        now = _now()
        conn.execute(
            """
            INSERT INTO league_activity_log (id, league_id, actor_user_id, action, detail_json, created_at)
            VALUES (?,?,?,?,?,?)
            """,
            (
                str(uuid.uuid4()),
                league_id,
                user_id,
                "unsubmit_week",
                json.dumps({"text": f"{team_name} unsubmitted for {stage_key}", "icon": "↩"}),
                now,
            ),
        )
    return {"ok": True, "team_name": team_name, "stage_key": stage_key}


def _activity_time_label(ts: int) -> str:
    if not ts:
        return ""
    try:
        now = _now()
        delta = max(0, now - int(ts))
        if delta < 60:
            return "Just now"
        if delta < 3600:
            mins = delta // 60
            return f"{mins}m ago"
        if delta < 86400:
            hours = delta // 3600
            return f"{hours}h ago"
        if delta < 86400 * 7:
            days = delta // 86400
            return f"{days}d ago"
        return datetime.fromtimestamp(int(ts)).strftime("%b %d")
    except Exception:
        return ""


def _verify_league_member_or_owner(league_id: str, user_id: str) -> Dict[str, Any]:
    league_row = _load_league_row(league_id)
    if not league_row:
        raise ValueError("league not found")
    if is_platform_owner_user(user_id):
        return league_row
    if str(league_row.get("commissioner_user_id") or "") == user_id:
        return league_row
    with db() as conn:
        row = conn.execute(
            """
            SELECT team_name, status FROM league_members
            WHERE league_id=? AND user_id=? AND status != 'removed'
            LIMIT 1
            """,
            (league_id, user_id),
        ).fetchone()
    if not row:
        raise PermissionError("not a league member")
    return league_row


def list_league_chat_messages(
    league_id: str,
    user_id: str,
    *,
    limit: int = 40,
) -> List[Dict[str, Any]]:
    _verify_league_member_or_owner(league_id, user_id)
    limit = max(1, min(100, int(limit or 40)))
    with db() as conn:
        rows = conn.execute(
            """
            SELECT id, user_id, team_name, display_name, body, created_at
            FROM league_chat_messages
            WHERE league_id=?
            ORDER BY created_at DESC
            LIMIT ?
            """,
            (league_id, limit),
        ).fetchall()
    messages = [
        {
            "id": str(r["id"]),
            "user_id": str(r["user_id"]),
            "team_name": r["team_name"],
            "display_name": str(r["display_name"] or "Coach"),
            "body": str(r["body"] or ""),
            "created_at": int(r["created_at"] or 0),
            "time_label": _activity_time_label(int(r["created_at"] or 0)),
            "is_you": str(r["user_id"]) == user_id,
        }
        for r in rows
    ]
    messages.reverse()
    return messages


def post_league_chat_message(
    league_id: str,
    user_id: str,
    body: str,
    *,
    team_name: Optional[str] = None,
) -> Dict[str, Any]:
    _verify_league_member_or_owner(league_id, user_id)
    text = " ".join(str(body or "").split()).strip()
    if not text:
        raise ValueError("message required")
    if len(text) > 500:
        raise ValueError("message must be 500 characters or fewer")

    display = ""
    acting_team = str(team_name or "").strip() or None
    with db() as conn:
        mem = conn.execute(
            """
            SELECT team_name FROM league_members
            WHERE league_id=? AND user_id=? AND status='active'
            ORDER BY team_name IS NULL, team_name
            LIMIT 1
            """,
            (league_id, user_id),
        ).fetchone()
    if mem and mem["team_name"]:
        if not acting_team:
            acting_team = str(mem["team_name"])
        display = acting_team
    if not display:
        display = _user_email(user_id) or "Coach"
        if "@" in display:
            display = display.split("@", 1)[0]

    now = _now()
    msg_id = str(uuid.uuid4())
    with db() as conn:
        conn.execute(
            """
            INSERT INTO league_chat_messages
              (id, league_id, user_id, team_name, display_name, body, created_at)
            VALUES (?,?,?,?,?,?,?)
            """,
            (msg_id, league_id, user_id, acting_team, display, text, now),
        )
    return {
        "id": msg_id,
        "user_id": user_id,
        "team_name": acting_team,
        "display_name": display,
        "body": text,
        "created_at": now,
        "time_label": "Just now",
        "is_you": True,
    }
