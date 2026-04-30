import json
import random
import time
import uuid
from typing import Any, Dict, List, Optional

from backend.services.game_state import dumps_game, loads_game
from backend.storage.db import db
from engine.game_engine import Game, regulation_dead_ball_clock_seconds, regulation_kneel_clock_seconds
from play_single_game import sync_game_ratings
from systems import calculate_team_ratings, calculate_turnover_profile
from systems.depth_chart import build_depth_chart
from systems.game_stats import (
    create_game_stats,
    record_play,
    format_game_box_score,
    player_game_stats_map_to_json_list,
    player_game_stats_by_id_from_json,
    player_game_stats_by_id_to_json,
)
from systems.playbook_system import build_playbook_for_team
from systems.play_caller import build_situation_from_game, pick_offensive_play, pick_defensive_play
from backend.services.play_by_play import build_dynamic_play_by_play

KICKOFF_PLAY_IDS = {"KICKOFF_DEEP", "KICKOFF_MIDDLE_SQUIB", "KICKOFF_ONSIDE", "KICKOFF_SURPRISE_ONSIDE"}
KICKOFF_RETURN_IDS = {"KICKOFF_RETURN_MIDDLE_WEDGE", "KICKOFF_RETURN_FIELD_RETURN", "KICKOFF_RETURN_REVERSE"}


def _ensure_team_stats(game: Game, home_name: str, away_name: str) -> Dict[str, Dict]:
    """Ensure game has team_stats; initialize if missing."""
    stats = getattr(game, "team_stats", None)
    if not stats:
        stats = {
            home_name: {"rush_yards": 0, "pass_yards": 0, "touchdowns": 0, "turnovers": 0,
                        "sacks": 0, "interceptions": 0, "fumbles": 0, "third_down": [0, 0], "fourth_down": [0, 0]},
            away_name: {"rush_yards": 0, "pass_yards": 0, "touchdowns": 0, "turnovers": 0,
                        "sacks": 0, "interceptions": 0, "fumbles": 0, "third_down": [0, 0], "fourth_down": [0, 0]},
        }
        game.team_stats = stats
    return stats


def _update_team_stats(
    game: Game,
    result: Dict,
    offense_name: str,
    defense_name: str,
    is_run: bool,
    down_before: int,
) -> None:
    """Update team_stats from play result."""
    home_name = getattr(game, "home_team_name", "Home")
    away_name = getattr(game, "away_team_name", "Away")
    stats = _ensure_team_stats(game, home_name, away_name)

    yards = result.get("yards", 0)
    ts = stats[offense_name]
    if is_run:
        ts["rush_yards"] += yards
    else:
        ts["pass_yards"] += yards
    if result.get("touchdown"):
        ts["touchdowns"] += 1
    if result.get("sack"):
        stats[defense_name]["sacks"] += 1
    if down_before == 3:
        ts["third_down"][0] += 1
        if result.get("first_down") or result.get("touchdown"):
            ts["third_down"][1] += 1
    elif down_before == 4:
        ts["fourth_down"][0] += 1
        if result.get("first_down") or result.get("touchdown"):
            ts["fourth_down"][1] += 1

    stats[home_name]["turnovers"] = getattr(game, "interceptions_home", 0) + getattr(game, "fumbles_home", 0)
    stats[away_name]["turnovers"] = getattr(game, "interceptions_away", 0) + getattr(game, "fumbles_away", 0)
    stats[home_name]["interceptions"] = getattr(game, "interceptions_home", 0)
    stats[away_name]["interceptions"] = getattr(game, "interceptions_away", 0)
    stats[home_name]["fumbles"] = getattr(game, "fumbles_home", 0)
    stats[away_name]["fumbles"] = getattr(game, "fumbles_away", 0)


def create_game(
    save_id: str,
    home_team: Any,
    away_team: Any,
    user_team_name: Optional[str] = None,
) -> str:
    game = Game()
    game.possession = "home"
    game.home_team_name = home_team.name
    game.away_team_name = away_team.name
    game.user_team_name = user_team_name or home_team.name

    home_ratings = calculate_team_ratings(home_team)
    away_ratings = calculate_team_ratings(away_team)
    home_turnover = calculate_turnover_profile(home_team)
    away_turnover = calculate_turnover_profile(away_team)
    sync_game_ratings(game, home_ratings, away_ratings, home_turnover, away_turnover)

    _ensure_team_stats(game, home_team.name, away_team.name)
    coach_sm, _, _ = create_game_stats(home_team, away_team)
    game.coach_player_stats_by_id = player_game_stats_by_id_to_json(coach_sm)
    game.play_log_lines = []
    game.pending_pat = False
    game.pending_kickoff = True
    game.opening_kickoff_receiver = random.choice(["home", "away"])
    game.kickoff_kicking_team = "away" if game.opening_kickoff_receiver == "home" else "home"
    game.possession = game.kickoff_kicking_team

    game_id = str(uuid.uuid4())
    now = int(time.time())
    with db() as conn:
        conn.execute(
            "INSERT INTO games (id, save_id, created_at, updated_at, state_json) VALUES (?,?,?,?,?)",
            (game_id, save_id, now, now, dumps_game(game)),
        )
    return game_id


def get_game(game_id: str) -> Game:
    with db() as conn:
        row = conn.execute("SELECT state_json FROM games WHERE id=?", (game_id,)).fetchone()
    if not row:
        raise ValueError("game not found")
    return loads_game(row["state_json"])


def save_game(game_id: str, game: Game) -> None:
    now = int(time.time())
    with db() as conn:
        conn.execute(
            "UPDATE games SET state_json=?, updated_at=? WHERE id=?",
            (dumps_game(game), now, game_id),
        )


def game_state_dict(game: Game) -> Dict[str, Any]:
    home_name = getattr(game, "home_team_name", "Home")
    away_name = getattr(game, "away_team_name", "Away")
    team_stats = getattr(game, "team_stats", None) or {}
    # Format third/fourth down for display
    formatted_stats = {}
    for name, ts in team_stats.items():
        c, a = ts.get("third_down", [0, 0])
        td = f"{c}/{a}" if a else "0/0"
        c4, a4 = ts.get("fourth_down", [0, 0])
        fd = f"{c4}/{a4}" if a4 else "0/0"
        rush = ts.get("rush_yards", 0)
        pass_yds = ts.get("pass_yards", 0)
        formatted_stats[name] = {
            "rush_yards": rush,
            "pass_yards": pass_yds,
            "total_yards": rush + pass_yds,
            "touchdowns": ts.get("touchdowns", 0),
            "turnovers": ts.get("turnovers", 0),
            "sacks": ts.get("sacks", 0),
            "interceptions": ts.get("interceptions", 0),
            "fumbles": ts.get("fumbles", 0),
            "third_down": td,
            "fourth_down": fd,
            "explosives": ts.get("explosives", 0),
            "time_of_possession": ts.get("time_of_possession", "0:00"),
        }
    return {
        "quarter": game.quarter,
        "time_remaining": game.time_remaining,
        "ball_position": game.ball_position,
        "down": game.down,
        "yards_to_go": game.yards_to_go,
        "score_home": game.score_home,
        "score_away": game.score_away,
        "possession": game.possession,
        "home_team_name": home_name,
        "away_team_name": away_name,
        "user_team_name": getattr(game, "user_team_name", home_name),
        "is_overtime": getattr(game, "is_overtime", False),
        "ot_period": getattr(game, "ot_period", 0),
        "ot_2pt_mode": getattr(game, "ot_2pt_mode", False),
        "ot_winner": getattr(game, "ot_winner", None),
        "pending_pat": getattr(game, "pending_pat", False),
        "pending_kickoff": getattr(game, "pending_kickoff", False),
        "team_stats": formatted_stats,
    }


def ensure_coach_player_stats_initialized(game: Game, home_team: Any, away_team: Any) -> None:
    """Lazy-init coach-mode player stat buckets (older saves / games without the field)."""
    raw = getattr(game, "coach_player_stats_by_id", None)
    if raw:
        return
    sm, _, _ = create_game_stats(home_team, away_team)
    game.coach_player_stats_by_id = player_game_stats_by_id_to_json(sm)


def _coach_record_scrimmage_stats(
    game: Game,
    home_team: Any,
    away_team: Any,
    possession_before: str,
    is_run: bool,
    result: Dict[str, Any],
) -> None:
    """Accumulate individual player stats for scrimmage plays (same attribution as simmed games)."""
    if result.get("kneel") or result.get("pat") or result.get("pat_2pt") or result.get("kickoff"):
        return
    if result.get("punt") or result.get("field_goal"):
        return
    ensure_coach_player_stats_initialized(game, home_team, away_team)
    home_dc = build_depth_chart(home_team)
    away_dc = build_depth_chart(away_team)
    sm = player_game_stats_by_id_from_json(getattr(game, "coach_player_stats_by_id", None) or {})
    record_play(sm, home_team, away_team, home_dc, away_dc, possession_before, "1" if is_run else "2", result)
    game.coach_player_stats_by_id = player_game_stats_by_id_to_json(sm)


def build_coach_postgame_box_assets(
    game: Game,
    home_team: Any,
    away_team: Any,
    home_name: str,
    away_name: str,
) -> tuple[List[str], List[Dict[str, Any]]]:
    """Player box score lines + week_results-compatible player_stats list."""
    if home_team is not None and away_team is not None:
        ensure_coach_player_stats_initialized(game, home_team, away_team)
    sm = player_game_stats_by_id_from_json(getattr(game, "coach_player_stats_by_id", None) or {})
    lines = format_game_box_score(sm, home_name, away_name)
    plist = player_game_stats_map_to_json_list(sm)
    return lines, plist


def _kickoff_play_options(game: Game, offense_team: Any, defense_team: Any) -> Dict[str, Any]:
    offense_plays = [
        {"id": "KICKOFF_DEEP", "name": "Kickoff - Deep", "category": "SPECIAL_TEAMS_KICKOFF", "formation": ""},
        {"id": "KICKOFF_MIDDLE_SQUIB", "name": "Kickoff - Middle Squib", "category": "SPECIAL_TEAMS_KICKOFF", "formation": ""},
        {"id": "KICKOFF_ONSIDE", "name": "Kickoff - Onside", "category": "SPECIAL_TEAMS_KICKOFF", "formation": ""},
        {"id": "KICKOFF_SURPRISE_ONSIDE", "name": "Kickoff - Surprise Onside", "category": "SPECIAL_TEAMS_KICKOFF", "formation": ""},
    ]
    defense_plays = [
        {"id": "KICKOFF_RETURN_MIDDLE_WEDGE", "name": "Kickoff Return - Middle Wedge", "category": "SPECIAL_TEAMS_RETURN", "formation": ""},
        {"id": "KICKOFF_RETURN_FIELD_RETURN", "name": "Kickoff Return - Field Return", "category": "SPECIAL_TEAMS_RETURN", "formation": ""},
        {"id": "KICKOFF_RETURN_REVERSE", "name": "Kickoff Return - Reverse", "category": "SPECIAL_TEAMS_RETURN", "formation": ""},
    ]
    ai_off = "KICKOFF_DEEP"
    ai_def = random.choice(list(KICKOFF_RETURN_IDS))
    return {
        "offense_team": offense_team.name,
        "defense_team": defense_team.name,
        "ai": {"offense_play_id": ai_off, "defense_play_id": ai_def},
        "offense_plays": offense_plays,
        "defense_plays": defense_plays,
    }


def _submit_kickoff_play(
    game: Game, home_team: Any, away_team: Any, offense_play_id: str, defense_play_id: str
) -> Dict[str, Any]:
    kicking_side = getattr(game, "kickoff_kicking_team", game.possession)
    if kicking_side not in ("home", "away"):
        kicking_side = game.possession
    receiving_side = "away" if kicking_side == "home" else "home"
    kicking_team = home_team if kicking_side == "home" else away_team
    receiving_team = away_team if kicking_side == "home" else home_team

    if offense_play_id not in KICKOFF_PLAY_IDS:
        offense_play_id = "KICKOFF_DEEP"
    if defense_play_id not in KICKOFF_RETURN_IDS:
        defense_play_id = "KICKOFF_RETURN_FIELD_RETURN"

    if offense_play_id == "KICKOFF_DEEP":
        kick_distance = random.randint(55, 70)
        touchback_chance = 0.16
        onside = False
    elif offense_play_id == "KICKOFF_MIDDLE_SQUIB":
        kick_distance = random.randint(35, 50)
        touchback_chance = 0.03
        onside = False
    elif offense_play_id == "KICKOFF_ONSIDE":
        kick_distance = random.randint(9, 14)
        touchback_chance = 0.0
        onside = True
    else:
        kick_distance = random.randint(10, 20)
        touchback_chance = 0.0
        onside = True

    recovered_by_kicking = False
    if onside:
        recover_chance = 0.16 if offense_play_id == "KICKOFF_ONSIDE" else 0.34
        recovered_by_kicking = random.random() < recover_chance

    result: Dict[str, Any] = {"kickoff": True, "kick_distance": kick_distance, "return_yards": 0, "touchback": False, "kickoff_td": False}
    game.pending_kickoff = False

    if recovered_by_kicking:
        game.possession = kicking_side
        game.ball_position = min(99, max(1, kick_distance))
        game.down = 1
        game.yards_to_go = 10
        result["onside_recovered"] = True
    else:
        game.possession = receiving_side
        if random.random() < touchback_chance:
            result["touchback"] = True
            # ball_position is always from current offense own goal line
            game.ball_position = 25
            game.down = 1
            game.yards_to_go = 10
        else:
            if defense_play_id == "KICKOFF_RETURN_MIDDLE_WEDGE":
                ret = random.randint(15, 25)
            elif defense_play_id == "KICKOFF_RETURN_FIELD_RETURN":
                ret = random.randint(22, 32)
            else:
                ret = random.randint(10, 38)
            result["return_yards"] = ret
            land = max(1, min(99, kick_distance))
            new_pos = land + ret
            if new_pos >= 100:
                result["kickoff_td"] = True
                if receiving_side == "home":
                    game.score_home += 6
                else:
                    game.score_away += 6
                game.pending_pat = True
                game.ball_position = 97
            else:
                game.ball_position = min(new_pos, 99)
                game.down = 1
                game.yards_to_go = 10
        if not result.get("kickoff_td"):
            game.time_remaining = max(0, game.time_remaining - random.randint(8, 18))

    narrative = build_play_narrative(
        receiving_team,
        kicking_team,
        result,
        is_run=False,
        context={"down": 1, "yards_to_go": 10, "ball_position": game.ball_position, "quarter": game.quarter, "time_remaining": game.time_remaining, "score_margin": 0},
    )
    if recovered_by_kicking:
        narrative = "Onside kick recovered by the kicking team!"
    return {"result": result, "state": game_state_dict(game), "narrative": narrative}


def _attempt_field_goal_hs(game: Game, defense_play_id: str = "") -> Dict[str, Any]:
    """HS-style field-goal model calibrated closer to provided ranges."""
    kick_distance = int((100 - game.ball_position) + 17)
    fg_block = defense_play_id == "DEF_FG_BLOCK"
    if kick_distance <= 30:
        success = 0.92
    elif kick_distance <= 35:
        success = 0.82
    elif kick_distance <= 40:
        success = 0.68
    elif kick_distance <= 45:
        success = 0.52
    elif kick_distance <= 50:
        success = 0.32
    else:
        success = 0.12

    block_chance = 0.04 if not fg_block else 0.10
    blocked = random.random() < block_chance
    if blocked:
        good = False
    else:
        if fg_block:
            success *= 0.82
        good = random.random() < success

    if good:
        if game.possession == "home":
            game.score_home += 3
        else:
            game.score_away += 3
        game.pending_kickoff = True
        game.kickoff_kicking_team = game.possession
    else:
        game.switch_possession()
        game.ball_position = 25
        game.down = 1
        game.yards_to_go = 10

    return {"good": good, "blocked": blocked, "distance": kick_distance}


def _pat_play_options(game: Game, offense_team: Any, defense_team: Any) -> Dict[str, Any]:
    """After a regulation TD: XP or 2PT; defense chooses block / 2PT look."""
    ai_pat_off = "PAT_KICK" if random.random() < 0.88 else "PAT_2PT"
    if ai_pat_off == "PAT_KICK":
        ai_pat_def = random.choice(["DEF_PAT_BLOCK", "DEF_PAT_RETURN"])
    else:
        ai_pat_def = random.choice(["DEF_2PT_RUN", "DEF_2PT_PASS", "DEF_2PT_BAL"])

    offense_plays = [
        {"id": "PAT_KICK", "name": "Kick extra point", "category": "AFTER_TOUCHDOWN", "formation": ""},
        {"id": "PAT_2PT", "name": "Go for two", "category": "AFTER_TOUCHDOWN", "formation": ""},
    ]
    defense_plays = [
        {"id": "DEF_PAT_BLOCK", "name": "Block extra point", "category": "AFTER_TOUCHDOWN_DEF", "formation": ""},
        {"id": "DEF_PAT_RETURN", "name": "Safe XP formation", "category": "AFTER_TOUCHDOWN_DEF", "formation": ""},
        {"id": "DEF_2PT_RUN", "name": "2PT — stop the run", "category": "AFTER_TOUCHDOWN_DEF", "formation": ""},
        {"id": "DEF_2PT_PASS", "name": "2PT — pass rush", "category": "AFTER_TOUCHDOWN_DEF", "formation": ""},
        {"id": "DEF_2PT_BAL", "name": "2PT — balanced", "category": "AFTER_TOUCHDOWN_DEF", "formation": ""},
    ]
    return {
        "offense_team": offense_team.name,
        "defense_team": defense_team.name,
        "ai": {"offense_play_id": ai_pat_off, "defense_play_id": ai_pat_def},
        "offense_plays": offense_plays,
        "defense_plays": defense_plays,
    }


def _knee_allowed(game: Game) -> bool:
    if getattr(game, "is_overtime", False) or getattr(game, "pending_pat", False):
        return False
    if game.quarter not in (2, 4):
        return False
    if game.time_remaining > 120:
        return False
    if game.possession == "home":
        margin = game.score_home - game.score_away
    else:
        margin = game.score_away - game.score_home
    return margin > 0


def play_options(game: Game, home_team: Any, away_team: Any) -> Dict[str, Any]:
    kickoff_pending = bool(getattr(game, "pending_kickoff", False))
    if kickoff_pending:
        kicking_side = getattr(game, "kickoff_kicking_team", game.possession)
        offense_team = home_team if kicking_side == "home" else away_team
        defense_team = away_team if kicking_side == "home" else home_team
        return _kickoff_play_options(game, offense_team, defense_team)
    offense_team = home_team if game.possession == "home" else away_team
    defense_team = away_team if game.possession == "home" else home_team

    if getattr(game, "pending_pat", False):
        return _pat_play_options(game, offense_team, defense_team)

    off_pb = build_playbook_for_team(offense_team)
    def_pb = build_playbook_for_team(defense_team)
    sit = build_situation_from_game(game, offense_team=offense_team, defense_team=defense_team)

    ai_off = pick_offensive_play(off_pb, sit, offense_team=offense_team)
    ai_def = pick_defensive_play(def_pb, sit, defense_team=defense_team)

    offense_plays = [
        {"id": p.id, "name": p.name, "category": p.offensive_category.name, "formation": getattr(p, "formation", None) or ""}
        for p in off_pb.offensive_plays
    ]
    defense_plays = [
        {"id": p.id, "name": p.name, "category": p.defensive_category.name, "formation": getattr(p, "formation", None) or ""}
        for p in def_pb.defensive_plays
    ]

    offense_plays = offense_plays + [
        {"id": "PUNT", "name": "Punt - Shield", "category": "SPECIAL_TEAMS_OFFENSE", "formation": ""},
        {"id": "PUNT_PRO", "name": "Punt - Pro", "category": "SPECIAL_TEAMS_OFFENSE", "formation": ""},
        {"id": "FAKE_PUNT", "name": "Punt - Fake Punt", "category": "SPECIAL_TEAMS_OFFENSE", "formation": ""},
        {"id": "FIELD_GOAL", "name": "Field goal", "category": "SPECIAL_TEAMS_OFFENSE", "formation": ""},
    ]
    defense_plays = defense_plays + [
        {"id": "DEF_PUNT_RETURN", "name": "Punt Return - Hold Up", "category": "SPECIAL_TEAMS_DEFENSE", "formation": ""},
        {"id": "DEF_PUNT_BLOCK", "name": "Punt Return - Block", "category": "SPECIAL_TEAMS_DEFENSE", "formation": ""},
        {"id": "DEF_PUNT_ALL_OUT_BLOCK", "name": "Punt Return - All Out Block", "category": "SPECIAL_TEAMS_DEFENSE", "formation": ""},
        {"id": "DEF_FG_BLOCK", "name": "Field goal - block", "category": "SPECIAL_TEAMS_DEFENSE", "formation": ""},
    ]

    if _knee_allowed(game):
        offense_plays = offense_plays + [
            {"id": "KNEE", "name": "Take a knee", "category": "SPECIAL_TEAMS_OFFENSE", "formation": ""},
        ]

    ai_off_id = getattr(ai_off, "id", None)
    ai_def_id = getattr(ai_def, "id", None)
    if game.down == 4 and not getattr(game, "is_overtime", False):
        try:
            coach = getattr(offense_team, "coach", None)
            go_max = getattr(coach, "fourth_down_go_for_it_max_ytg", None) if coach is not None else None
            if go_max is not None:
                game.fourth_down_go_for_it_max_ytg = go_max
        except Exception:
            pass
        dec = game.fourth_down_decision()
        if dec == "punt":
            ai_off_id = "PUNT"
            ai_def_id = "DEF_PUNT_BLOCK" if random.random() < 0.15 else "DEF_PUNT_RETURN"
        elif dec == "fg":
            ai_off_id = "FIELD_GOAL"
            ai_def_id = "DEF_FG_BLOCK" if random.random() < 0.14 else (ai_def_id or "DEF_FG_BLOCK")

    return {
        "offense_team": offense_team.name,
        "defense_team": defense_team.name,
        "ai": {
            "offense_play_id": ai_off_id,
            "defense_play_id": ai_def_id,
        },
        "offense_plays": offense_plays,
        "defense_plays": defense_plays,
    }


def _pick_roster_name(team: Any, positions: List[str]) -> Optional[str]:
    """Pick a random player name from roster matching one of the positions."""
    roster = getattr(team, "roster", None) or []
    if not roster:
        return None
    candidates = [p for p in roster if getattr(p, "position", None) in positions]
    if not candidates:
        candidates = list(roster)
    if not candidates:
        return None
    name = getattr(random.choice(candidates), "name", None)
    return str(name).strip() if name else None


def build_play_narrative(
    offense_team: Any,
    defense_team: Any,
    result: Dict[str, Any],
    is_run: bool,
    context: Optional[Dict[str, Any]] = None,
) -> str:
    """Short broadcast-style line using roster names (best-effort from depth)."""
    qb = _pick_roster_name(offense_team, ["QB"]) or "The QB"
    rb = _pick_roster_name(offense_team, ["RB"]) or "The running back"
    wr = _pick_roster_name(offense_team, ["WR", "TE"]) or "the receiver"
    rusher = _pick_roster_name(defense_team, ["DE", "DT", "LB"]) or "The pass rusher"
    db = _pick_roster_name(defense_team, ["CB", "S"]) or _pick_roster_name(defense_team, ["LB"]) or "The defense"

    tackler = _pick_roster_name(defense_team, ["LB", "CB", "S", "DE", "DT"]) or "a defender"
    return build_dynamic_play_by_play(
        result=result,
        is_run=is_run,
        offense_team=getattr(offense_team, "name", "Offense"),
        defense_team=getattr(defense_team, "name", "Defense"),
        qb=qb,
        rb=rb,
        wr=wr,
        rusher=rusher,
        db=db,
        tackler=tackler,
        offensive_style=getattr(getattr(offense_team, "coach", None), "offensive_style", "") or "",
        offensive_formation=getattr(getattr(offense_team, "coach", None), "offensive_formation", "") or "",
        context=context or {},
    )


def _fmt_clock(sec: int) -> str:
    sec = max(0, int(sec or 0))
    return f"{sec // 60}:{sec % 60:02d}"


def _off_call_label(play_obj: Any, play_id: str) -> str:
    if play_obj is not None:
        form = getattr(play_obj, "formation", None) or ""
        nm = getattr(play_obj, "name", "Play")
        return f"{nm}" + (f" ({form})" if form else "")
    if play_id == "1":
        return "RUN"
    if play_id == "2":
        return "PASS"
    if play_id == "PUNT":
        return "PUNT"
    if play_id == "PUNT_PRO":
        return "PUNT (PRO)"
    if play_id == "FAKE_PUNT":
        return "FAKE PUNT"
    if play_id == "FIELD_GOAL":
        return "FIELD GOAL"
    if play_id == "KICKOFF_DEEP":
        return "KICKOFF (DEEP)"
    if play_id == "KICKOFF_MIDDLE_SQUIB":
        return "KICKOFF (MIDDLE SQUIB)"
    if play_id == "KICKOFF_ONSIDE":
        return "KICKOFF (ONSIDE)"
    if play_id == "KICKOFF_SURPRISE_ONSIDE":
        return "KICKOFF (SURPRISE ONSIDE)"
    if play_id == "PAT_KICK":
        return "EXTRA POINT"
    if play_id == "PAT_2PT":
        return "TWO-POINT TRY"
    if play_id == "KNEE":
        return "TAKE A KNEE"
    return str(play_id)


def _def_call_label(play_obj: Any, play_id: str) -> str:
    if play_obj is not None:
        form = getattr(play_obj, "formation", None) or ""
        nm = getattr(play_obj, "name", "Play")
        return f"{nm}" + (f" ({form})" if form else "")
    if play_id == "1":
        return "RUN DEFENSE"
    if play_id == "2":
        return "PASS RUSH"
    if play_id == "3":
        return "BALANCED DEFENSE"
    if play_id == "DEF_PUNT_RETURN":
        return "PUNT RETURN / SAFE"
    if play_id == "DEF_PUNT_BLOCK":
        return "PUNT BLOCK"
    if play_id == "DEF_PUNT_ALL_OUT_BLOCK":
        return "ALL-OUT PUNT BLOCK"
    if play_id == "DEF_FG_BLOCK":
        return "FG BLOCK"
    if play_id == "KICKOFF_RETURN_MIDDLE_WEDGE":
        return "KO RETURN (MIDDLE WEDGE)"
    if play_id == "KICKOFF_RETURN_FIELD_RETURN":
        return "KO RETURN (FIELD RETURN)"
    if play_id == "KICKOFF_RETURN_REVERSE":
        return "KO RETURN (REVERSE)"
    if play_id == "DEF_PAT_BLOCK":
        return "XP BLOCK RUSH"
    if play_id == "DEF_PAT_RETURN":
        return "XP SAFE"
    if play_id == "DEF_2PT_RUN":
        return "2PT RUN D"
    if play_id == "DEF_2PT_PASS":
        return "2PT PASS RUSH"
    if play_id == "DEF_2PT_BAL":
        return "2PT BALANCED"
    return str(play_id)


def _append_game_log_line(
    game: Game,
    offense_name: str,
    defense_name: str,
    offense_call_label: str,
    defense_call_label: str,
    narrative: str,
    down_before: int,
    ytg_before: int,
    ball_before: int,
    quarter_before: int,
    time_before: int,
) -> None:
    lines = getattr(game, "play_log_lines", None)
    if lines is None or not isinstance(lines, list):
        lines = []
        game.play_log_lines = lines
    spot = f"Own {ball_before}" if ball_before <= 50 else f"Opp {100 - ball_before}"
    lines.append(
        f"Q{quarter_before} {_fmt_clock(time_before)} | {offense_name} {down_before}&{ytg_before} @ {spot} | "
        f"O: {offense_call_label} | D: {defense_call_label} | Result: {narrative}"
    )


def _sync_ratings(game: Game, home_team: Any, away_team: Any) -> None:
    home_ratings = calculate_team_ratings(home_team)
    away_ratings = calculate_team_ratings(away_team)
    home_turnover = calculate_turnover_profile(home_team)
    away_turnover = calculate_turnover_profile(away_team)
    sync_game_ratings(game, home_ratings, away_ratings, home_turnover, away_turnover)


def _execute_knee(game: Game) -> Dict[str, Any]:
    yards = -1 if random.random() < 0.65 else -2
    game.ball_position += yards
    game.ball_position = max(0, min(99, game.ball_position))
    game.yards_to_go -= yards
    clock_elapsed = regulation_kneel_clock_seconds()
    game.time_remaining = max(0, game.time_remaining - clock_elapsed)
    first_down = game.yards_to_go <= 0
    if first_down:
        game.down = 1
        game.yards_to_go = 10
    else:
        game.down += 1
    turnover = False
    if game.down > 4:
        turnover = True
        game.switch_possession()
    return {
        "yards": yards,
        "touchdown": False,
        "turnover": turnover,
        "kneel": True,
        "clock_elapsed": clock_elapsed,
        "first_down": first_down,
        "sack": False,
        "interception": False,
        "incomplete_pass": False,
        "fumble": False,
    }


def _map_2pt_defense(defense_play_id: str) -> str:
    if defense_play_id == "DEF_2PT_RUN":
        return "1"
    if defense_play_id == "DEF_2PT_PASS":
        return "2"
    return "3"


def _submit_pat_play(game: Game, home_team: Any, away_team: Any, offense_play_id: str, defense_play_id: str) -> Dict[str, Any]:
    if not getattr(game, "pending_pat", False):
        raise ValueError("not in PAT phase")
    offense_team = home_team if game.possession == "home" else away_team
    defense_team = away_team if game.possession == "home" else home_team
    offense_name = offense_team.name
    defense_name = defense_team.name

    q_before = game.quarter
    t_before = game.time_remaining
    b_before = game.ball_position
    off_score_before = game.score_home if game.possession == "home" else game.score_away
    def_score_before = game.score_away if game.possession == "home" else game.score_home

    if offense_play_id == "PAT_KICK":
        mode = "block" if defense_play_id == "DEF_PAT_BLOCK" else "return"
        pat_res = game.attempt_extra_point_kick("block" if mode == "block" else "return")
        result = {
            "yards": 0,
            "touchdown": False,
            "pat": True,
            "pat_kick": True,
            "pat_success": pat_res.get("pat_success", False),
            "pat_blocked": pat_res.get("blocked", False),
            "clock_elapsed": 0,
        }
        narrative = (
            "Extra point is good."
            if pat_res.get("pat_success")
            else ("Extra point blocked!" if pat_res.get("blocked") else "Extra point no good.")
        )
    elif offense_play_id == "PAT_2PT":
        d_call = _map_2pt_defense(defense_play_id)
        twopt = game.attempt_two_point(None, d_call)
        result = {
            "yards": twopt.get("yards", 0),
            "touchdown": bool(twopt.get("success")),
            "pat": True,
            "pat_2pt": True,
            "pat_success": bool(twopt.get("success")),
            "clock_elapsed": 0,
        }
        narrative = "Two-point conversion good!" if twopt.get("success") else "Two-point try fails."
    else:
        raise ValueError("invalid PAT play")

    # PAT / 2PT attempts are untimed plays. Clock runoff happens on the following kickoff.
    game.time_remaining = max(0, game.time_remaining - int(result.get("clock_elapsed", 0)))
    game.pending_pat = False
    game.pending_kickoff = True
    game.kickoff_kicking_team = game.possession

    _append_game_log_line(
        game,
        offense_name,
        defense_name,
        _off_call_label(None, offense_play_id),
        _def_call_label(None, defense_play_id),
        narrative,
        1,
        0,
        b_before,
        q_before,
        t_before,
    )
    game.advance_quarter()
    return {"result": result, "state": game_state_dict(game), "narrative": narrative}


def _kickoff_followup_narrative(ko_meta: Dict[str, Any], recv_team: Any, other_team: Any) -> str:
    if not ko_meta or not ko_meta.get("kickoff"):
        return ""
    res = {
        "kickoff": True,
        "return_yards": int(ko_meta.get("return_yards") or 0),
        "touchback": bool(ko_meta.get("touchback")),
        "kickoff_td": bool(ko_meta.get("kickoff_td")),
    }
    return build_play_narrative(recv_team, other_team, res, is_run=False, context={}).strip()


def _resolve_pat_ai(game: Game, home_team: Any, away_team: Any) -> None:
    """Auto-resolve PAT when simming (no user input)."""
    offense_team = home_team if game.possession == "home" else away_team
    defense_team = away_team if game.possession == "home" else home_team
    offense_name = offense_team.name
    defense_name = defense_team.name
    q_before = game.quarter
    t_before = game.time_remaining
    b_before = game.ball_position

    go_kick = random.random() < 0.88
    if go_kick:
        mode = random.choice(["block", "return"])
        pat_res = game.attempt_extra_point_kick("block" if mode == "block" else "return")
        narrative = (
            "Extra point is good."
            if pat_res.get("pat_success")
            else ("Extra point blocked!" if pat_res.get("blocked") else "Extra point no good.")
        )
        off_lbl = "EXTRA POINT"
        def_lbl = "XP BLOCK RUSH" if mode == "block" else "XP SAFE"
    else:
        d_call = random.choice(["1", "2", "3"])
        twopt = game.attempt_two_point(None, d_call)
        narrative = "Two-point conversion good!" if twopt.get("success") else "Two-point try fails."
        off_lbl = "TWO-POINT TRY"
        def_lbl = "2PT DEFENSE"

    # PAT / 2PT attempts are untimed plays in regulation.
    game.time_remaining = max(0, game.time_remaining - 0)
    game.pending_pat = False
    game.pending_kickoff = True
    game.kickoff_kicking_team = game.possession
    _append_game_log_line(
        game,
        offense_name,
        defense_name,
        off_lbl,
        def_lbl,
        narrative,
        1,
        0,
        b_before,
        q_before,
        t_before,
    )


def submit_play(game: Game, home_team: Any, away_team: Any, offense_play_id: str, defense_play_id: str) -> Dict[str, Any]:
    _sync_ratings(game, home_team, away_team)
    if getattr(game, "pending_kickoff", False) or offense_play_id in KICKOFF_PLAY_IDS:
        return _submit_kickoff_play(game, home_team, away_team, offense_play_id, defense_play_id)
    offense_team = home_team if game.possession == "home" else away_team
    defense_team = away_team if game.possession == "home" else home_team
    offense_name = offense_team.name
    defense_name = defense_team.name

    if getattr(game, "pending_pat", False):
        return _submit_pat_play(game, home_team, away_team, offense_play_id, defense_play_id)

    if offense_play_id == "KNEE":
        if not _knee_allowed(game):
            raise ValueError("take a knee not available now")
        q_before = game.quarter
        t_before = game.time_remaining
        d_before = game.down
        ytg_before = game.yards_to_go
        b_before = game.ball_position
        off_score_before = game.score_home if game.possession == "home" else game.score_away
        def_score_before = game.score_away if game.possession == "home" else game.score_home
        result = _execute_knee(game)
        narrative = "Quarterback takes a knee; the clock runs."
        _append_game_log_line(
            game,
            offense_name,
            defense_name,
            _off_call_label(None, "KNEE"),
            _def_call_label(None, defense_play_id),
            narrative,
            d_before,
            ytg_before,
            b_before,
            q_before,
            t_before,
        )
        game.advance_quarter()
        return {"result": result, "state": game_state_dict(game), "narrative": narrative}

    # Special Teams: Punt or Field Goal (only valid on 4th down)
    if offense_play_id in ("PUNT", "PUNT_PRO", "FAKE_PUNT", "FIELD_GOAL") and not getattr(game, "is_overtime", False):
        q_before = game.quarter
        t_before = game.time_remaining
        d_before = game.down
        ytg_before = game.yards_to_go
        b_before = game.ball_position
        clock_elapsed = regulation_dead_ball_clock_seconds()
        game.time_remaining = max(0, game.time_remaining - clock_elapsed)
        st_possession = game.possession
        if offense_play_id in ("PUNT", "PUNT_PRO", "FAKE_PUNT"):
            if offense_play_id == "FAKE_PUNT":
                # Fake punt: medium chance to convert, otherwise turnover on downs.
                success = random.random() < 0.42
                if success:
                    gain = random.randint(4, 18)
                    game.ball_position = min(99, game.ball_position + gain)
                    game.down = 1
                    game.yards_to_go = 10
                    result = {"yards": gain, "touchdown": False, "turnover": False, "sack": False, "interception": False, "incomplete_pass": False, "clock_elapsed": clock_elapsed, "first_down": True}
                    _coach_record_scrimmage_stats(
                        game,
                        home_team,
                        away_team,
                        st_possession,
                        True,
                        {
                            "yards": gain,
                            "touchdown": False,
                            "sack": False,
                            "interception": False,
                            "incomplete_pass": False,
                            "fumble": False,
                        },
                    )
                else:
                    game.switch_possession()
                    result = {"yards": 0, "touchdown": False, "turnover": True, "sack": False, "interception": False, "incomplete_pass": False, "clock_elapsed": clock_elapsed, "first_down": False}
            else:
                if defense_play_id == "DEF_PUNT_ALL_OUT_BLOCK":
                    mode = "block" if random.random() < 0.9 else "return"
                elif defense_play_id == "DEF_PUNT_BLOCK":
                    mode = "block"
                else:
                    mode = "return"
                punt_meta = game.punt_ball(defense_mode=mode) or {}
                gross = int(punt_meta.get("distance") or 0)
                blocked = bool(punt_meta.get("blocked"))
                # Add explicit punt return behavior (engine punt currently changes possession but does not model return yardage).
                if blocked:
                    ret = random.randint(0, 8)
                elif defense_play_id == "DEF_PUNT_RETURN":
                    ret = random.randint(5, 12)
                elif defense_play_id == "DEF_PUNT_BLOCK":
                    ret = random.randint(8, 16)
                else:
                    ret = random.randint(10, 20)
                # Possession has already switched inside punt_ball; apply return from receiving-team perspective.
                game.ball_position = max(1, min(99, game.ball_position + ret))
                if offense_play_id == "PUNT":
                    # Shield punts are safer/shorter than pro punts.
                    game.ball_position = max(1, min(99, game.ball_position + random.randint(4, 8)))
                if offense_play_id == "PUNT_PRO":
                    game.ball_position = max(1, min(99, game.ball_position - random.randint(2, 8)))
                result = {
                    "yards": 0,
                    "touchdown": False,
                    "turnover": False,
                    "sack": False,
                    "interception": False,
                    "incomplete_pass": False,
                    "clock_elapsed": clock_elapsed,
                    "first_down": False,
                    "punt": True,
                    "punt_gross_yards": gross,
                    "punt_return_yards": ret,
                }
        else:
            fg_meta = _attempt_field_goal_hs(game, defense_play_id)
            fg_good = bool(fg_meta.get("good"))
            result = {
                "yards": 0,
                "touchdown": False,
                "turnover": False,
                "sack": False,
                "interception": False,
                "incomplete_pass": False,
                "clock_elapsed": clock_elapsed,
                "first_down": False,
                "field_goal": True,
                "field_goal_good": fg_good,
                "field_goal_blocked": bool(fg_meta.get("blocked")),
                "field_goal_distance": int(fg_meta.get("distance") or 0),
            }
        game.advance_quarter()
        off_score_before = game.score_home if game.possession == "home" else game.score_away
        def_score_before = game.score_away if game.possession == "home" else game.score_home
        narrative = build_play_narrative(
            offense_team,
            defense_team,
            result,
            is_run=False,
            context={
                "down": d_before,
                "yards_to_go": ytg_before,
                "ball_position": b_before,
                "quarter": q_before,
                "time_remaining": t_before,
                "score_margin": off_score_before - def_score_before,
            },
        )
        _append_game_log_line(
            game,
            offense_name,
            defense_name,
            _off_call_label(None, offense_play_id),
            _def_call_label(None, defense_play_id),
            narrative,
            d_before,
            ytg_before,
            b_before,
            q_before,
            t_before,
        )
        return {"result": result, "state": game_state_dict(game), "narrative": narrative}

    off_pb = build_playbook_for_team(offense_team)
    def_pb = build_playbook_for_team(defense_team)
    o = off_pb.get_offensive_play_by_id(offense_play_id)
    d = def_pb.get_defensive_play_by_id(defense_play_id)

    if o is None or d is None:
        raise ValueError("invalid play id")

    down_before = game.down
    q_before = game.quarter
    t_before = game.time_remaining
    ytg_before = game.yards_to_go
    b_before = game.ball_position
    off_score_before = game.score_home if game.possession == "home" else game.score_away
    def_score_before = game.score_away if game.possession == "home" else game.score_home
    possession_before = game.possession
    result = game.run_play(o, d, offense_team=offense_team, defense_team=defense_team)
    is_run = o.offensive_category and getattr(o.offensive_category, "name", "") in ("INSIDE_RUN", "OUTSIDE_RUN")
    _update_team_stats(game, result, offense_name, defense_name, is_run, down_before)
    _coach_record_scrimmage_stats(game, home_team, away_team, possession_before, bool(is_run), result)

    if not result.get("needs_pat"):
        game.advance_quarter()
    narrative = build_play_narrative(
        offense_team,
        defense_team,
        result,
        is_run=is_run,
        context={
            "down": down_before,
            "yards_to_go": ytg_before,
            "ball_position": b_before,
            "quarter": q_before,
            "time_remaining": t_before,
            "score_margin": off_score_before - def_score_before,
        },
    )
    _append_game_log_line(
        game,
        offense_name,
        defense_name,
        _off_call_label(o, offense_play_id),
        _def_call_label(d, defense_play_id),
        narrative,
        down_before,
        ytg_before,
        b_before,
        q_before,
        t_before,
    )
    return {"result": result, "state": game_state_dict(game), "narrative": narrative}


def _try_sim_fourth_down_special(game: Game, home_team: Any, away_team: Any) -> Optional[Dict[str, Any]]:
    """Run punt / FG / coach-threshold logic on 4th when AI would not call a normal play."""
    if game.down != 4 or getattr(game, "is_overtime", False):
        return None
    offense_team = home_team if game.possession == "home" else away_team
    defense_team = away_team if game.possession == "home" else home_team
    try:
        coach = getattr(offense_team, "coach", None)
        go_max = getattr(coach, "fourth_down_go_for_it_max_ytg", None) if coach is not None else None
        if go_max is not None:
            game.fourth_down_go_for_it_max_ytg = go_max
    except Exception:
        pass
    dec = game.fourth_down_decision()
    if dec == "go":
        return None

    offense_name = offense_team.name
    defense_name = defense_team.name
    down_before = game.down
    q_before = game.quarter
    t_before = game.time_remaining
    ytg_before = game.yards_to_go
    b_before = game.ball_position
    off_score_before = game.score_home if game.possession == "home" else game.score_away
    def_score_before = game.score_away if game.possession == "home" else game.score_home
    clock_elapsed = regulation_dead_ball_clock_seconds()
    game.time_remaining = max(0, game.time_remaining - clock_elapsed)

    if dec == "punt":
        mode = "block" if random.random() < 0.15 else "return"
        game.punt_ball(defense_mode=mode)
        result = {
            "yards": 0,
            "touchdown": False,
            "turnover": False,
            "sack": False,
            "interception": False,
            "incomplete_pass": False,
            "clock_elapsed": clock_elapsed,
            "first_down": False,
            "punt": True,
        }
        off_lbl = "PUNT"
        def_lbl = "PUNT BLOCK" if mode == "block" else "PUNT RETURN"
    else:
        fg_block = random.random() < 0.18
        defense_play_id = "DEF_FG_BLOCK" if fg_block else "DEF_FG_SAFE"
        fg_meta = _attempt_field_goal_hs(game, "DEF_FG_BLOCK" if fg_block else "")
        fg_good = bool(fg_meta.get("good"))
        result = {
            "yards": 0,
            "touchdown": False,
            "turnover": False,
            "sack": False,
            "interception": False,
            "incomplete_pass": False,
            "clock_elapsed": clock_elapsed,
            "first_down": False,
            "field_goal": True,
            "field_goal_good": fg_good,
            "field_goal_blocked": bool(fg_meta.get("blocked")),
            "field_goal_distance": int(fg_meta.get("distance") or 0),
        }
        off_lbl = "FIELD GOAL"
        def_lbl = "FG BLOCK RUSH" if fg_block else "FG SAFE"

    narrative = build_play_narrative(
        offense_team,
        defense_team,
        result,
        is_run=False,
        context={
            "down": down_before,
            "yards_to_go": ytg_before,
            "ball_position": b_before,
            "quarter": q_before,
            "time_remaining": t_before,
            "score_margin": off_score_before - def_score_before,
        },
    )
    _append_game_log_line(
        game,
        offense_name,
        defense_name,
        off_lbl,
        def_lbl,
        narrative,
        down_before,
        ytg_before,
        b_before,
        q_before,
        t_before,
    )
    game.advance_quarter()
    return {"result": result, "state": game_state_dict(game), "game_over": game.is_game_over(), "narrative": narrative}


def sim_next_play(game: Game, home_team: Any, away_team: Any) -> Dict[str, Any]:
    """AI calls both sides, runs one play, returns result and new state."""
    home_name = getattr(game, "home_team_name", home_team.name)
    away_name = getattr(game, "away_team_name", away_team.name)
    _sync_ratings(game, home_team, away_team)

    if game.is_game_over():
        return {"result": None, "state": game_state_dict(game), "game_over": True}

    # Resolve pending kickoffs in AI sim mode (opening, post-score, halftime).
    if getattr(game, "pending_kickoff", False):
        ko_off = "KICKOFF_DEEP"
        ko_def = random.choice(list(KICKOFF_RETURN_IDS))
        out = _submit_kickoff_play(game, home_team, away_team, ko_off, ko_def)
        game.advance_quarter()
        return {
            "result": out.get("result"),
            "state": out.get("state"),
            "game_over": game.is_game_over(),
            "narrative": out.get("narrative", "Kickoff."),
        }

    # After a user-played TD, engine leaves pending_pat True until PAT — same as submit_play path.
    if getattr(game, "pending_pat", False):
        _resolve_pat_ai(game, home_team, away_team)
        game.pending_kickoff = True
        game.kickoff_kicking_team = game.possession
        game.advance_quarter()
        return {
            "result": {"pat_resolved": True},
            "state": game_state_dict(game),
            "game_over": game.is_game_over(),
            "narrative": "Extra point / two-point (auto).",
        }

    if getattr(game, "ot_2pt_mode", False):
        offense_team = home_team if game.possession == "home" else away_team
        defense_team = away_team if game.possession == "home" else home_team
        off_pb = build_playbook_for_team(offense_team)
        def_pb = build_playbook_for_team(defense_team)
        sit = build_situation_from_game(game, offense_team=offense_team, defense_team=defense_team)
        o = pick_offensive_play(off_pb, sit, offense_team=offense_team)
        d = pick_defensive_play(def_pb, sit, defense_team=defense_team)
        o = o or off_pb.offensive_plays[0] if off_pb.offensive_plays else None
        d = d or def_pb.defensive_plays[0] if def_pb.defensive_plays else None
        if o and d:
            game.run_play_2pt_shootout(o, d)
        game.advance_quarter()
        return {
            "result": {"yards": 0, "touchdown": False},
            "state": game_state_dict(game),
            "game_over": game.is_game_over(),
            "narrative": "Two-point conversion attempt.",
        }

    fourth_out = _try_sim_fourth_down_special(game, home_team, away_team)
    if fourth_out is not None:
        return fourth_out

    offense_team = home_team if game.possession == "home" else away_team
    defense_team = away_team if game.possession == "home" else home_team
    off_pb = build_playbook_for_team(offense_team)
    def_pb = build_playbook_for_team(defense_team)
    sit = build_situation_from_game(game, offense_team=offense_team, defense_team=defense_team)
    o = pick_offensive_play(off_pb, sit, offense_team=offense_team)
    d = pick_defensive_play(def_pb, sit, defense_team=defense_team)
    if not o:
        o = off_pb.offensive_plays[0] if off_pb.offensive_plays else None
    if not d:
        d = def_pb.defensive_plays[0] if def_pb.defensive_plays else None
    if not o or not d:
        raise ValueError(
            f"Cannot auto-sim: team playbook is missing plays ({home_name} vs {away_name}). "
            "Offense or defense has zero callable plays."
        )

    down_before = game.down
    q_before = game.quarter
    t_before = game.time_remaining
    ytg_before = game.yards_to_go
    b_before = game.ball_position
    off_score_before = game.score_home if game.possession == "home" else game.score_away
    def_score_before = game.score_away if game.possession == "home" else game.score_home
    possession_before = game.possession
    result = game.run_play(o, d, offense_team=offense_team, defense_team=defense_team)
    is_run = o.offensive_category and getattr(o.offensive_category, "name", "") in ("INSIDE_RUN", "OUTSIDE_RUN")
    _update_team_stats(game, result, offense_team.name, defense_team.name, is_run, down_before)
    _coach_record_scrimmage_stats(game, home_team, away_team, possession_before, bool(is_run), result)

    if result.get("needs_pat"):
        _resolve_pat_ai(game, home_team, away_team)
    elif result.get("needs_2pt"):
        game.attempt_two_point(o, d)
        game.setup_ot_possession()
        game.check_ot_period_end()
    elif result.get("ot_possession_ended"):
        game.check_ot_period_end()

    game.advance_quarter()
    narrative = build_play_narrative(
        offense_team,
        defense_team,
        result,
        is_run=is_run,
        context={
            "down": down_before,
            "yards_to_go": ytg_before,
            "ball_position": b_before,
            "quarter": q_before,
            "time_remaining": t_before,
            "score_margin": off_score_before - def_score_before,
        },
    )
    _append_game_log_line(
        game,
        offense_team.name,
        defense_team.name,
        _off_call_label(o, "1" if is_run else "2"),
        _def_call_label(d, "3"),
        narrative,
        down_before,
        ytg_before,
        b_before,
        q_before,
        t_before,
    )
    game.advance_quarter()
    return {"result": result, "state": game_state_dict(game), "game_over": game.is_game_over(), "narrative": narrative}


def sim_to_half(game: Game, home_team: Any, away_team: Any) -> Dict[str, Any]:
    """Simulate until halftime (end of Q2)."""
    narratives: List[str] = []
    max_plays = 4000
    for _ in range(max_plays):
        if game.is_game_over() or game.quarter > 2:
            break
        out = sim_next_play(game, home_team, away_team)
        n = out.get("narrative")
        if isinstance(n, str) and n.strip():
            narratives.append(n.strip())
        if out.get("game_over"):
            break
    else:
        raise ValueError("Sim to half aborted: exceeded play limit.")
    return {"state": game_state_dict(game), "game_over": game.is_game_over(), "narratives": narratives}


def sim_to_end(game: Game, home_team: Any, away_team: Any) -> Dict[str, Any]:
    """Simulate until game over."""
    narratives: List[str] = []
    max_plays = 8000
    for _ in range(max_plays):
        if game.is_game_over():
            break
        out = sim_next_play(game, home_team, away_team)
        n = out.get("narrative")
        if isinstance(n, str) and n.strip():
            narratives.append(n.strip())
    else:
        raise ValueError("Sim to end aborted: exceeded play limit (game state may be stuck).")
    return {"state": game_state_dict(game), "game_over": True, "narratives": narratives}

