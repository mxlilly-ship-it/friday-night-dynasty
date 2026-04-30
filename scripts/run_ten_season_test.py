"""
Run 10 seasons of games with playbooks (coach tendencies).
Output: per-game stats + run/pass calls, player stats by team, season leaderboards, coaches with tendencies.
No game logs (play-by-play).
"""

import sys
import time

sys.path.insert(0, ".")

from models import Team
from systems import calculate_team_ratings, calculate_turnover_profile
from systems.teams_loader import build_teams_from_json
from systems import Playbook, build_playbook_for_team, build_situation_from_game, pick_offensive_play, pick_defensive_play
from systems.playoff_system import run_playoff
from systems.league_history import append_season, load_league_history
from systems.prestige_system import update_prestige
from systems.coach_career_system import run_coach_career_phase
from systems.awards_system import compute_awards, format_awards_text
from systems.records_system import load_records, save_records, update_records_from_game, format_records_text
from systems.depth_chart import build_depth_chart
from systems.game_stats import (
    create_game_stats,
    record_play,
    merge_game_stats_into_season,
    format_season_player_stats,
    PlayerSeasonStats,
)
from systems.offseason_manager import run_offseason_all_teams
from engine.game_engine import Game, _normalize_offense_choice
from play_single_game import sync_game_ratings


from systems.schedule_system import build_schedule_10_game


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


def run_game_with_playbooks(
    home_team,
    away_team,
    season_stats,
    standings,
    season_player_stats,
    home_playbook,
    away_playbook,
    season_num=1,
):
    """
    Run one game using playbooks (coach tendencies). Returns per-game stats dict.
    """
    home_name = home_team.name
    away_name = away_team.name

    home_ratings = calculate_team_ratings(home_team)
    away_ratings = calculate_team_ratings(away_team)
    home_turnover = calculate_turnover_profile(home_team)
    away_turnover = calculate_turnover_profile(away_team)

    stats_map, home_dc, away_dc = create_game_stats(home_team, away_team)

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

    # Per-game run/pass call counters (by team name)
    game_run_calls = {home_name: 0, away_name: 0}
    game_pass_calls = {home_name: 0, away_name: 0}
    game_team_stats = {
        home_name: {"rush_yards": 0, "pass_yards": 0, "touchdowns": 0, "turnovers": 0, "total_plays": 0, "run_plays": 0, "pass_plays": 0},
        away_name: {"rush_yards": 0, "pass_yards": 0, "touchdowns": 0, "turnovers": 0, "total_plays": 0, "run_plays": 0, "pass_plays": 0},
    }

    while not game.is_game_over():
        sync_game_ratings(game, home_ratings, away_ratings, home_turnover, away_turnover)

        if game.ot_2pt_mode:
            off_team = home_team if game.possession == "home" else away_team
            def_team = away_team if game.possession == "home" else home_team
            sit = build_situation_from_game(game, offense_team=off_team, defense_team=def_team)
            off_pb = home_playbook if game.possession == "home" else away_playbook
            def_pb = away_playbook if game.possession == "home" else home_playbook
            o = pick_offensive_play(off_pb, sit, offense_team=off_team)
            d = pick_defensive_play(def_pb, sit, defense_team=def_team)
            result = game.run_play_2pt_shootout(o, d)
            game.advance_quarter()
            time.sleep(0.005)
            continue

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
                time.sleep(0.005)
                continue

        offense_team = home_team if game.possession == "home" else away_team
        defense_team = away_team if game.possession == "home" else home_team
        offense_name = offense_team.name
        defense_name = defense_team.name

        situation = build_situation_from_game(game, offense_team=offense_team, defense_team=defense_team)
        offense_pb = home_playbook if game.possession == "home" else away_playbook
        defense_pb = away_playbook if game.possession == "home" else home_playbook
        offense_call = pick_offensive_play(offense_pb, situation, offense_team=offense_team)
        defense_call = pick_defensive_play(defense_pb, situation, defense_team=defense_team)
        if offense_call is None:
            offense_call = game.get_ai_play_call()
        if defense_call is None:
            defense_call = game.get_ai_defense_call()

        # Normalize for engine and record_play
        norm_call = _normalize_offense_choice(offense_call)
        if norm_call == "1":
            game_run_calls[offense_name] += 1
        else:
            game_pass_calls[offense_name] += 1

        possession_side = game.possession
        down_before = game.down
        result = game.run_play(offense_call, defense_call, offense_team=offense_team, defense_team=defense_team)
        record_play(stats_map, home_team, away_team, home_dc, away_dc, possession_side, norm_call, result)

        if result.get("needs_pat"):
            game.attempt_extra_point_kick(defense_pat_choice="return")
            game.finish_pat_and_kickoff()
            time.sleep(0.005)
            continue

        # 2PT conversion
        if result.get("needs_2pt"):
            yards = result.get("yards", 0)
            game_team_stats[offense_name]["total_plays"] += 1
            if norm_call == "1":
                game_team_stats[offense_name]["run_plays"] += 1
                game_team_stats[offense_name]["rush_yards"] += yards
            else:
                game_team_stats[offense_name]["pass_plays"] += 1
                game_team_stats[offense_name]["pass_yards"] += yards
            game_team_stats[offense_name]["touchdowns"] += 1
            season_stats[offense_name]["total_plays"] += 1
            if norm_call == "1":
                season_stats[offense_name]["run_plays"] += 1
                season_stats[offense_name]["rush_yards"] += yards
            else:
                season_stats[offense_name]["pass_plays"] += 1
                season_stats[offense_name]["pass_yards"] += yards
            season_stats[offense_name]["touchdowns"] += 1
            game.attempt_two_point(offense_call, defense_call)
            game.setup_ot_possession()
            game.check_ot_period_end()
            time.sleep(0.005)
            continue

        converted = result.get("touchdown") or result.get("first_down")
        yards = result.get("yards", 0)

        game_team_stats[offense_name]["total_plays"] += 1
        if norm_call == "1":
            game_team_stats[offense_name]["run_plays"] += 1
            game_team_stats[offense_name]["rush_yards"] += yards
        else:
            game_team_stats[offense_name]["pass_plays"] += 1
            game_team_stats[offense_name]["pass_yards"] += yards
        if result.get("touchdown"):
            game_team_stats[offense_name]["touchdowns"] += 1

        season_stats[offense_name]["total_plays"] += 1
        if norm_call == "1":
            season_stats[offense_name]["run_plays"] += 1
            season_stats[offense_name]["rush_yards"] += yards
            if yards > 10:
                season_stats[offense_name]["explosive_run"] += 1
        else:
            season_stats[offense_name]["pass_plays"] += 1
            season_stats[offense_name]["pass_yards"] += yards
            if yards > 20 and not result.get("interception"):
                season_stats[offense_name]["explosive_pass"] += 1
            if not result.get("sack"):
                season_stats[offense_name]["pass_attempts"] += 1
                if not result.get("interception") and not result.get("incomplete_pass"):
                    season_stats[offense_name]["pass_completions"] += 1
        if result.get("touchdown"):
            season_stats[offense_name]["touchdowns"] += 1
        if down_before == 3:
            season_stats[offense_name]["third_down_attempts"] += 1
            if converted:
                season_stats[offense_name]["third_down_conversions"] += 1
        elif down_before == 4:
            season_stats[offense_name]["fourth_down_attempts"] += 1
            if converted:
                season_stats[offense_name]["fourth_down_conversions"] += 1
        season_stats[offense_name]["time_of_possession"] += result.get("clock_elapsed", 0)
        if result.get("sack"):
            season_stats[defense_name]["sacks"] += 1

        if result.get("ot_possession_ended"):
            game.check_ot_period_end()

        game.advance_quarter()
        time.sleep(0.005)

    # Turnovers
    season_stats[home_name]["interceptions"] += game.interceptions_home
    season_stats[away_name]["interceptions"] += game.interceptions_away
    season_stats[home_name]["fumbles"] += game.fumbles_home
    season_stats[away_name]["fumbles"] += game.fumbles_away
    season_stats[home_name]["turnovers"] += game.interceptions_home + game.fumbles_home
    season_stats[away_name]["turnovers"] += game.interceptions_away + game.fumbles_away
    game_team_stats[home_name]["turnovers"] = game.interceptions_home + game.fumbles_home
    game_team_stats[away_name]["turnovers"] = game.interceptions_away + game.fumbles_away

    standings[home_name]["points_for"] += game.score_home
    standings[home_name]["points_against"] += game.score_away
    standings[away_name]["points_for"] += game.score_away
    standings[away_name]["points_against"] += game.score_home

    if game.ot_winner:
        winner = home_name if game.ot_winner == "home" else away_name
        loser = away_name if game.ot_winner == "home" else home_name
        standings[winner]["wins"] += 1
        standings[loser]["losses"] += 1
    else:
        if game.score_home > game.score_away:
            standings[home_name]["wins"] += 1
            standings[away_name]["losses"] += 1
        else:
            standings[home_name]["losses"] += 1
            standings[away_name]["wins"] += 1

    rec = load_records()
    update_records_from_game(rec, stats_map, home_name, away_name, game.score_home, game.score_away, season_num)
    save_records(rec)
    merge_game_stats_into_season(season_player_stats, stats_map)

    return {
        "home": home_name,
        "away": away_name,
        "home_score": game.score_home,
        "away_score": game.score_away,
        "ot": bool(game.ot_winner),
        "home_stats": game_team_stats[home_name],
        "away_stats": game_team_stats[away_name],
        "home_run_calls": game_run_calls[home_name],
        "home_pass_calls": game_pass_calls[home_name],
        "away_run_calls": game_run_calls[away_name],
        "away_pass_calls": game_pass_calls[away_name],
    }


def format_game_result(g: dict) -> list:
    lines = []
    ot = " (OT)" if g["ot"] else ""
    lines.append(f"  {g['home']} {g['home_score']} - {g['away']} {g['away_score']}{ot}")
    h = g["home_stats"]
    a = g["away_stats"]
    hr, hp = g["home_run_calls"], g["home_pass_calls"]
    ar, ap = g["away_run_calls"], g["away_pass_calls"]
    lines.append(f"    {g['home']}: {h['rush_yards']} rush / {h['pass_yards']} pass | {h['total_plays']} plays | Run calls: {hr} | Pass calls: {hp}")
    lines.append(f"    {g['away']}: {a['rush_yards']} rush / {a['pass_yards']} pass | {a['total_plays']} plays | Run calls: {ar} | Pass calls: {ap}")
    return lines


def format_leaderboard(season_player_stats: dict, team_names: list) -> list:
    lines = []
    all_stats = list(season_player_stats.values())
    if not all_stats:
        return ["  (No stats)"]

    # Top passer (pass yards)
    qbs = [s for s in all_stats if s.att > 0]
    qbs.sort(key=lambda s: -s.pass_yds)
    if qbs:
        s = qbs[0]
        lines.append(f"  Top Passer: {s.player_name} ({s.team_name}) - {s.pass_yds} yds, {s.comp}/{s.att}, {s.pass_td} TD, {s.int_thrown} INT")

    # Top rusher
    rbs = [s for s in all_stats if s.rush_yds != 0 or s.rush_td > 0]
    rbs.sort(key=lambda s: (-s.rush_yds, -s.rush_td))
    if rbs:
        s = rbs[0]
        lines.append(f"  Top Rusher: {s.player_name} ({s.team_name}) - {s.rush_yds} yds, {s.rush_td} TD")

    # Top receiver
    recs = [s for s in all_stats if s.rec > 0 or s.rec_yds != 0 or s.rec_td > 0]
    recs.sort(key=lambda s: (-s.rec_yds, -s.rec))
    if recs:
        s = recs[0]
        lines.append(f"  Top Receiver: {s.player_name} ({s.team_name}) - {s.rec} rec, {s.rec_yds} yds, {s.rec_td} TD")

    # Top sacks
    sack_list = [s for s in all_stats if s.sacks > 0]
    sack_list.sort(key=lambda s: -s.sacks)
    if sack_list:
        s = sack_list[0]
        lines.append(f"  Top Sacks: {s.player_name} ({s.team_name}) - {s.sacks} sacks")

    # Top tackles
    tack = [s for s in all_stats if s.tackles > 0]
    tack.sort(key=lambda s: -s.tackles)
    if tack:
        s = tack[0]
        lines.append(f"  Top Tackles: {s.player_name} ({s.team_name}) - {s.tackles} tackles")
    return lines


def format_coaches_section(teams: dict) -> list:
    lines = []
    for name, team in teams.items():
        coach = getattr(team, "coach", None)
        if coach:
            style = getattr(coach, "offensive_style", None)
            tendency = getattr(style, "value", "?") if style else "?"
            lines.append(f"  {name}: {coach.name} - Play Call Tendency: {tendency}")
        else:
            lines.append(f"  {name}: (no coach)")
    return lines


def main():
    output_lines = []

    output_lines.append("FRIDAY NIGHT DYNASTY - 10 SEASON TEST")
    output_lines.append("Playbooks enabled (coach tendencies affect play calling)")
    output_lines.append("=" * 60)

    # Create teams from data/teams.json
    teams = build_teams_from_json(generate_roster=True, two_way_chance=0.55, assign_coaches=True)
    team_names = list(teams.keys())
    schedule = build_schedule_10_game(team_names)

    for season_num in range(1, 11):
        output_lines.append("")
        output_lines.append("=" * 60)
        output_lines.append(f"SEASON {season_num}")
        output_lines.append("=" * 60)

        # Coaches and tendencies
        output_lines.append("")
        output_lines.append("COACHES & PLAY CALLING TENDENCIES")
        output_lines.append("-" * 50)
        output_lines.extend(format_coaches_section(teams))

        standings = {name: {"wins": 0, "losses": 0, "points_for": 0, "points_against": 0} for name in team_names}
        season_stats = init_season_stats(team_names)
        season_player_stats: dict = {}

        output_lines.append("")
        output_lines.append("GAME RESULTS & STATS (no play-by-play)")
        output_lines.append("-" * 50)

        game_results = []
        for home_name, away_name in schedule:
            home = teams[home_name]
            away = teams[away_name]
            home_pb = build_playbook_for_team(home)
            away_pb = build_playbook_for_team(away)
            g = run_game_with_playbooks(
                home, away, season_stats, standings, season_player_stats,
                home_pb, away_pb, season_num=season_num,
            )
            game_results.append(g)
            output_lines.extend(format_game_result(g))

        # Playoffs
        champion, bracket_results = run_playoff(teams, standings, team_names, None, season_player_stats)
        for br in (bracket_results or []):
            output_lines.append(f"  Playoff: {br['home']} {br.get('home_score', '?')} - {br['away']} {br.get('away_score', '?')} -> {br['winner']}")

        runner_up = ""
        if bracket_results:
            last = bracket_results[-1]
            runner_up = last["away"] if last["winner"] == last["home"] else last["home"]
        append_season(
            champion=champion,
            runner_up=runner_up,
            team_names=team_names,
            standings=standings,
            season_player_stats=season_player_stats,
        )

        # Coach career phase then prestige
        league_history = load_league_history()
        coach_events, coach_changes = run_coach_career_phase(
            teams,
            league_history=league_history,
            standings=standings,
            current_year=season_num + 1,
        )
        for ev in coach_events:
            output_lines.append(f"  [Coach] {ev['detail']}")
        update_prestige(teams, league_history, coach_changes=coach_changes)

        # Final standings
        output_lines.append("")
        output_lines.append("FINAL STANDINGS")
        output_lines.append("-" * 50)
        for name in sorted(team_names, key=lambda n: (-standings[n]["wins"], -(standings[n]["points_for"] - standings[n]["points_against"]))):
            r = standings[name]
            pd = r["points_for"] - r["points_against"]
            output_lines.append(f"  {name}: {r['wins']}-{r['losses']} (PF {r['points_for']} PA {r['points_against']} PD {pd:+d})")

        # Season leaderboard
        output_lines.append("")
        output_lines.append("SEASON LEADERBOARD")
        output_lines.append("-" * 50)
        output_lines.extend(format_leaderboard(season_player_stats, team_names))

        # Awards
        output_lines.append("")
        awards = compute_awards(season_player_stats)
        output_lines.extend(format_awards_text(awards))

        # Player stats by team
        output_lines.append("")
        output_lines.append("PLAYER STATS BY TEAM")
        output_lines.append("-" * 50)
        player_stats_lines = format_season_player_stats(season_player_stats, team_names_order=team_names, top_n=10)
        output_lines.extend(player_stats_lines)

        output_lines.append("")
        output_lines.append(f"CHAMPION: {champion}")
        output_lines.append("")

        # Offseason for next season
        if season_num < 10:
            run_offseason_all_teams(list(teams.values()), standings, season_stats)

    output_lines.append("=" * 60)
    output_lines.append("RECORD BOOK")
    output_lines.append("=" * 60)
    output_lines.extend(format_records_text(load_records()))
    output_lines.append("")
    output_lines.append("=" * 60)
    output_lines.append("END OF 10 SEASON TEST")
    output_lines.append("=" * 60)

    out = "\n".join(output_lines)
    out_path = "ten_season_test_results.txt"
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(out)

    print(f"10 seasons complete! Results written to {out_path}")
    print("\nSummary:")
    for season_num in range(1, 11):
        print(f"  Season {season_num}: See {out_path} for details")


if __name__ == "__main__":
    main()
