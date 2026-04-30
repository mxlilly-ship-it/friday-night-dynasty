"""
Run 10-year simulation showing incoming 9th grade classes for each team.
Each year: full season (games + playoffs) -> offseason (graduation, add freshmen).
Output: recruiting class summary per team per year.
"""

import sys
import os
import time

sys.path.insert(0, ".")

# Suppress game engine print output during sim
DEVNULL = open(os.devnull, "w")

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
from systems.recruiting_system import compute_recruiting_score
from systems.offseason_manager import run_offseason_all_teams
from systems.game_stats import create_game_stats, record_play, merge_game_stats_into_season
from engine.game_engine import Game, _normalize_offense_choice
from play_single_game import sync_game_ratings


from systems.schedule_system import build_schedule_10_game


def init_season_stats(team_names):
    return {
        name: {"rush_yards": 0, "pass_yards": 0, "touchdowns": 0, "turnovers": 0,
               "sacks": 0, "interceptions": 0, "fumbles": 0, "total_plays": 0,
               "run_plays": 0, "pass_plays": 0, "pass_attempts": 0, "pass_completions": 0,
               "explosive_run": 0, "explosive_pass": 0, "time_of_possession": 0,
               "third_down_attempts": 0, "third_down_conversions": 0,
               "fourth_down_attempts": 0, "fourth_down_conversions": 0,}
        for name in team_names
    }


def run_game_quick(home_team, away_team, season_stats, standings, season_player_stats, home_pb, away_pb, season_num=1):
    """Run one game with playbooks. Minimal output."""
    home_name, away_name = home_team.name, away_team.name
    home_ratings = calculate_team_ratings(home_team)
    away_ratings = calculate_team_ratings(away_team)
    home_turnover = calculate_turnover_profile(home_team)
    away_turnover = calculate_turnover_profile(away_team)
    stats_map, home_dc, away_dc = create_game_stats(home_team, away_team)

    game = Game(offense_rating=home_ratings["offense"], defense_rating=away_ratings["defense"],
                run_rating=home_ratings["run"], pass_rating=home_ratings["pass"])
    game.home_team_name = home_name
    game.away_team_name = away_name
    sync_game_ratings(game, home_ratings, away_ratings, home_turnover, away_turnover)
    game.apply_opening_kickoff()

    old_stdout = sys.stdout
    sys.stdout = DEVNULL
    try:
        while not game.is_game_over():
            sync_game_ratings(game, home_ratings, away_ratings, home_turnover, away_turnover)
            if game.ot_2pt_mode:
                off = home_team if game.possession == "home" else away_team
                def_t = away_team if game.possession == "home" else home_team
                sit = build_situation_from_game(game, offense_team=off, defense_team=def_t)
                off_pb = home_pb if game.possession == "home" else away_pb
                def_pb = away_pb if game.possession == "home" else home_pb
                o = pick_offensive_play(off_pb, sit, offense_team=off)
                d = pick_defensive_play(def_pb, sit, defense_team=def_t)
                game.run_play_2pt_shootout(o, d)
                game.advance_quarter()
                time.sleep(0.001)
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
                    time.sleep(0.001)
                    continue

            offense_team = home_team if game.possession == "home" else away_team
            defense_team = away_team if game.possession == "home" else home_team
            sit = build_situation_from_game(game, offense_team=offense_team, defense_team=defense_team)
            off_pb = home_pb if game.possession == "home" else away_pb
            def_pb = away_pb if game.possession == "home" else home_pb
            off_call = pick_offensive_play(off_pb, sit, offense_team=offense_team)
            def_call = pick_defensive_play(def_pb, sit, defense_team=defense_team)
            off_call = off_call or game.get_ai_play_call()
            def_call = def_call or game.get_ai_defense_call()
            norm = _normalize_offense_choice(off_call)
            result = game.run_play(off_call, def_call, offense_team=offense_team, defense_team=defense_team)
            record_play(stats_map, home_team, away_team, home_dc, away_dc, game.possession, norm, result)

            if result.get("needs_pat"):
                game.attempt_extra_point_kick(defense_pat_choice="return")
                game.finish_pat_and_kickoff()
                time.sleep(0.001)
                continue

            if result.get("needs_2pt"):
                yards = result.get("yards", 0)
                offense_name = offense_team.name
                season_stats[offense_name]["total_plays"] += 1
                season_stats[offense_name]["run_plays" if norm == "1" else "pass_plays"] += 1
                season_stats[offense_name]["rush_yards" if norm == "1" else "pass_yards"] += yards
                season_stats[offense_name]["touchdowns"] += 1
                game.attempt_two_point(off_call, def_call)
                game.setup_ot_possession()
                game.check_ot_period_end()
                time.sleep(0.001)
                continue

            offense_name = offense_team.name
            defense_name = defense_team.name
            yards = result.get("yards", 0)
            season_stats[offense_name]["total_plays"] += 1
            if norm == "1":
                season_stats[offense_name]["run_plays"] += 1
                season_stats[offense_name]["rush_yards"] += yards
            else:
                season_stats[offense_name]["pass_plays"] += 1
                season_stats[offense_name]["pass_yards"] += yards
            if result.get("touchdown"):
                season_stats[offense_name]["touchdowns"] += 1
            if game.down == 3 and (result.get("touchdown") or result.get("first_down")):
                season_stats[offense_name]["third_down_attempts"] += 1
                season_stats[offense_name]["third_down_conversions"] += 1
            elif game.down == 3:
                season_stats[offense_name]["third_down_attempts"] += 1
            if result.get("sack"):
                season_stats[defense_name]["sacks"] += 1
            season_stats[offense_name]["time_of_possession"] += result.get("clock_elapsed", 0)

            if result.get("ot_possession_ended"):
                game.check_ot_period_end()
            game.advance_quarter()
            time.sleep(0.001)
    finally:
        sys.stdout = old_stdout

    season_stats[home_name]["interceptions"] += game.interceptions_home
    season_stats[away_name]["interceptions"] += game.interceptions_away
    season_stats[home_name]["fumbles"] += game.fumbles_home
    season_stats[away_name]["fumbles"] += game.fumbles_away
    season_stats[home_name]["turnovers"] = season_stats[home_name]["interceptions"] + season_stats[home_name]["fumbles"]
    season_stats[away_name]["turnovers"] = season_stats[away_name]["interceptions"] + season_stats[away_name]["fumbles"]
    standings[home_name]["points_for"] += game.score_home
    standings[home_name]["points_against"] += game.score_away
    standings[away_name]["points_for"] += game.score_away
    standings[away_name]["points_against"] += game.score_home
    if game.ot_winner:
        w = home_name if game.ot_winner == "home" else away_name
        l = away_name if game.ot_winner == "home" else home_name
        standings[w]["wins"] += 1
        standings[l]["losses"] += 1
    elif game.score_home > game.score_away:
        standings[home_name]["wins"] += 1
        standings[away_name]["losses"] += 1
    else:
        standings[home_name]["losses"] += 1
        standings[away_name]["wins"] += 1
    rec = load_records()
    update_records_from_game(rec, stats_map, home_name, away_name, game.score_home, game.score_away, season_num)
    save_records(rec)
    merge_game_stats_into_season(season_player_stats, stats_map)


def format_recruiting_class(team_name: str, added: list, recruiting_score: float) -> list:
    """Format one team's incoming 9th grade class for output."""
    if not added:
        return [f"  {team_name}: No recruits this year (roster full)"]
    avg_pot = sum(p.potential for p in added) / len(added)
    top = sorted(added, key=lambda p: -p.potential)[:5]
    lines = [
        f"  {team_name} (Recruiting Score: {recruiting_score:.1f})",
        f"    {len(added)} recruits | Avg potential: {avg_pot:.1f}",
        f"    Top 5: " + ", ".join(f"{p.name} ({p.position}) {p.potential}" for p in top),
    ]
    return lines


def main():
    output_lines = [
        "FRIDAY NIGHT DYNASTY - 10 YEAR RECRUITING SIMULATION",
        "=" * 60,
    ]

    teams = build_teams_from_json(generate_roster=True, two_way_chance=0.55, assign_coaches=True)
    team_names = list(teams.keys())
    schedule = build_schedule_10_game(team_names)

    # Store classes by team for recruiting_classes_by_team.txt
    classes_by_team: dict = {name: [] for name in team_names}

    for year in range(1, 11):
        output_lines.append("")
        output_lines.append("=" * 60)
        output_lines.append(f"YEAR {year}")
        output_lines.append("=" * 60)

        # Run season
        standings = {n: {"wins": 0, "losses": 0, "points_for": 0, "points_against": 0} for n in team_names}
        season_stats = init_season_stats(team_names)
        season_player_stats = {}
        for home_name, away_name in schedule:
            home_pb = build_playbook_for_team(teams[home_name])
            away_pb = build_playbook_for_team(teams[away_name])
            run_game_quick(teams[home_name], teams[away_name], season_stats, standings,
                          season_player_stats, home_pb, away_pb, season_num=year)
        _so, sys.stdout = sys.stdout, DEVNULL
        try:
            champion, bracket = run_playoff(teams, standings, team_names, None, season_player_stats)
        finally:
            sys.stdout = _so
        runner_up = (bracket[-1]["away"] if bracket and bracket[-1]["winner"] == bracket[-1]["home"] else bracket[-1]["home"]) if bracket else ""
        append_season(champion, runner_up,
                     team_names, standings, season_player_stats)

        # Coach career phase, prestige, then offseason
        league_history = load_league_history()
        coach_events, coach_changes = run_coach_career_phase(
            teams,
            league_history=league_history,
            standings=standings,
            current_year=year + 1,
        )
        for ev in coach_events:
            output_lines.append(f"  [Coach] {ev['detail']}")
        update_prestige(teams, league_history, coach_changes=coach_changes)
        results = run_offseason_all_teams(list(teams.values()), standings, season_stats, league_history=league_history)

        output_lines.append("")
        output_lines.append("Season result: " + champion + " State Champion")
        output_lines.append("Standings: " + ", ".join(f"{n} {standings[n]['wins']}-{standings[n]['losses']}" for n in sorted(team_names, key=lambda x: -standings[x]["wins"])))
        awards = compute_awards(season_player_stats)
        output_lines.extend(format_awards_text(awards))
        output_lines.append("")
        output_lines.append("INCOMING 9TH GRADE CLASSES")
        output_lines.append("-" * 50)
        for name in team_names:
            added = results[name].get("added", [])
            rec_score = compute_recruiting_score(teams[name], league_history)
            output_lines.extend(format_recruiting_class(name, added, rec_score))
            output_lines.append("")
            classes_by_team[name].append({
                "year": year,
                "champion": champion,
                "added": added,
                "rec_score": rec_score,
            })

    output_lines.append("=" * 60)
    output_lines.append("RECORD BOOK")
    output_lines.append("=" * 60)
    output_lines.extend(format_records_text(load_records()))
    output_lines.append("")
    output_lines.append("=" * 60)
    output_lines.append("END OF 10 YEAR RECRUITING SIMULATION")
    output_lines.append("=" * 60)

    out = "\n".join(output_lines)
    path = "ten_year_recruiting_sim.txt"
    with open(path, "w", encoding="utf-8") as f:
        f.write(out)

    # Write recruiting_classes_by_team.txt - one section per team, all 10 years
    by_team_lines = [
        "FRIDAY NIGHT DYNASTY - RECRUITING CLASSES BY TEAM",
        "=" * 60,
        "Incoming 9th grade classes for each team across 10 years.",
        "",
    ]
    for name in team_names:
        by_team_lines.append("=" * 60)
        by_team_lines.append(name.upper())
        by_team_lines.append("=" * 60)
        for entry in classes_by_team[name]:
            yr, champ, added, rec = entry["year"], entry["champion"], entry["added"], entry["rec_score"]
            by_team_lines.append(f"\nYear {yr} (Champion: {champ})")
            by_team_lines.append(f"  Recruiting Score: {rec:.1f} | {len(added)} recruits")
            if added:
                avg = sum(p.potential for p in added) / len(added)
                by_team_lines.append(f"  Avg potential: {avg:.1f}")
                top = sorted(added, key=lambda p: -p.potential)[:5]
                by_team_lines.append("  Top 5: " + ", ".join(f"{p.name} ({p.position}) {p.potential}" for p in top))
                by_team_lines.append("  Full class: " + ", ".join(f"{p.name} {p.position}/{p.potential}" for p in sorted(added, key=lambda p: -p.potential)))
            else:
                by_team_lines.append("  (No recruits - roster full)")
        by_team_lines.append("")

    by_team_path = "recruiting_classes_by_team.txt"
    with open(by_team_path, "w", encoding="utf-8") as f:
        f.write("\n".join(by_team_lines))

    print(f"10-year recruiting sim complete!")
    print(f"  By year: {path}")
    print(f"  By team: {by_team_path}")


if __name__ == "__main__":
    main()
