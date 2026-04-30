"""
Play a league as an individual save: New Game / Load Game, then Sim Season, View Standings/Rosters, Save & Exit.
Each save lives in saves/<name>/ with its own league_save.json, league_history.json, and records.json.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from systems.save_system import (
    list_saves,
    get_save_dir,
    save_league,
    load_league,
    ensure_save_has_history_and_records,
    league_history_path,
)
from systems.teams_loader import build_teams_from_json
from systems.league_history import load_league_history
from systems.offseason_manager import run_offseason_all_teams
from systems.schedule_system import build_weeks_10_game
from systems.playoff_system import run_playoff
from systems.league_history import append_season
from systems.prestige_system import update_prestige
from systems.coach_career_system import run_coach_career_phase
from systems.game_stats import format_season_player_stats
from run_season import init_season_stats, parse_scores_from_final_line, run_game_silent
from play_single_game import play_game_human_coach
from models.coach import Coach, OffensiveStyle, DefensiveStyle


def _prompt(msg: str, default: str = "") -> str:
    s = input(msg).strip()
    return s if s else default


def _prompt_int(msg: str, lo: int, hi: int, default: int) -> int:
    while True:
        s = input(msg).strip()
        if not s:
            return default
        try:
            n = int(s)
            if lo <= n <= hi:
                return n
        except ValueError:
            pass
        print(f"  Enter a number from {lo} to {hi}.")


def _setup_your_team_and_coach(teams):
    """
    Let the user select their team, name the coach, and set coach attributes.
    Modifies the chosen team's coach in place; returns the chosen team name for display.
    """
    team_names = sorted(teams.keys())
    print("\n  Select YOUR team (you'll play as this program):")
    for i, name in enumerate(team_names, 1):
        print(f"    {i}) {name}")
    idx = _prompt_int(f"  Team number (1-{len(team_names)}): ", 1, len(team_names), 1)
    your_team_name = team_names[idx - 1]
    team = teams[your_team_name]
    coach = team.coach
    if coach is None:
        coach = Coach(name="Coach")
        team.coach = coach

    name = _prompt(f"  Enter your head coach's name (or Enter to keep '{coach.name}'): ", coach.name)
    if name:
        coach.name = name.strip()

    print("\n  Offensive style:")
    for i, s in enumerate(OffensiveStyle, 1):
        print(f"    {i}) {s.value}")
    off_idx = _prompt_int(f"  Choice (1-{len(OffensiveStyle)}): ", 1, len(OffensiveStyle), 3)  # 3 = BALANCED
    coach.offensive_style = list(OffensiveStyle)[off_idx - 1]

    print("\n  Defensive style:")
    for i, s in enumerate(DefensiveStyle, 1):
        print(f"    {i}) {s.value}")
    def_idx = _prompt_int(f"  Choice (1-{len(DefensiveStyle)}): ", 1, len(DefensiveStyle), 1)  # 1 = BASE
    coach.defensive_style = list(DefensiveStyle)[def_idx - 1]

    print("\n  Coach ratings (1-10). Enter to keep defaults (5).")
    for attr in ("playcalling", "player_development", "recruiting", "culture", "community_outreach", "scheme_teach"):
        label = attr.replace("_", " ").title()
        val = _prompt_int(f"  {label} (1-10): ", 1, 10, 5)
        setattr(coach, attr, val)

    print(f"\n  {your_team_name} — Head Coach: {coach.name} ({coach.offensive_style.value} / {coach.defensive_style.value})")
    return your_team_name


def _init_standings(team_names):
    return {name: {"wins": 0, "losses": 0, "points_for": 0, "points_against": 0} for name in team_names}


def _weeks_to_save_shape(weeks):
    return [[{"home": h, "away": a} for (h, a) in wk] for wk in weeks]


def _empty_week_results(weeks):
    return [[{"played": False, "home_score": 0, "away_score": 0, "ot": False} for _ in wk] for wk in weeks]


def _find_user_game_index(week_games, user_team):
    for i, (h, a) in enumerate(week_games):
        if h == user_team or a == user_team:
            return i
    return None


def _save_state(save_name, teams, current_year, user_team, current_week, season_phase, weeks, week_results, standings):
    save_league(
        save_name,
        teams,
        current_year,
        user_team=user_team,
        current_week=current_week,
        season_phase=season_phase,
        weeks=_weeks_to_save_shape(weeks),
        week_results=week_results,
        standings=standings,
    )


def _finish_season_and_advance_year(teams, save_dir, save_name, current_year, standings, season_player_stats, user_team):
    output_lines = []
    team_names = list(teams.keys())
    champion, bracket_results = run_playoff(teams, standings, team_names, output_lines, season_player_stats)
    runner_up = ""
    if bracket_results:
        champ_game = bracket_results[-1]
        runner_up = champ_game["away"] if champ_game["winner"] == champ_game["home"] else champ_game["home"]

    append_season(
        champion=champion,
        runner_up=runner_up,
        team_names=team_names,
        standings=standings,
        season_player_stats=season_player_stats,
        year=current_year,
        save_dir=save_dir,
    )

    league_history = load_league_history(league_history_path(save_dir))
    coach_events, coach_changes = run_coach_career_phase(
        teams,
        league_history=league_history,
        standings=standings,
        current_year=current_year + 1,
    )
    update_prestige(teams, league_history, coach_changes=coach_changes)

    # Offseason and advance year
    run_offseason_all_teams(list(teams.values()), standings=standings)
    current_year += 1
    return current_year, champion


def main_menu(teams, current_year, save_dir, save_name, state):
    """Week-by-week play loop."""
    team_names = sorted(teams.keys())
    user_team = state.get("user_team")
    current_week = int(state.get("current_week", 1))
    season_phase = state.get("season_phase", "regular")

    # Load or create schedule + standings
    saved_weeks = state.get("weeks") or []
    if saved_weeks:
        weeks = [[(g["home"], g["away"]) for g in wk] for wk in saved_weeks]
    else:
        weeks = build_weeks_10_game(team_names)

    standings = state.get("standings") or _init_standings(team_names)
    week_results = state.get("week_results") or _empty_week_results(weeks)

    # In-memory season stats (not persisted mid-year yet)
    season_stats = init_season_stats(team_names)
    season_player_stats = {}

    while True:
        if season_phase == "playoffs":
            print("\n  Regular season complete. Running playoffs + offseason...")
            current_year, champ = _finish_season_and_advance_year(
                teams, save_dir, save_name, current_year, standings, season_player_stats, user_team
            )
            print(f"  Champion: {champ}")

            # Start next year fresh
            weeks = build_weeks_10_game(team_names)
            standings = _init_standings(team_names)
            week_results = _empty_week_results(weeks)
            current_week = 1
            season_phase = "regular"
            season_stats = init_season_stats(team_names)
            season_player_stats = {}
            _save_state(save_name, teams, current_year, user_team, current_week, season_phase, weeks, week_results, standings)
            print(f"  Advanced to Year {current_year}. Week 1 is ready.")

        print()
        print("=" * 50)
        ut = user_team or "None"
        print(f"  FRIDAY NIGHT DYNASTY  —  {save_name}  —  Year {current_year}  —  Week {current_week}  —  {ut}")
        print("=" * 50)
        print("  1) Play week (you call plays for your game)")
        print("  2) Sim week")
        print("  3) View current standings")
        print("  4) View week results")
        print("  5) View rosters")
        print("  6) Save & exit")
        print("  7) Quit without saving")
        print()
        choice = _prompt_int("Choice (1-7): ", 1, 7, 1)

        if choice in (1, 2):
            if season_phase != "regular":
                print("  Not in regular season.")
                continue
            if not user_team:
                print("  No user team set for this save.")
                continue
            if current_week < 1 or current_week > len(weeks):
                print("  Season is complete. Proceeding to playoffs/offseason...")
                season_phase = "playoffs"
            else:
                wk_idx = current_week - 1
                week_games = weeks[wk_idx]

                # Sim or play games in this week
                user_game_i = _find_user_game_index(week_games, user_team)
                if user_game_i is None:
                    print("  Bye week for your team. Simulating the week.")
                    choice = 2

                for gi, (home, away) in enumerate(week_games):
                    if week_results[wk_idx][gi].get("played"):
                        continue
                    ot = False
                    if choice == 1 and gi == user_game_i:
                        print(f"\n  Your game: {home} vs {away}")
                        res = play_game_human_coach(teams[home], teams[away], human_team_name=user_team, verbose=True)
                        hs, as_ = res["home_score"], res["away_score"]
                        recap = f"FINAL: {home} {hs} - {away} {as_}\n\n(Human-coached game — recap not archived.)"
                    else:
                        # Silent sim (keeps standings/stats updates)
                        game_lines = []
                        run_game_silent(teams[home], teams[away], teams, season_stats, standings, game_lines, season_player_stats, team_schedules=None)
                        hs, as_ = 0, 0
                        for line in reversed(game_lines):
                            if isinstance(line, str) and line.startswith("FINAL:"):
                                ot = "(OT)" in line
                                parsed = parse_scores_from_final_line(line)
                                if parsed is not None:
                                    hs, as_ = parsed
                                else:
                                    hs, as_ = 0, 0
                                break
                        recap = "\n".join(game_lines).strip()

                    week_results[wk_idx][gi] = {
                        "played": True,
                        "home_score": hs,
                        "away_score": as_,
                        "ot": ot,
                        "recap": recap,
                    }

                    # Update standings for human game (since play_single_game doesn't update standings)
                    if choice == 1 and gi == user_game_i:
                        standings[home]["points_for"] += hs
                        standings[home]["points_against"] += as_
                        standings[away]["points_for"] += as_
                        standings[away]["points_against"] += hs
                        if hs > as_:
                            standings[home]["wins"] += 1
                            standings[away]["losses"] += 1
                        else:
                            standings[away]["wins"] += 1
                            standings[home]["losses"] += 1

                current_week += 1

                _save_state(save_name, teams, current_year, user_team, current_week, season_phase, weeks, week_results, standings)
                print(f"  Week complete. Saved. Now Week {current_week}.")

                if current_week > len(weeks):
                    season_phase = "playoffs"

        elif choice == 3:
            print("\n  CURRENT STANDINGS")
            order = sorted(team_names, key=lambda n: (-standings[n]["wins"], -(standings[n]["points_for"] - standings[n]["points_against"])))
            for name in order:
                r = standings[name]
                pd = r["points_for"] - r["points_against"]
                print(f"  {name}: {r['wins']}-{r['losses']} (PF {r['points_for']} PA {r['points_against']} PD {pd:+d})")

        elif choice == 4:
            wk = _prompt_int(f"  Which week (1-{len(weeks)}): ", 1, len(weeks), max(1, min(current_week, len(weeks))))
            wk_idx = wk - 1
            print(f"\n  WEEK {wk} RESULTS")
            for gi, (home, away) in enumerate(weeks[wk_idx]):
                r = week_results[wk_idx][gi]
                if not r.get("played"):
                    print(f"  {home} vs {away}: (unplayed)")
                else:
                    print(f"  {home} vs {away}: {r.get('home_score', 0)}-{r.get('away_score', 0)}")

        elif choice == 5:
            print("\n  Teams:")
            for i, name in enumerate(team_names, 1):
                print(f"    {i}) {name}")
            idx = _prompt_int(f"  Team number (1-{len(team_names)}): ", 1, len(team_names), 1)
            t = teams[team_names[idx - 1]]
            print(f"\n  {t.name} — Roster ({t.roster_size()} players)")
            for p in t.roster[:30]:
                pos = p.position or "?"
                print(f"    {pos:4} {p.name}")
            if t.roster_size() > 30:
                print(f"    ... and {t.roster_size() - 30} more")

        elif choice == 6:
            _save_state(save_name, teams, current_year, user_team, current_week, season_phase, weeks, week_results, standings)
            print("  Saved. Goodbye.")
            return

        else:  # 7
            print("  Quit without saving. Goodbye.")
            return


def start_new_league():
    name = _prompt("Name your save: ", "Untitled")
    if not name:
        name = "Untitled"
    save_name = "".join(c for c in name if c.isalnum() or c in " _-").strip() or "Untitled"
    save_dir = get_save_dir(save_name)
    if os.path.isdir(save_dir) and os.path.isfile(os.path.join(save_dir, "league_save.json")):
        overwrite = _prompt(f"Save '{save_name}' already exists. Overwrite? (y/N): ").strip().lower()
        if overwrite != "y":
            return
    print("  Building league from data/teams.json (rosters + coaches)...")
    teams = build_teams_from_json(generate_roster=True, two_way_chance=0.55, assign_coaches=True)
    user_team = _setup_your_team_and_coach(teams)
    current_year = 1
    team_names = sorted(teams.keys())
    weeks = build_weeks_10_game(team_names)
    standings = _init_standings(team_names)
    week_results = _empty_week_results(weeks)
    _save_state(save_name, teams, current_year, user_team, 1, "regular", weeks, week_results, standings)
    ensure_save_has_history_and_records(save_dir)
    print(f"  New league created: {save_name} (Year 1).")
    main_menu(teams, current_year, save_dir, save_name, {"user_team": user_team, "current_week": 1, "season_phase": "regular", "weeks": _weeks_to_save_shape(weeks), "week_results": week_results, "standings": standings})


def load_existing_league():
    saves = list_saves()
    if not saves:
        print("  No saves found. Create one with 'New League'.")
        return
    print("\n  Saves:")
    for i, s in enumerate(saves, 1):
        print(f"    {i}) {s}")
    idx = _prompt_int(f"  Load save (1-{len(saves)}): ", 1, len(saves), 1)
    save_name = saves[idx - 1]
    try:
        teams, current_year, save_dir, state = load_league(save_name)
        print(f"  Loaded '{save_name}' — Year {current_year}, {len(teams)} teams.")
        main_menu(teams, current_year, save_dir, save_name, state)
    except Exception as e:
        print(f"  Error loading save: {e}")


def main():
    print("FRIDAY NIGHT DYNASTY — Play a league (save/load)")
    print()
    while True:
        print("  1) New league")
        print("  2) Load league")
        print("  3) Quit")
        choice = _prompt_int("Choice (1-3): ", 1, 3, 1)
        if choice == 1:
            start_new_league()
            break
        if choice == 2:
            load_existing_league()
            break
        print("  Goodbye.")
        break


if __name__ == "__main__":
    main()
