from game_engine import Game
import random
import time

# -------------------------
# Step 1: Define teams
# -------------------------
teams = {
    "Independence Patriots": {"offense": 80, "defense": 80, "run": 70, "pass": 60},
    "MT View Knights": {"offense": 35, "defense": 30, "run": 40, "pass": 55},
    "Bluefield Beavers": {"offense": 40, "defense": 45, "run": 55, "pass": 70},
    "Shady Spring Tigers": {"offense": 20, "defense": 55, "run": 50, "pass": 60}
}

# -------------------------
# Step 2: Schedule
# -------------------------
schedule = [
    ("Independence Patriots", "MT View Knights"),
]

random.shuffle(schedule)

# -------------------------
# Step 3: Standings
# -------------------------
standings = {team: {"wins": 0, "losses": 0} for team in teams}

# -------------------------
# Step 4: Season Stats Tracker
# -------------------------
season_stats = {
    team: {
        "rush_yards": 0,
        "pass_yards": 0,
        "touchdowns": 0,
        "turnovers": 0,
        "sacks": 0,
        "interceptions": 0,
        "fumbles": 0,
        "total_plays": 0,
        "run_plays": 0,
        "pass_plays": 0,
        "pass_attempts": 0,
        "pass_completions": 0,
        "explosive_run": 0,   # run 10+ yards
        "explosive_pass": 0,  # pass 20+ yards
        "time_of_possession": 0,  # seconds
        "third_down_attempts": 0,
        "third_down_conversions": 0,
        "fourth_down_attempts": 0,
        "fourth_down_conversions": 0,
    }
    for team in teams
}

# -------------------------
# Step 5: Simulate Season
# -------------------------
for home, away in schedule:
    home_team = teams[home]
    away_team = teams[away]

    game = Game(
        offense_rating=home_team["offense"],
        defense_rating=away_team["defense"],
        run_rating=home_team["run"],
        pass_rating=home_team["pass"]
    )

    game.home_team_name = home
    game.away_team_name = away
    game.apply_opening_kickoff()

    print(f"\nStarting Game: {home} vs {away}")

    while not game.is_game_over():

        offense_team = home if game.possession == "home" else away
        defense_team = away if game.possession == "home" else home

        # ---- NCAA OT 2-POINT SHOOTOUT (OT3+) ----
        if game.ot_2pt_mode:
            result = game.run_play_2pt_shootout()
            game.advance_quarter()
            time.sleep(0.05)
            continue

        if game.down == 4 and not getattr(game, "is_overtime", False):
            result = game.run_play()
            if isinstance(result, dict) and (result.get("first_down") is False) and (result.get("yards") == 0) and game.down != 4:
                time.sleep(0.05)
                continue

        offense_call = str(random.choice(["1", "2"]))
        defense_call = str(random.choice(["1", "2", "3"]))

        down_before = game.down
        result = game.run_play(offense_call, defense_call)

        if result.get("needs_pat"):
            game.attempt_extra_point_kick(defense_pat_choice="return")
            game.finish_pat_and_kickoff()
            time.sleep(0.05)
            continue

        # ---- OT2: 2-POINT CONVERSION AFTER TD ----
        if result.get("needs_2pt"):
            yards = result.get("yards", 0)
            season_stats[offense_team]["total_plays"] += 1
            if offense_call == "1":
                season_stats[offense_team]["run_plays"] += 1
                season_stats[offense_team]["rush_yards"] += yards
            else:
                season_stats[offense_team]["pass_plays"] += 1
                season_stats[offense_team]["pass_yards"] += yards
            season_stats[offense_team]["touchdowns"] += 1
            game.attempt_two_point(offense_call, defense_call)
            game.setup_ot_possession()
            game.check_ot_period_end()
            time.sleep(0.05)
            continue

        converted = result.get("touchdown") or result.get("first_down")

        yards = result.get("yards", 0)

        # ---- Track Plays ----
        season_stats[offense_team]["total_plays"] += 1
        if offense_call == "1":
            season_stats[offense_team]["run_plays"] += 1
            season_stats[offense_team]["rush_yards"] += yards
            if yards > 10:
                season_stats[offense_team]["explosive_run"] += 1
        else:
            season_stats[offense_team]["pass_plays"] += 1
            season_stats[offense_team]["pass_yards"] += yards
            # Pass attempts = throws (excludes sacks); completions = attempts minus INTs
            if yards > 20 and not result.get("interception"):
                season_stats[offense_team]["explosive_pass"] += 1
            if not result.get("sack"):
                season_stats[offense_team]["pass_attempts"] += 1
                if not result.get("interception") and not result.get("incomplete_pass"):
                    season_stats[offense_team]["pass_completions"] += 1

        # ---- Track Touchdowns ----
        if result.get("touchdown"):
            season_stats[offense_team]["touchdowns"] += 1

        # ---- Track 3rd/4th Down Conversions ----
        if down_before == 3:
            season_stats[offense_team]["third_down_attempts"] += 1
            if converted:
                season_stats[offense_team]["third_down_conversions"] += 1
        elif down_before == 4:
            season_stats[offense_team]["fourth_down_attempts"] += 1
            if converted:
                season_stats[offense_team]["fourth_down_conversions"] += 1

        # ---- Track Time of Possession ----
        season_stats[offense_team]["time_of_possession"] += result.get("clock_elapsed", 0)

        # ---- Track Sacks ----
        if result.get("sack"):
            season_stats[defense_team]["sacks"] += 1

        # ---- NCAA OT: Check if period ended (both teams had possession) ----
        if result.get("ot_possession_ended"):
            game.check_ot_period_end()

        game.advance_quarter()
        time.sleep(0.05)

    # ---------------------------------
    # NEW: Pull INT + FUM from engine
    # ---------------------------------
    season_stats[home]["interceptions"] += game.interceptions_home
    season_stats[away]["interceptions"] += game.interceptions_away

    season_stats[home]["fumbles"] += game.fumbles_home
    season_stats[away]["fumbles"] += game.fumbles_away

    # Turnovers = INT + FUM only (excludes turnover on downs)
    season_stats[home]["turnovers"] += game.interceptions_home + game.fumbles_home
    season_stats[away]["turnovers"] += game.interceptions_away + game.fumbles_away

    # ---------------------------------
    # End Game Summary
    # ---------------------------------
    game.end_game_summary()

    print(f"\nFinal Score: {home} {game.score_home} - {away} {game.score_away}")

    # Update standings (use ot_winner if game went to OT)
    if game.ot_winner:
        winner = home if game.ot_winner == "home" else away
        loser = away if game.ot_winner == "home" else home
        standings[winner]["wins"] += 1
        standings[loser]["losses"] += 1
    elif game.score_home > game.score_away:
        standings[home]["wins"] += 1
        standings[away]["losses"] += 1
    else:
        standings[home]["losses"] += 1
        standings[away]["wins"] += 1


# -------------------------
# Step 6: Print Final Standings
# -------------------------
print("\nFINAL SEASON STANDINGS:")
for team, record in standings.items():
    print(f"{team}: {record['wins']} - {record['losses']}")

# -------------------------
# Step 7: Print Season Stats
# -------------------------
print("\nSEASON STATS:")
for team, stats in season_stats.items():
    total_plays = stats["total_plays"]
    total_yards = stats["rush_yards"] + stats["pass_yards"]
    run_plays = stats["run_plays"]
    pass_plays = stats["pass_plays"]

    # Derived stats (avoid division by zero)
    ypp = total_yards / total_plays if total_plays else 0
    ypc_run = stats["rush_yards"] / run_plays if run_plays else 0
    ypc_pass = stats["pass_yards"] / pass_plays if pass_plays else 0
    run_pct = (run_plays / total_plays * 100) if total_plays else 0
    pass_pct = (pass_plays / total_plays * 100) if total_plays else 0
    cmp_pct = (stats["pass_completions"] / stats["pass_attempts"] * 100) if stats["pass_attempts"] else 0

    top_sec = stats["time_of_possession"]
    top_str = f"{top_sec // 60}:{top_sec % 60:02}"

    print(f"\n{team}")
    print(f"  Offense: {total_plays} plays | {total_yards} total yards | {ypp:.1f} yards/play")
    print(f"  Run: {run_plays} ({run_pct:.1f}%) | {stats['rush_yards']} yds | {ypc_run:.1f} ypc")
    print(f"  Pass: {pass_plays} ({pass_pct:.1f}%) | {stats['pass_completions']}/{stats['pass_attempts']} ({cmp_pct:.1f}%) | {stats['pass_yards']} yds | {ypc_pass:.1f} ypc")
    print(f"  Touchdowns: {stats['touchdowns']} | Turnovers: {stats['turnovers']}")
    print(f"  {stats['third_down_conversions']}/{stats['third_down_attempts']} 3rd Down | {stats['fourth_down_conversions']}/{stats['fourth_down_attempts']} 4th Down")
    print(f"  Explosives: {stats['explosive_run']} run (10+) | {stats['explosive_pass']} pass (20+)")
    print(f"  Sacks: {stats['sacks']} | INT: {stats['interceptions']} | FUM: {stats['fumbles']}")
    print(f"  Time of Possession: {top_str}")