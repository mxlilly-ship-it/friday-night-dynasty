"""
Play a single game between two teams with generated rosters.
1. Create two teams
2. Generate rosters for each
3. Calculate team overalls (offense, defense, run, pass) from roster
4. Simulate one game
"""

import sys
import time

# Add project root to path
sys.path.insert(0, ".")

from models import Team
from models.community import CommunityType
from systems import (
    generate_team_roster,
    assign_coaches_to_teams,
    calculate_team_ratings,
    calculate_turnover_profile,
    Playbook,
    build_playbook_for_team,
    build_situation_from_game,
    pick_offensive_play,
    pick_defensive_play,
)
from engine.game_engine import Game


def sync_game_ratings(
    game: Game,
    home_ratings: dict,
    away_ratings: dict,
    home_turnover: dict,
    away_turnover: dict,
) -> None:
    """Update game ratings + turnover profile based on current possession."""
    if game.possession == "home":
        game.offense_rating = home_ratings["offense"]
        game.defense_rating = away_ratings["defense"]
        game.run_rating = home_ratings["run"]
        game.pass_rating = home_ratings["pass"]
        game.qb_decision_rating = home_turnover["qb_decisions"]
        game.qb_arm_strength = home_turnover["qb_arm_strength"]
        game.qb_scramble_base = home_turnover.get("qb_scramble_base", 0.04)
        game.ball_security_rating = home_turnover["off_ball_security"]
        game.off_discipline_rating = home_turnover["off_discipline"]
        game.def_coverage_rating = away_turnover["def_coverage"]
        game.def_tackling_rating = away_turnover["def_tackling"]
        game.def_pass_rush_rating = away_turnover["def_pass_rush"]
    else:
        game.offense_rating = away_ratings["offense"]
        game.defense_rating = home_ratings["defense"]
        game.run_rating = away_ratings["run"]
        game.pass_rating = away_ratings["pass"]
        game.qb_decision_rating = away_turnover["qb_decisions"]
        game.qb_arm_strength = away_turnover["qb_arm_strength"]
        game.qb_scramble_base = away_turnover.get("qb_scramble_base", 0.04)
        game.ball_security_rating = away_turnover["off_ball_security"]
        game.off_discipline_rating = away_turnover["off_discipline"]
        game.def_coverage_rating = home_turnover["def_coverage"]
        game.def_tackling_rating = home_turnover["def_tackling"]
        game.def_pass_rush_rating = home_turnover["def_pass_rush"]


def play_single_game(
    home_team: Team,
    away_team: Team,
    verbose: bool = True,
    use_playbooks: bool = True,
) -> dict:
    """
    Play one game between two teams. Teams must have rosters.

    If use_playbooks is True (default), calls plays from coach offensive playbook and defensive playbook fronts
    and displays the play names. Otherwise uses legacy AI play calling.

    Returns dict with final score and basic stats.
    """
    home_ratings = calculate_team_ratings(home_team)
    away_ratings = calculate_team_ratings(away_team)
    home_turnover = calculate_turnover_profile(home_team)
    away_turnover = calculate_turnover_profile(away_team)

    if verbose:
        print(f"\n{'='*50}")
        print(f"  {home_team.name} vs {away_team.name}")
        print(f"{'='*50}")
        print(f"\nTeam Ratings:")
        print(f"  {home_team.name}: Off {home_ratings['offense']} | Def {home_ratings['defense']} | Run {home_ratings['run']} | Pass {home_ratings['pass']}")
        print(f"  {away_team.name}: Off {away_ratings['offense']} | Def {away_ratings['defense']} | Run {away_ratings['run']} | Pass {away_ratings['pass']}")
        print(f"\nRoster sizes: {home_team.roster_size()} vs {away_team.roster_size()}")

    game = Game(
        offense_rating=home_ratings["offense"],
        defense_rating=away_ratings["defense"],
        run_rating=home_ratings["run"],
        pass_rating=home_ratings["pass"],
    )
    game.home_team_name = home_team.name
    game.away_team_name = away_team.name
    sync_game_ratings(game, home_ratings, away_ratings, home_turnover, away_turnover)
    game.apply_opening_kickoff()

    # Build playbooks from each team's coach (offensive playbook + defensive playbook → multiple fronts; see build_playbook_for_team)
    home_playbook = away_playbook = None
    if use_playbooks:
        home_playbook = build_playbook_for_team(home_team)
        away_playbook = build_playbook_for_team(away_team)
        if verbose:
            h_off = getattr(home_team.coach, "offensive_formation", "Spread") if getattr(home_team, "coach", None) else "Spread"
            h_def = getattr(home_team.coach, "defensive_formation", "4-3") if getattr(home_team, "coach", None) else "4-3"
            a_off = getattr(away_team.coach, "offensive_formation", "Spread") if getattr(away_team, "coach", None) else "Spread"
            a_def = getattr(away_team.coach, "defensive_formation", "4-3") if getattr(away_team, "coach", None) else "4-3"
            print(f"\nPlaybooks: {home_team.name} {h_off} (off) / {h_def} (def) – {away_team.name} {a_off} (off) / {a_def} (def)\n")

    if verbose:
        print(f"\nKickoff! {home_team.name} vs {away_team.name}\n")

    while not game.is_game_over():
        # Sync ratings to current possession (home/away swap when ball turns over)
        sync_game_ratings(game, home_ratings, away_ratings, home_turnover, away_turnover)

        # NCAA OT 2-point shootout
        if game.ot_2pt_mode:
            if use_playbooks and home_playbook and away_playbook:
                off_team = home_team if game.possession == "home" else away_team
                def_team = away_team if game.possession == "home" else home_team
                sit = build_situation_from_game(game, offense_team=off_team, defense_team=def_team)
                off_pb = home_playbook if game.possession == "home" else away_playbook
                def_pb = away_playbook if game.possession == "home" else home_playbook
                o = pick_offensive_play(off_pb, sit, offense_team=off_team)
                d = pick_defensive_play(def_pb, sit, defense_team=def_team)
                result = game.run_play_2pt_shootout(o, d)
            else:
                result = game.run_play_2pt_shootout()
            game.advance_quarter()
            time.sleep(0.03)
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
                time.sleep(0.03)
                continue

        # Identify current offense/defense teams each snap
        offense_team = home_team if game.possession == "home" else away_team
        defense_team = away_team if game.possession == "home" else home_team

        # Call plays from playbooks or legacy AI
        if use_playbooks and home_playbook and away_playbook:
            situation = build_situation_from_game(game, offense_team=offense_team, defense_team=defense_team)
            offense_pb = home_playbook if game.possession == "home" else away_playbook
            defense_pb = away_playbook if game.possession == "home" else home_playbook
            offense_call = pick_offensive_play(offense_pb, situation, offense_team=offense_team)
            defense_call = pick_defensive_play(defense_pb, situation, defense_team=defense_team)
            if offense_call is None:
                offense_call = game.get_ai_play_call()
            if defense_call is None:
                defense_call = game.get_ai_defense_call()
        else:
            offense_call = game.get_ai_play_call()
            defense_call = game.get_ai_defense_call()

        result = game.run_play(offense_call, defense_call, offense_team=offense_team, defense_team=defense_team)

        if result.get("needs_pat"):
            game.attempt_extra_point_kick(defense_pat_choice="return")
            game.finish_pat_and_kickoff()
            time.sleep(0.03)
            continue

        # OT2: 2-point conversion after TD
        if result.get("needs_2pt"):
            if use_playbooks and home_playbook and away_playbook:
                off_team = home_team if game.possession == "home" else away_team
                def_team = away_team if game.possession == "home" else home_team
                sit = build_situation_from_game(game, offense_team=off_team, defense_team=def_team)
                off_pb = home_playbook if game.possession == "home" else away_playbook
                def_pb = away_playbook if game.possession == "home" else home_playbook
                o = pick_offensive_play(off_pb, sit, offense_team=off_team)
                d = pick_defensive_play(def_pb, sit, defense_team=def_team)
                game.attempt_two_point(o, d)
            else:
                game.attempt_two_point(offense_call, defense_call)
            game.setup_ot_possession()
            game.check_ot_period_end()
            time.sleep(0.03)
            continue

        if result.get("ot_possession_ended"):
            game.check_ot_period_end()

        game.advance_quarter()
        time.sleep(0.03)

    if verbose:
        game.end_game_summary()
        print(f"\nFINAL: {home_team.name} {game.score_home} - {away_team.name} {game.score_away}")

    return {
        "home_score": game.score_home,
        "away_score": game.score_away,
        "home_team": home_team.name,
        "away_team": away_team.name,
        "ot_winner": game.ot_winner,
        "home_turnovers": game.interceptions_home + game.fumbles_home,
        "away_turnovers": game.interceptions_away + game.fumbles_away,
        "home_interceptions": game.interceptions_home,
        "away_interceptions": game.interceptions_away,
        "home_fumbles": game.fumbles_home,
        "away_fumbles": game.fumbles_away,
    }


def play_game_human_coach(
    home_team: Team,
    away_team: Team,
    human_team_name: str,
    human_controls_offense: bool = True,
    human_controls_defense: bool = True,
    verbose: bool = True,
) -> dict:
    """
    Play one game where the user can call plays for one team.

    UI:
    - Lists actual plays from the team's playbook for offense and defense.
    - Enter selects AI recommendation for the situation.
    """
    home_ratings = calculate_team_ratings(home_team)
    away_ratings = calculate_team_ratings(away_team)
    home_turnover = calculate_turnover_profile(home_team)
    away_turnover = calculate_turnover_profile(away_team)

    game = Game(
        offense_rating=home_ratings["offense"],
        defense_rating=away_ratings["defense"],
        run_rating=home_ratings["run"],
        pass_rating=home_ratings["pass"],
    )
    game.home_team_name = home_team.name
    game.away_team_name = away_team.name
    sync_game_ratings(game, home_ratings, away_ratings, home_turnover, away_turnover)
    game.apply_opening_kickoff()

    home_playbook = build_playbook_for_team(home_team)
    away_playbook = build_playbook_for_team(away_team)

    if verbose:
        print(f"\n{'='*50}")
        print(f"  {home_team.name} vs {away_team.name}")
        print(f"{'='*50}\n")
        print(f"Human coach: {human_team_name}")

    def _format_play(p):
        note = ""
        md = getattr(p, "metadata", None) or {}
        if isinstance(md, dict):
            if "ball_carrier" in md:
                note = f" ({md['ball_carrier']})"
            elif "concept" in md:
                note = f" ({md['concept']})"
            elif "note" in md:
                note = f" ({md['note']})"
        return f"{p.name}{note} [{p.id}]"

    def prompt_offense_play(off_team, def_team, pb):
        from systems import play_caller as pc

        situation = build_situation_from_game(game, offense_team=off_team, defense_team=def_team)
        suggested_cat = pc._situation_to_offensive_category(situation)  # type: ignore
        candidates = pb.get_offensive_plays_by_category(suggested_cat)
        if not candidates:
            candidates = list(pb.offensive_plays)

        while True:
            print(f"\nOffense ({off_team.name}) — Suggested: {suggested_cat.value}")
            show = candidates[:10]
            for i, p in enumerate(show, 1):
                print(f"  {i}) {_format_play(p)}")
            if len(candidates) > 10:
                print(f"  ... {len(candidates) - 10} more in this list")
            s = input("Pick play # (Enter=AI, A=all plays): ").strip().lower()
            if s == "":
                ai = pick_offensive_play(pb, situation, offense_team=off_team)
                return ai if ai is not None else game.get_ai_play_call()
            if s == "a":
                candidates = list(pb.offensive_plays)
                continue
            if s.isdigit():
                n = int(s)
                if 1 <= n <= len(show):
                    return show[n - 1]
            print("  Invalid choice.")

    def prompt_defense_play(off_team, def_team, pb):
        from systems import play_caller as pc

        situation = build_situation_from_game(game, offense_team=off_team, defense_team=def_team)
        suggested_cat = pc._situation_to_defensive_category(situation)  # type: ignore
        candidates = pb.get_defensive_plays_by_category(suggested_cat)
        if not candidates:
            candidates = list(pb.defensive_plays)

        while True:
            print(f"\nDefense ({def_team.name}) — Suggested: {suggested_cat.value}")
            show = candidates[:10]
            for i, p in enumerate(show, 1):
                print(f"  {i}) {_format_play(p)}")
            if len(candidates) > 10:
                print(f"  ... {len(candidates) - 10} more in this list")
            s = input("Pick play # (Enter=AI, A=all plays): ").strip().lower()
            if s == "":
                ai = pick_defensive_play(pb, situation, defense_team=def_team)
                return ai if ai is not None else game.get_ai_defense_call()
            if s == "a":
                candidates = list(pb.defensive_plays)
                continue
            if s.isdigit():
                n = int(s)
                if 1 <= n <= len(show):
                    return show[n - 1]
            print("  Invalid choice.")

    while not game.is_game_over():
        sync_game_ratings(game, home_ratings, away_ratings, home_turnover, away_turnover)

        if game.ot_2pt_mode:
            result = game.run_play_2pt_shootout()
            game.advance_quarter()
            time.sleep(0.01)
            continue

        offense_team = home_team if game.possession == "home" else away_team
        defense_team = away_team if game.possession == "home" else home_team

        skip_fourth_auto = human_controls_offense and offense_team.name == human_team_name
        if game.down == 4 and not getattr(game, "is_overtime", False) and not skip_fourth_auto:
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

        # Offense
        if human_controls_offense and offense_team.name == human_team_name:
            pb = home_playbook if offense_team is home_team else away_playbook
            offense_call = prompt_offense_play(offense_team, defense_team, pb)
        else:
            situation = build_situation_from_game(game, offense_team=offense_team, defense_team=defense_team)
            pb = home_playbook if offense_team is home_team else away_playbook
            offense_call = pick_offensive_play(pb, situation, offense_team=offense_team) or game.get_ai_play_call()

        # Defense
        if human_controls_defense and defense_team.name == human_team_name:
            pb = home_playbook if defense_team is home_team else away_playbook
            defense_call = prompt_defense_play(offense_team, defense_team, pb)
        else:
            situation = build_situation_from_game(game, offense_team=offense_team, defense_team=defense_team)
            pb = home_playbook if defense_team is home_team else away_playbook
            defense_call = pick_defensive_play(pb, situation, defense_team=defense_team) or game.get_ai_defense_call()

        result = game.run_play(offense_call, defense_call, offense_team=offense_team, defense_team=defense_team)

        if result.get("needs_pat"):
            game.attempt_extra_point_kick(defense_pat_choice="return")
            game.finish_pat_and_kickoff()
            time.sleep(0.01)
            continue

        if result.get("needs_2pt"):
            game.attempt_two_point(offense_call, defense_call)
            game.setup_ot_possession()
            game.check_ot_period_end()
            time.sleep(0.01)
            continue

        if result.get("ot_possession_ended"):
            game.check_ot_period_end()

        game.advance_quarter()
        time.sleep(0.01)

    if verbose:
        game.end_game_summary()
        print(f"\nFINAL: {home_team.name} {game.score_home} - {away_team.name} {game.score_away}")

    return {
        "home_score": game.score_home,
        "away_score": game.score_away,
        "home_team": home_team.name,
        "away_team": away_team.name,
        "ot_winner": game.ot_winner,
    }


def main():
    """Create two teams, generate rosters, play one game."""
    # Team 1
    home = Team(
        name="Independence Patriots",
        prestige=8,
        community_type=CommunityType.BLUE_COLLAR,
        culture_grade=9,
        enrollment=1200,
        classification="4A",
    )
    generate_team_roster(home, two_way_chance=0.55)

    # Team 2
    away = Team(
        name="MT View Knights",
        prestige=5,
        community_type=CommunityType.RURAL,
        culture_grade=7,
        enrollment=600,
        classification="3A",
    )
    generate_team_roster(away, two_way_chance=0.55)

    assign_coaches_to_teams([home, away])

    result = play_single_game(home, away, verbose=True)
    return result


if __name__ == "__main__":
    main()
