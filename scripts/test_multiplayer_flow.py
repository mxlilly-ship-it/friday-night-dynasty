"""End-to-end checks for multiplayer league coach/commish flows (items 9-15)."""

from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile
import uuid

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

# Isolate DB + league files for this run
_tmp = tempfile.mkdtemp(prefix="fnd_mp_test_")
os.environ["FND_PLATFORM_OWNER_EMAILS"] = "commish@example.com"
os.environ["FND_DATA_DIR"] = _tmp

from backend.storage.db import db, init_db  # noqa: E402
from backend.services import multiplayer_service as mp  # noqa: E402


def _insert_user(user_id: str, email: str) -> None:
    with db() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO users (id, username, email, entitlement_active) VALUES (?,?,?,1)",
            (user_id, email, email),
        )


def _minimal_state(team_a: str, team_b: str) -> dict:
    return {
        "save_name": "MP Test",
        "user_team": team_a,
        "season_phase": "regular",
        "current_week": 1,
        "current_year": 2026,
        "weeks": [[{"home": team_a, "away": team_b}]],
        "week_results": [[{"played": False}]],
        "standings": {
            team_a: {"wins": 0, "losses": 0},
            team_b: {"wins": 0, "losses": 0},
        },
        "teams": [
            {"name": team_a, "classification": "AAA", "region": "North", "coach": {"name": "Coach A"}},
            {"name": team_b, "classification": "AAA", "region": "North", "coach": {"name": "Coach B"}},
        ],
        "coach_gameplans_v2": {
            f"week:1:0:{team_a} vs {team_b}": {"offense_package": {"gameplan_mode": "grid"}},
            f"week:1:0:Other vs X": {"offense_package": {"gameplan_mode": "grid"}},
        },
    }


def main() -> None:
    init_db()
    commish_id = "user-commish"
    coach_id = "user-coach"
    other_id = "user-other"
    _insert_user(commish_id, "commish@example.com")
    _insert_user(coach_id, "coach@example.com")
    _insert_user(other_id, "other@example.com")

    league_id = str(uuid.uuid4())
    save_dir = os.path.join(_tmp, "leagues", league_id)
    os.makedirs(save_dir, exist_ok=True)
    team_a, team_b = "Alpha High", "Beta High"
    state = _minimal_state(team_a, team_b)
    with open(os.path.join(save_dir, "league_save.json"), "w", encoding="utf-8") as f:
        json.dump(state, f)

    now = mp._now()
    with db() as conn:
        conn.execute(
            """
            INSERT INTO leagues (
              id, name, save_dir, status, created_by_user_id, commissioner_user_id,
              timezone, advance_mode, submit_lockout_minutes, rules_json,
              state_version, sim_job_status, created_at, updated_at
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                league_id,
                "Test League",
                save_dir,
                "active",
                commish_id,
                commish_id,
                "America/New_York",
                "manual",
                5,
                "{}",
                0,
                "idle",
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
                team_a,
                "commissioner",
                "active",
                "human",
                mp._hash_pin("123456"),
                now,
                1,
                now,
            ),
        )

    # #13 invite + #14 duplicate invite / already member
    inv = mp.invite_user_to_league(league_id, commish_id, "coach@example.com")
    assert inv["status"] == "pending"
    assert inv.get("email_sent") is False  # no RESEND in test env
    try:
        mp.invite_user_to_league(league_id, commish_id, "coach@example.com")
        raise AssertionError("duplicate invite should fail")
    except ValueError as e:
        assert "pending invite" in str(e).lower()

    mp.sync_pending_invites_for_user(coach_id)
    try:
        mp.invite_user_to_league(league_id, commish_id, "coach@example.com")
        raise AssertionError("invite for existing member should fail")
    except ValueError as e:
        assert "already in this league" in str(e).lower()

    # #14 assign + duplicate team
    pin_res = mp.assign_team_by_email(league_id, commish_id, "coach@example.com", team_b)
    assert pin_res["team_name"] == team_b
    assert len(pin_res["pin"]) == 6
    try:
        mp.assign_team_by_email(league_id, commish_id, "other@example.com", team_b)
        raise AssertionError("duplicate team assign should fail")
    except ValueError as e:
        assert "already assigned" in str(e).lower()

    with db() as conn:
        conn.execute(
            """
            UPDATE league_members SET coach_setup_complete=1
            WHERE league_id=? AND user_id=?
            """,
            (league_id, coach_id),
        )

    # #3/#privacy gameplan filter on coach load
    bundle = mp.get_league_game_bundle(league_id, coach_id, team_b)
    gp = bundle["state"].get("coach_gameplans_v2") or {}
    assert all("Beta High" in k or k.startswith("bye:") for k in gp), gp

    # #9/#11 submit activity
    mp.submit_league_week(league_id, coach_id, team_b)
    dash = mp.build_league_dashboard(league_id, coach_id, acting_team_name=team_b)
    assert dash["your_status"]["submitted"] is True
    assert any("submitted" in (a.get("text") or "").lower() for a in dash["activity"])
    assert dash["chat_enabled"] is True

    # #12 chat
    msg = mp.post_league_chat_message(league_id, coach_id, "Ready for week 1", team_name=team_b)
    assert msg["body"] == "Ready for week 1"
    msgs = mp.list_league_chat_messages(league_id, coach_id)
    assert any(m["id"] == msg["id"] for m in msgs)
    dash2 = mp.build_league_dashboard(league_id, coach_id, acting_team_name=team_b)
    assert any(m["id"] == msg["id"] for m in dash2.get("chat_messages") or [])

    # #10 badges
    leagues = mp.list_leagues_for_user(coach_id)
    mine = next(x for x in leagues if x["league_id"] == league_id)
    assert "Submitted" in (mine.get("badges") or [])
    assert mine.get("submitted") is True

    # #14 cannot remove commissioner
    try:
        mp.remove_league_member(league_id, commish_id, commish_id)
        raise AssertionError("removing commissioner should fail")
    except ValueError as e:
        assert "commissioner" in str(e).lower()

    # unsubmit + activity
    mp.unsubmit_league_week(league_id, coach_id, team_b)
    dash3 = mp.build_league_dashboard(league_id, coach_id, acting_team_name=team_b)
    assert dash3["your_status"]["submitted"] is False
    assert any("unsubmitted" in (a.get("text") or "").lower() for a in dash3["activity"])

    print("multiplayer flow ok")


if __name__ == "__main__":
    try:
        main()
    finally:
        shutil.rmtree(_tmp, ignore_errors=True)
