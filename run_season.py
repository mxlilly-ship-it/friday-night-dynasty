"""
Run a full season: 10-game regular season (5H/5A, random opponents), 8-team playoff.
Output everything to season_results.txt
"""

import sys
import time
import os
import threading

# run_game / scrimmage swap sys.stdout; concurrent requests must not interleave or stdout ends up closed.
_ENGINE_PRINT_LOCK = threading.Lock()

sys.path.insert(0, ".")

from models import Team
from systems.teams_loader import build_teams_from_json
from systems import calculate_team_ratings, calculate_turnover_profile
from systems.playoff_system import run_playoff
from systems.league_history import append_season, load_league_history
from systems.prestige_system import update_prestige
from systems.coach_career_system import run_coach_career_phase
from systems.depth_chart import build_depth_chart
from systems.game_fatigue import (
    GameStaminaTracker,
    PlayFatigueContext,
    build_current_lineup_from_depth_chart,
    process_after_play,
)
from systems.game_stats import (
    create_game_stats,
    record_play,
    format_game_box_score,
    merge_game_stats_into_season,
    format_season_player_stats,
    player_game_stats_map_to_json_list,
)
from engine.game_engine import Game, _offense_play_label, _defense_play_label
from play_single_game import sync_game_ratings
from systems.playbook_system import build_playbook_for_team
from systems.play_caller import build_situation_from_game, call_plays_for_situation


from systems.schedule_system import build_schedule_10_game


def parse_scores_from_final_line(line: str):
    """
    Parse FINAL line from run_game output: 'FINAL: {home} {hs} - {away} {as}' optional ' (OT)'.
    Uses ' - ' as the divider and last token on each side as the score (supports multi-word team names).
    Returns (home_score, away_score) or None if parsing fails.
    """
    if not isinstance(line, str):
        return None
    s = line.strip()
    if not s.startswith("FINAL:"):
        return None
    body = s[6:].strip()
    if body.endswith("(OT)"):
        body = body[: -len("(OT)")].rstrip()
    sep = " - "
    if sep not in body:
        return None
    left, right = body.split(sep, 1)
    left, right = left.strip(), right.strip()
    try:
        lt = left.rsplit(None, 1)
        rt = right.rsplit(None, 1)
        if len(lt) < 2 or len(rt) < 2:
            return None
        return int(lt[1]), int(rt[1])
    except ValueError:
        return None


def run_game_silent(
    home_team,
    away_team,
    teams_dict,
    season_stats,
    standings,
    output_lines,
    season_player_stats=None,
    team_schedules=None,
    game_log_lines=None,
):
    """
    Run run_game() while suppressing engine print output (keeps output_lines updates).
    Useful for week-by-week sim where you don't want snap-by-snap spam.
    """
    with _ENGINE_PRINT_LOCK:
        devnull = open(os.devnull, "w")
        old_stdout = sys.stdout
        sys.stdout = devnull
        try:
            return run_game(
                home_team,
                away_team,
                teams_dict,
                season_stats,
                standings,
                output_lines,
                season_player_stats,
                team_schedules,
                game_log_lines=game_log_lines,
            )
        finally:
            sys.stdout = old_stdout
            devnull.close()


def run_scrimmage_game(home_team, away_team):
    """
    Run a practice/scrimmage game. Plays out like a real game but:
    - No stats kept
    - No fatigue (no stamina drain, no subs)
    - No standings impact

    Returns dict: {home, away, home_score, away_score, ot: bool}
    """
    with _ENGINE_PRINT_LOCK:
        devnull = open(os.devnull, "w")
        old_stdout = sys.stdout
        sys.stdout = devnull
        try:
            return _run_scrimmage_game_impl(home_team, away_team)
        finally:
            sys.stdout = old_stdout
            devnull.close()


def _run_scrimmage_game_impl(home_team, away_team):
    """Inner scrimmage logic (called with stdout suppressed). Tracks stats for display only."""
    home_name = home_team.name
    away_name = away_team.name

    home_ratings = calculate_team_ratings(home_team)
    away_ratings = calculate_team_ratings(away_team)
    home_turnover = calculate_turnover_profile(home_team)
    away_turnover = calculate_turnover_profile(away_team)

    stats_map, home_dc, away_dc = create_game_stats(home_team, away_team)
    team_stats = {
        home_name: {"rush_yards": 0, "pass_yards": 0, "touchdowns": 0, "turnovers": 0,
                    "sacks": 0, "interceptions": 0, "fumbles": 0, "total_plays": 0,
                    "third_down": "0/0", "fourth_down": "0/0"},
        away_name: {"rush_yards": 0, "pass_yards": 0, "touchdowns": 0, "turnovers": 0,
                    "sacks": 0, "interceptions": 0, "fumbles": 0, "total_plays": 0,
                    "third_down": "0/0", "fourth_down": "0/0"},
    }
    third_down = {home_name: [0, 0], away_name: [0, 0]}
    fourth_down = {home_name: [0, 0], away_name: [0, 0]}

    game = Game(
        offense_rating=home_ratings["offense"],
        defense_rating=away_ratings["defense"],
        run_rating=home_ratings["run"],
        pass_rating=home_ratings["pass"],
    )
    game.home_team_name = home_name
    game.away_team_name = away_name
    sync_game_ratings(game, home_ratings, away_ratings, home_turnover, away_turnover)
    game.apply_opening_kickoff()

    # Build playbooks once; play caller chooses exact plays during sim.
    home_playbook = build_playbook_for_team(home_team)
    away_playbook = build_playbook_for_team(away_team)

    while not game.is_game_over():
        sync_game_ratings(game, home_ratings, away_ratings, home_turnover, away_turnover)

        if game.ot_2pt_mode:
            game.run_play_2pt_shootout()
            game.advance_quarter()
            continue

        # 4th down: allow engine punt/FG logic (and coach override threshold) to run.
        if game.down == 4 and not getattr(game, "is_overtime", False):
            try:
                off_obj = home_team if game.possession == "home" else away_team
                coach = getattr(off_obj, "coach", None)
                go_max = getattr(coach, "fourth_down_go_for_it_max_ytg", None) if coach is not None else None
                if go_max is not None:
                    game.fourth_down_go_for_it_max_ytg = go_max
            except Exception:
                pass
            # Run a special-teams decision play (punt/fg) when appropriate.
            result = game.run_play()
            # If it punted/FG'd, the engine returned early with no play concept; skip player stat attribution.
            if isinstance(result, dict) and (result.get("first_down") is False) and (result.get("yards") == 0) and game.down != 4:
                continue

        # Choose exact plays from each team's playbook (silent sim).
        off_obj = home_team if game.possession == "home" else away_team
        def_obj = away_team if game.possession == "home" else home_team
        off_pb = home_playbook if game.possession == "home" else away_playbook
        def_pb = away_playbook if game.possession == "home" else home_playbook
        situation = build_situation_from_game(game, offense_team=off_obj, defense_team=def_obj)
        offense_play, defense_play = call_plays_for_situation(off_pb, def_pb, situation)
        offense_call = offense_play if offense_play is not None else game.get_ai_play_call()
        defense_call = defense_play if defense_play is not None else game.get_ai_defense_call()
        down_before = game.down
        # off_obj/def_obj already set above
        offense_name = home_name if game.possession == "home" else away_name
        defense_name = away_name if game.possession == "home" else home_name

        result = game.run_play(offense_call, defense_call, offense_team=off_obj, defense_team=def_obj)
        record_play(stats_map, home_team, away_team, home_dc, away_dc, game.possession, offense_call, result)

        yards = result.get("yards", 0)
        converted = result.get("touchdown") or result.get("first_down")
        ts = team_stats[offense_name]
        ts["total_plays"] += 1
        if offense_call == "1":
            ts["rush_yards"] += yards
            if yards > 10:
                pass
        else:
            ts["pass_yards"] += yards
            if result.get("sack"):
                team_stats[defense_name]["sacks"] += 1
        if result.get("touchdown"):
            ts["touchdowns"] += 1
        if down_before == 3:
            third_down[offense_name][0] += 1
            if converted:
                third_down[offense_name][1] += 1
        elif down_before == 4:
            fourth_down[offense_name][0] += 1
            if converted:
                fourth_down[offense_name][1] += 1

        if result.get("needs_pat"):
            game.attempt_extra_point_kick(defense_pat_choice="return")
            game.finish_pat_and_kickoff()
            continue

        if result.get("needs_2pt"):
            game.attempt_two_point(offense_call, defense_call)
            game.setup_ot_possession()
            game.check_ot_period_end()
            continue

        if result.get("ot_possession_ended"):
            game.check_ot_period_end()

        game.advance_quarter()

    team_stats[home_name]["interceptions"] = game.interceptions_home
    team_stats[away_name]["interceptions"] = game.interceptions_away
    team_stats[home_name]["fumbles"] = game.fumbles_home
    team_stats[away_name]["fumbles"] = game.fumbles_away
    team_stats[home_name]["turnovers"] = game.interceptions_home + game.fumbles_home
    team_stats[away_name]["turnovers"] = game.interceptions_away + game.fumbles_away
    for name in (home_name, away_name):
        a, c = third_down[name]
        team_stats[name]["third_down"] = f"{c}/{a}" if a else "0/0"
        a, c = fourth_down[name]
        team_stats[name]["fourth_down"] = f"{c}/{a}" if a else "0/0"

    return {
        "home": home_name,
        "away": away_name,
        "home_score": game.score_home,
        "away_score": game.score_away,
        "ot": bool(game.ot_winner),
        "team_stats": team_stats,
        "player_stats": player_game_stats_map_to_json_list(stats_map),
    }


# -------------------------
# Season stats structure
# -------------------------
def init_season_stats(team_names):
    return {
        name: {
            "rush_yards": 0, "pass_yards": 0, "touchdowns": 0, "turnovers": 0,
            "sacks": 0, "interceptions": 0, "fumbles": 0,
            "total_plays": 0, "run_plays": 0, "pass_plays": 0,
            "pass_attempts": 0, "pass_completions": 0,
            "explosive_run": 0, "explosive_pass": 0,
            "time_of_possession": 0,
            "third_down_attempts": 0, "third_down_conversions": 0,
            "fourth_down_attempts": 0, "fourth_down_conversions": 0,
        }
        for name in team_names
    }


# -------------------------
# Run one game (returns game result, updates season_stats, standings)
# -------------------------
def _pick_roster_name(team, positions):
    roster = getattr(team, "roster", None) or []
    if not roster:
        return None
    candidates = [p for p in roster if getattr(p, "position", None) in positions]
    if not candidates:
        candidates = list(roster)
    if not candidates:
        return None
    name = getattr(candidates[0], "name", None)
    return str(name).strip() if name else None


def _build_play_narrative(offense_team, defense_team, result, is_run):
    qb = _pick_roster_name(offense_team, ["QB"]) or "The QB"
    rb = _pick_roster_name(offense_team, ["RB"]) or "The running back"
    wr = _pick_roster_name(offense_team, ["WR", "TE"]) or "the receiver"
    rusher = _pick_roster_name(defense_team, ["DE", "DT", "LB"]) or "The pass rusher"
    db = _pick_roster_name(defense_team, ["CB", "S"]) or _pick_roster_name(defense_team, ["LB"]) or "The defense"
    yards = int(result.get("yards") or 0)
    ay = abs(yards)

    if result.get("touchdown"):
        if is_run:
            return f"{rb} scores on a {ay}-yard run."
        if result.get("scramble"):
            return f"{qb} scrambles in for the touchdown."
        return f"{qb} connects with {wr} for a {ay}-yard touchdown."
    if result.get("sack"):
        if result.get("fumble"):
            return f"{rusher} strip-sacks {qb} — turnover!"
        return f"{rusher} sacks {qb} for a loss of {ay}."
    if result.get("interception"):
        return f"{db} intercepts {qb}."
    if result.get("scramble"):
        return f"{qb} scrambles for {yards} yards."
    if is_run:
        if result.get("turnover"):
            if result.get("fumble"):
                return f"{rb} fumbles — turnover."
            return "Turnover on downs."
        if yards <= 0:
            return f"{rb} is stopped for {yards}."
        return f"{rb} runs for {yards} yards."
    if result.get("incomplete_pass"):
        return f"{qb}'s pass to {wr} is incomplete."
    if result.get("turnover"):
        return "Turnover."
    return f"{qb} completes to {wr} for {yards} yards."


def _fmt_clock(sec):
    sec = max(0, int(sec or 0))
    return f"{sec // 60}:{sec % 60:02d}"


def _fmt_ball(ball_pos):
    bp = int(ball_pos or 0)
    if bp <= 50:
        return f"Own {bp}"
    return f"Opp {100 - bp}"


def run_game(
    home_team,
    away_team,
    teams_dict,
    season_stats,
    standings,
    output_lines,
    season_player_stats=None,
    team_schedules=None,
    game_log_lines=None,
):
    """Sim one game; updates season_stats, standings, output_lines. Returns per-game ``stats_map``."""
    home_name = home_team.name
    away_name = away_team.name

    home_ratings = calculate_team_ratings(home_team)
    away_ratings = calculate_team_ratings(away_team)
    home_turnover = calculate_turnover_profile(home_team)
    away_turnover = calculate_turnover_profile(away_team)

    output_lines.append(f"\n{'='*50}")
    output_lines.append(f"  {home_name} vs {away_name}")
    output_lines.append(f"{'='*50}")
    output_lines.append(f"Team Ratings: {home_name} Off {home_ratings['offense']}/Def {home_ratings['defense']} | {away_name} Off {away_ratings['offense']}/Def {away_ratings['defense']}")
    output_lines.append("")

    # Player game stats: build depth charts and init box score
    stats_map, home_dc, away_dc = create_game_stats(home_team, away_team)

    # Stamina/fatigue: start at 100, drain by position/play type, recover on bench, auto-sub by thresholds
    home_stamina = GameStaminaTracker()
    away_stamina = GameStaminaTracker()
    if home_team.roster:
        home_stamina.init_players(home_team.roster)
    if away_team.roster:
        away_stamina.init_players(away_team.roster)
    home_lineup_off, home_lineup_def = build_current_lineup_from_depth_chart(home_dc)
    away_lineup_off, away_lineup_def = build_current_lineup_from_depth_chart(away_dc)
    drive_plays = 0

    game = Game(
        offense_rating=home_ratings["offense"],
        defense_rating=away_ratings["defense"],
        run_rating=home_ratings["run"],
        pass_rating=home_ratings["pass"],
    )
    game.home_team_name = home_name
    game.away_team_name = away_name
    sync_game_ratings(game, home_ratings, away_ratings, home_turnover, away_turnover)
    game.apply_opening_kickoff()

    # Build playbooks once; play caller chooses exact plays during sim.
    home_playbook = build_playbook_for_team(home_team)
    away_playbook = build_playbook_for_team(away_team)

    while not game.is_game_over():
        sync_game_ratings(game, home_ratings, away_ratings, home_turnover, away_turnover)

        if game.ot_2pt_mode:
            result = game.run_play_2pt_shootout()
            game.advance_quarter()
            time.sleep(0.01)
            continue

        # 4th down: punt / FG / go-for-it (engine) before normal play call.
        if game.down == 4 and not getattr(game, "is_overtime", False):
            try:
                off_obj = home_team if game.possession == "home" else away_team
                coach = getattr(off_obj, "coach", None)
                go_max = getattr(coach, "fourth_down_go_for_it_max_ytg", None) if coach is not None else None
                if go_max is not None:
                    game.fourth_down_go_for_it_max_ytg = go_max
            except Exception:
                pass
            result = game.run_play()
            if isinstance(result, dict) and (result.get("first_down") is False) and (result.get("yards") == 0) and game.down != 4:
                time.sleep(0.01)
                continue

        # Choose exact plays from each team's playbook (silent sim).
        off_obj = home_team if game.possession == "home" else away_team
        def_obj = away_team if game.possession == "home" else home_team
        off_pb = home_playbook if game.possession == "home" else away_playbook
        def_pb = away_playbook if game.possession == "home" else home_playbook
        situation = build_situation_from_game(game, offense_team=off_obj, defense_team=def_obj)
        offense_play, defense_play = call_plays_for_situation(off_pb, def_pb, situation)

        # game_engine.run_play supports either Play objects or legacy string calls.
        offense_call = offense_play if offense_play is not None else game.get_ai_play_call()
        defense_call = defense_play if defense_play is not None else game.get_ai_defense_call()

        down_before = game.down
        offense_team = home_name if game.possession == "home" else away_name
        defense_team = away_name if game.possession == "home" else home_name
        possession_side = game.possession
        # off_obj/def_obj already set above

        q_before = game.quarter
        t_before = game.time_remaining
        down_to_go = f"{game.down}&{game.yards_to_go}"
        ball_before = _fmt_ball(game.ball_position)
        off_label = _offense_play_label(offense_call)
        def_label = _defense_play_label(defense_call)

        # Exact play names for logs (only needed for legacy string calls)
        off_exact = ""
        def_exact = ""
        if isinstance(offense_call, str):
            # Legacy: map RUN/PASS label to a specific play name when available
            if offense_play is not None:
                try:
                    form = getattr(offense_play, "formation", "") or ""
                    off_exact = f"{getattr(offense_play, 'name', '')}{f' ({form})' if form else ''}"
                except Exception:
                    off_exact = ""
        if isinstance(defense_call, str):
            if defense_play is not None:
                try:
                    def_exact = str(getattr(defense_play, "name", "") or "")
                except Exception:
                    def_exact = ""

        result = game.run_play(offense_call, defense_call, offense_team=off_obj, defense_team=def_obj)

        # record_play expects "1" (run) or "2" (pass). Derive from the chosen play when possible.
        offense_call_code = offense_call
        if not isinstance(offense_call, str) and hasattr(offense_call, "offensive_category"):
            try:
                oc = getattr(offense_call, "offensive_category", None)
                if oc is not None and getattr(oc, "name", "") in ("INSIDE_RUN", "OUTSIDE_RUN"):
                    offense_call_code = "1"
                else:
                    offense_call_code = "2"
            except Exception:
                offense_call_code = "2"
        record_play(stats_map, home_team, away_team, home_dc, away_dc, possession_side, offense_call_code, result)

        # Fatigue: drain on-field, recover bench, apply subs. Build context from play.
        yards = result.get("yards", 0)
        is_run = (offense_call_code == "1") if isinstance(offense_call_code, str) else False
        if game_log_lines is not None:
            narrative = _build_play_narrative(off_obj, def_obj, result, is_run=is_run)
            o_disp = off_label if not off_exact else f"{off_label} ({off_exact})"
            d_disp = def_label if not def_exact else f"{def_label} ({def_exact})"
            game_log_lines.append(
                f"Q{q_before} {_fmt_clock(t_before)} | {offense_team} {down_to_go} @ {ball_before} | "
                f"O: {o_disp} | D: {d_disp} | Result: {narrative}"
            )
        converted = result.get("touchdown") or result.get("first_down")
        ctx = PlayFatigueContext(
            is_run=is_run or result.get("scramble", False),
            is_pass=not is_run and not result.get("scramble", False),
            is_deep_pass=not is_run and yards > 20 and not result.get("interception"),
            is_long_run=is_run and yards >= 10,
            is_qb_scramble=result.get("scramble", False),
            drive_plays=drive_plays,
        )
        if game.possession == "home":
            process_after_play(
                home_stamina, away_stamina,
                home_lineup_off, home_lineup_def, away_lineup_off, away_lineup_def,
                home_dc, away_dc, home_team, away_team, ctx, ball_carrier=None,
            )
        else:
            process_after_play(
                away_stamina, home_stamina,
                away_lineup_off, away_lineup_def, home_lineup_off, home_lineup_def,
                away_dc, home_dc, away_team, home_team, ctx, ball_carrier=None,
            )
        drive_plays += 1
        if result.get("touchdown") or result.get("turnover") or (down_before == 4 and not converted):
            drive_plays = 0

        if result.get("needs_pat"):
            game.attempt_extra_point_kick(defense_pat_choice="return")
            game.finish_pat_and_kickoff()
            time.sleep(0.01)
            continue

        if result.get("needs_2pt"):
            yards = result.get("yards", 0)
            season_stats[offense_team]["total_plays"] += 1
            if offense_call_code == "1":
                season_stats[offense_team]["run_plays"] += 1
                season_stats[offense_team]["rush_yards"] += yards
            else:
                season_stats[offense_team]["pass_plays"] += 1
                season_stats[offense_team]["pass_yards"] += yards
            season_stats[offense_team]["touchdowns"] += 1
            game.attempt_two_point(offense_call, defense_call)
            game.setup_ot_possession()
            game.check_ot_period_end()
            time.sleep(0.01)
            continue

        yards = result.get("yards", 0)

        season_stats[offense_team]["total_plays"] += 1
        if offense_call_code == "1":
            season_stats[offense_team]["run_plays"] += 1
            season_stats[offense_team]["rush_yards"] += yards
            if yards > 10:
                season_stats[offense_team]["explosive_run"] += 1
        else:
            season_stats[offense_team]["pass_plays"] += 1
            season_stats[offense_team]["pass_yards"] += yards
            if yards > 20 and not result.get("interception"):
                season_stats[offense_team]["explosive_pass"] += 1
            if not result.get("sack"):
                season_stats[offense_team]["pass_attempts"] += 1
                if not result.get("interception") and not result.get("incomplete_pass"):
                    season_stats[offense_team]["pass_completions"] += 1

        if result.get("touchdown"):
            season_stats[offense_team]["touchdowns"] += 1

        if down_before == 3:
            season_stats[offense_team]["third_down_attempts"] += 1
            if converted:
                season_stats[offense_team]["third_down_conversions"] += 1
        elif down_before == 4:
            season_stats[offense_team]["fourth_down_attempts"] += 1
            if converted:
                season_stats[offense_team]["fourth_down_conversions"] += 1

        season_stats[offense_team]["time_of_possession"] += result.get("clock_elapsed", 0)

        if result.get("sack"):
            season_stats[defense_team]["sacks"] += 1

        if result.get("ot_possession_ended"):
            game.check_ot_period_end()

        # Quarter/halftime stamina recovery
        old_quarter = getattr(game, "quarter", 1)
        game.advance_quarter()
        if getattr(game, "quarter", 1) != old_quarter:
            if home_team.roster:
                home_stamina.recover_quarter_break(home_team.roster)
            if away_team.roster:
                away_stamina.recover_quarter_break(away_team.roster)
            if old_quarter == 2:
                if home_team.roster:
                    home_stamina.recover_halftime(home_team.roster)
                if away_team.roster:
                    away_stamina.recover_halftime(away_team.roster)
        time.sleep(0.01)

    season_stats[home_name]["interceptions"] += game.interceptions_home
    season_stats[away_name]["interceptions"] += game.interceptions_away
    season_stats[home_name]["fumbles"] += game.fumbles_home
    season_stats[away_name]["fumbles"] += game.fumbles_away
    season_stats[home_name]["turnovers"] += game.interceptions_home + game.fumbles_home
    season_stats[away_name]["turnovers"] += game.interceptions_away + game.fumbles_away

    standings[home_name]["points_for"] += game.score_home
    standings[home_name]["points_against"] += game.score_away
    standings[away_name]["points_for"] += game.score_away
    standings[away_name]["points_against"] += game.score_home

    ot_note = " (OT)" if game.ot_winner else ""
    output_lines.append(f"FINAL: {home_name} {game.score_home} - {away_name} {game.score_away}{ot_note}")

    output_lines.extend(format_game_box_score(stats_map, home_name, away_name))

    if season_player_stats is not None:
        merge_game_stats_into_season(season_player_stats, stats_map)

    if game.ot_winner:
        winner = home_name if game.ot_winner == "home" else away_name
        loser = away_name if game.ot_winner == "home" else home_name
        standings[winner]["wins"] += 1
        standings[loser]["losses"] += 1
    elif game.score_home > game.score_away:
        standings[home_name]["wins"] += 1
        standings[away_name]["losses"] += 1
    else:
        standings[home_name]["losses"] += 1
        standings[away_name]["wins"] += 1

    if team_schedules is not None:
        home_won = (game.ot_winner == "home") or (game.score_home > game.score_away)
        team_schedules[home_name].append((away_name, "W" if home_won else "L", game.score_home, game.score_away, "vs"))
        team_schedules[away_name].append((home_name, "W" if not home_won else "L", game.score_away, game.score_home, "@"))

    return stats_map


# -------------------------
# Format team schedule (opponent, W/L, score)
# -------------------------
def format_team_schedules(team_schedules, standings):
    lines = []
    lines.append("")
    lines.append("=" * 50)
    lines.append("TEAM SCHEDULES (Regular Season)")
    lines.append("=" * 50)
    order = sorted(team_schedules.keys(), key=lambda n: (-standings[n]["wins"], -(standings[n]["points_for"] - standings[n]["points_against"])))
    for name in order:
        games = team_schedules[name]
        r = standings[name]
        lines.append(f"\n{name} ({r['wins']}-{r['losses']})")
        for opp, result, score_for, score_against, home_away in games:
            lines.append(f"  {result} {home_away} {opp} {score_for}-{score_against}")
    return lines


# -------------------------
# Format stats output
# -------------------------
def format_stats_output(team_name, stats):
    lines = []
    total_plays = stats["total_plays"]
    total_yards = stats["rush_yards"] + stats["pass_yards"]
    run_plays = stats["run_plays"]
    pass_plays = stats["pass_plays"]

    ypp = total_yards / total_plays if total_plays else 0
    ypc_run = stats["rush_yards"] / run_plays if run_plays else 0
    ypc_pass = stats["pass_yards"] / pass_plays if pass_plays else 0
    run_pct = (run_plays / total_plays * 100) if total_plays else 0
    pass_pct = (pass_plays / total_plays * 100) if total_plays else 0
    cmp_pct = (stats["pass_completions"] / stats["pass_attempts"] * 100) if stats["pass_attempts"] else 0
    top_str = f"{stats['time_of_possession'] // 60}:{stats['time_of_possession'] % 60:02}"

    lines.append(f"\n{team_name}")
    lines.append(f"  Offense: {total_plays} plays | {total_yards} total yards | {ypp:.1f} yards/play")
    lines.append(f"  Run: {run_plays} ({run_pct:.1f}%) | {stats['rush_yards']} yds | {ypc_run:.1f} ypc")
    lines.append(f"  Pass: {pass_plays} ({pass_pct:.1f}%) | {stats['pass_completions']}/{stats['pass_attempts']} ({cmp_pct:.1f}%) | {stats['pass_yards']} yds | {ypc_pass:.1f} ypc")
    lines.append(f"  Touchdowns: {stats['touchdowns']} | Turnovers: {stats['turnovers']}")
    lines.append(f"  {stats['third_down_conversions']}/{stats['third_down_attempts']} 3rd Down | {stats['fourth_down_conversions']}/{stats['fourth_down_attempts']} 4th Down")
    lines.append(f"  Explosives: {stats['explosive_run']} run (10+) | {stats['explosive_pass']} pass (20+)")
    lines.append(f"  Sacks: {stats['sacks']} | INT: {stats['interceptions']} | FUM: {stats['fumbles']}")
    lines.append(f"  Time of Possession: {top_str}")
    return lines


# -------------------------
# Run one season (for save/play loop: pass teams, save_dir, current_year)
# -------------------------
def run_one_season(teams, save_dir, current_year, write_output_to_save_dir=True):
    """
    Run a full season with the given teams. History and records are written under save_dir.
    Returns (champion, standings, season_player_stats, output_lines).
    """
    output_lines = []
    output_lines.append("FRIDAY NIGHT DYNASTY - SEASON RESULTS")
    output_lines.append("=" * 50)
    output_lines.append(f"Season {current_year} | 10-Game Regular Season | 8-Team Playoff")
    output_lines.append("")

    team_names = list(teams.keys())
    standings = {name: {"wins": 0, "losses": 0, "points_for": 0, "points_against": 0} for name in team_names}
    season_stats = init_season_stats(team_names)
    season_player_stats = {}  # player_id -> PlayerSeasonStats (regular season + playoffs)
    team_schedules = {name: [] for name in team_names}

    output_lines.append("TEAMS & ROSTER SIZES:")
    for name in team_names:
        output_lines.append(f"  {name}: {teams[name].roster_size()} players")
    output_lines.append("")

    schedule = build_schedule_10_game(team_names)

    output_lines.append("SCHEDULE & RESULTS:")
    output_lines.append("-" * 50)

    for home_name, away_name in schedule:
        run_game(teams[home_name], teams[away_name], teams, season_stats, standings, output_lines, season_player_stats, team_schedules)

    output_lines.append("")
    output_lines.append("=" * 50)
    output_lines.append("FINAL STANDINGS")
    output_lines.append("=" * 50)

    for name in sorted(team_names, key=lambda n: (-standings[n]["wins"], -(standings[n]["points_for"] - standings[n]["points_against"]))):
        r = standings[name]
        pd = r["points_for"] - r["points_against"]
        output_lines.append(f"  {name}: {r['wins']}-{r['losses']} (PF {r['points_for']} PA {r['points_against']} PD {pd:+d})")

    output_lines.extend(format_team_schedules(team_schedules, standings))

    # Playoffs: 1v4, 2v3, then championship (seed by wins, then point differential)
    champion, bracket_results = run_playoff(teams, standings, team_names, output_lines, season_player_stats)
    runner_up = ""
    if bracket_results:
        champ_game = bracket_results[-1]
        runner_up = champ_game["away"] if champ_game["winner"] == champ_game["home"] else champ_game["home"]

    # Append to league history (pass save_dir when running as part of a saved league)
    append_season(
        champion=champion,
        runner_up=runner_up,
        team_names=team_names,
        standings=standings,
        season_player_stats=season_player_stats,
        year=current_year if save_dir else None,
        save_dir=save_dir,
    )

    # Coach career phase (retirement, hire/fire, promotion, scheme changes)
    if save_dir:
        from systems.save_system import league_history_path
        _hist_path = league_history_path(save_dir)
        league_history = load_league_history(_hist_path)
    else:
        league_history = load_league_history()
    coach_events, coach_changes = run_coach_career_phase(
        teams,
        league_history=league_history,
        standings=standings,
        current_year=current_year + 1,
    )
    for ev in coach_events:
        output_lines.append(f"  [Coach] {ev['detail']}")

    # Update dynamic prestige (includes coach turnover penalty)
    update_prestige(teams, league_history, coach_changes=coach_changes)

    output_lines.append("")
    output_lines.append("=" * 50)
    output_lines.append("SEASON STATS")
    output_lines.append("=" * 50)

    for name in team_names:
        output_lines.extend(format_stats_output(name, season_stats[name]))

    output_lines.append("")
    output_lines.append("=" * 50)
    output_lines.append(f"CHAMPION: {champion}")
    output_lines.append("=" * 50)
    output_lines.append("END OF SEASON")
    output_lines.append("=" * 50)

    # Write to file (save dir when in play mode, else project root)
    import os
    results_path = os.path.join(save_dir, "season_results.txt") if save_dir else "season_results.txt"
    player_stats_path = os.path.join(save_dir, "season_player_stats.txt") if save_dir else "season_player_stats.txt"
    output = "\n".join(output_lines)
    with open(results_path, "w", encoding="utf-8") as f:
        f.write(output)
    player_stats_lines = format_season_player_stats(season_player_stats, team_names_order=team_names, top_n=5)
    with open(player_stats_path, "w", encoding="utf-8") as f:
        f.write("FRIDAY NIGHT DYNASTY - SEASON PLAYER STATS\n")
        f.write("=" * 60 + "\n\n")
        f.write("\n".join(player_stats_lines))

    if not save_dir:
        print("Season complete! Results written to season_results.txt and season_player_stats.txt")
        print(f"\nChampion: {champion}")
        print("\nFinal Standings (incl. playoffs):")
        for name in sorted(team_names, key=lambda n: (-standings[n]["wins"], -(standings[n]["points_for"] - standings[n]["points_against"]))):
            r = standings[name]
            print(f"  {name}: {r['wins']}-{r['losses']}")

    return champion, standings, season_player_stats, output_lines


# -------------------------
# Main (standalone: one season, project root output)
# -------------------------
def main():
    teams = build_teams_from_json(generate_roster=True, two_way_chance=0.55, assign_coaches=True)
    run_one_season(teams, save_dir=None, current_year=1, write_output_to_save_dir=False)


if __name__ == "__main__":
    main()
