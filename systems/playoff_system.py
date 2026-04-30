"""
Basic 4-team playoff: seed by wins then point differential.
Semifinals: 1v4, 2v3. Winners meet in championship.
Player game stats are tracked and appended to output when output_lines is provided.
"""

import time
from typing import Any, Dict, List, Optional, Tuple

from engine.game_engine import Game
from systems.team_ratings import calculate_team_ratings
from systems.depth_chart import build_depth_chart
from systems.game_stats import create_game_stats, record_play, format_game_box_score, merge_game_stats_into_season


def run_next_playoff_round_8(
    teams: Dict[str, Any],
    standings: Dict[str, Dict[str, Any]],
    seeded_names: List[str],
    bracket_results: List[Dict[str, Any]],
    season_player_stats: Optional[Dict[int, Any]] = None,
    output_lines: Optional[List[str]] = None,
) -> Tuple[Optional[str], bool]:
    """
    Run the next *round* of an 8-team bracket (all QF games, then both SF games, then championship).
    Mutates standings and bracket_results in place.
    seeded_names: eight team names in seed order 1..8.
    Returns (champion_name_or_none, playoffs_fully_complete).
    """
    append = output_lines.append if output_lines is not None else lambda x: None
    # Keep regular-season standings/rankings stable while playoffs are in progress.
    update_standings = False
    if len(seeded_names) != 8:
        raise ValueError("8-team playoff requires exactly 8 seeded teams")

    def _same_matchup(rh: Any, ra: Any, team_a: str, team_b: str) -> bool:
        """True if this row is the two teams (order may differ — coach-played games follow game home/away)."""
        h, a = str(rh or ""), str(ra or "")
        return (h == team_a and a == team_b) or (h == team_b and a == team_a)

    names = list(seeded_names)
    qf = [r for r in bracket_results if r.get("round") == "Quarterfinal"]
    sf = [r for r in bracket_results if r.get("round") == "Semifinal"]
    ch = [r for r in bracket_results if r.get("round") == "Championship"]

    if ch:
        w = str(ch[0].get("winner") or "")
        return (w, True)

    def _apply_game(hn: str, an: str, round_name: str) -> str:
        h, a = teams[hn], teams[an]
        sh, sa, ot, st = run_playoff_game(h, a)
        winner = hn if (ot == "home" or sh > sa) else an
        loser = an if winner == hn else hn
        if season_player_stats is not None:
            merge_game_stats_into_season(season_player_stats, st)
        final_line = f"FINAL: {hn} {sh} - {an} {sa}{' (OT)' if ot else ''}"
        box_lines = [final_line] + format_game_box_score(st, hn, an)
        box_score_text = "\n".join([ln for ln in box_lines if ln is not None]).strip()
        game_log_text = "No detailed play log is recorded for AI-simulated playoff games yet."
        if update_standings:
            standings[hn]["points_for"] += sh
            standings[hn]["points_against"] += sa
            standings[an]["points_for"] += sa
            standings[an]["points_against"] += sh
            standings[winner]["wins"] += 1
            standings[loser]["losses"] += 1
        bracket_results.append(
            {
                "round": round_name,
                "home": hn,
                "away": an,
                "home_score": sh,
                "away_score": sa,
                "winner": winner,
                "box_score_text": box_score_text,
                "game_log_text": game_log_text,
            }
        )
        return winner

    # Standard 8-team pairings (seed index 0 = 1-seed … index 7 = 8-seed).
    qf_pairs = [(0, 7), (1, 6), (2, 5), (3, 4)]
    sf_slot_pairs = [(0, 3), (1, 2)]  # winners from QF slots → SF1, SF2

    if len(qf) < 4:
        if len(qf) == 0:
            append("")
            append("PLAYOFFS — Quarterfinals")
            append("-" * 50)
        # Coach-played QFs can be recorded in any order; only sim *missing* pairings.
        for hi, ai in qf_pairs:
            hn, an = names[hi], names[ai]
            qf_now = [r for r in bracket_results if r.get("round") == "Quarterfinal"]
            if any(_same_matchup(r.get("home"), r.get("away"), hn, an) for r in qf_now):
                continue
            append(f"Quarterfinal: {hn} vs {an}")
            _apply_game(hn, an, "Quarterfinal")
        return (None, False)

    qf_now = [r for r in bracket_results if r.get("round") == "Quarterfinal"]
    if len(qf_now) != 4:
        raise ValueError("Invalid bracket: expected exactly 4 quarterfinal results")
    winners: List[str] = []
    for hi, ai in qf_pairs:
        hn, an = names[hi], names[ai]
        found = next((r for r in qf_now if _same_matchup(r.get("home"), r.get("away"), hn, an)), None)
        if not found:
            raise ValueError("Invalid bracket: missing quarterfinal for a seeded pairing")
        winners.append(str(found["winner"]))

    if len(sf) < 2:
        if len(sf) == 0:
            append("")
            append("SEMIFINALS")
            append("-" * 50)
        for wi, wj in sf_slot_pairs:
            wh, wa = winners[wi], winners[wj]
            sf_now = [r for r in bracket_results if r.get("round") == "Semifinal"]
            if any(_same_matchup(r.get("home"), r.get("away"), wh, wa) for r in sf_now):
                continue
            append(f"Semifinal: {wh} vs {wa}")
            _apply_game(wh, wa, "Semifinal")
        return (None, False)

    sf_now = [r for r in bracket_results if r.get("round") == "Semifinal"]
    if len(sf_now) != 2:
        raise ValueError("Invalid bracket: expected exactly 2 semifinal results")
    sf1_h, sf1_a = winners[0], winners[3]
    sf2_h, sf2_a = winners[1], winners[2]
    g1 = next((r for r in sf_now if _same_matchup(r.get("home"), r.get("away"), sf1_h, sf1_a)), None)
    g2 = next((r for r in sf_now if _same_matchup(r.get("home"), r.get("away"), sf2_h, sf2_a)), None)
    if not g1 or not g2:
        raise ValueError("Invalid bracket: semifinal results do not match quarterfinal winners")

    if len(ch) == 0:
        append("")
        append("CHAMPIONSHIP")
        append("-" * 50)
        wh_ch = str(g1["winner"])
        wa_ch = str(g2["winner"])
        champion = _apply_game(wh_ch, wa_ch, "Championship")
        append(f"CHAMPION: {champion}")
        return (champion, True)

    raise RuntimeError("playoff bracket in inconsistent state")

# Avoid circular import; sync is used at runtime
def _sync_game_ratings(game: Game, home_ratings: dict, away_ratings: dict) -> None:
    if game.possession == "home":
        game.offense_rating = home_ratings["offense"]
        game.defense_rating = away_ratings["defense"]
        game.run_rating = home_ratings["run"]
        game.pass_rating = home_ratings["pass"]
    else:
        game.offense_rating = away_ratings["offense"]
        game.defense_rating = home_ratings["defense"]
        game.run_rating = away_ratings["run"]
        game.pass_rating = away_ratings["pass"]


def seed_teams(
    team_names: List[str],
    standings: Dict[str, Dict[str, Any]],
    top_n: int = 8,
) -> List[Tuple[int, str]]:
    """
    Sort teams by wins (desc), then point differential (desc).
    Standings must have wins, losses, points_for, points_against per team.
    Returns [(seed, team_name), ...] with seed 1 through top_n.
    """
    def point_diff(name: str) -> int:
        s = standings.get(name, {})
        return (s.get("points_for", 0) - s.get("points_against", 0))

    sorted_names = sorted(
        team_names,
        key=lambda n: (-standings[n]["wins"], -point_diff(n)),
    )
    return [(i + 1, name) for i, name in enumerate(sorted_names[:top_n])]


def run_playoff_game(
    home_team: Any,
    away_team: Any,
    verbose: bool = False,
) -> Tuple[int, int, Optional[str], Dict[int, Any]]:
    """
    Run one playoff game. Returns (score_home, score_away, ot_winner, stats_map).
    ot_winner is "home" or "away" or None. stats_map is for player game stats.
    """
    home_ratings = calculate_team_ratings(home_team)
    away_ratings = calculate_team_ratings(away_team)

    stats_map, home_dc, away_dc = create_game_stats(home_team, away_team)

    game = Game(
        offense_rating=home_ratings["offense"],
        defense_rating=away_ratings["defense"],
        run_rating=home_ratings["run"],
        pass_rating=home_ratings["pass"],
    )
    game.home_team_name = home_team.name
    game.away_team_name = away_team.name
    _sync_game_ratings(game, home_ratings, away_ratings)
    game.apply_opening_kickoff()

    while not game.is_game_over():
        _sync_game_ratings(game, home_ratings, away_ratings)

        if game.ot_2pt_mode:
            game.run_play_2pt_shootout()
            game.advance_quarter()
            time.sleep(0.01)
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
                time.sleep(0.01)
                continue

        offense_call = game.get_ai_play_call()
        defense_call = game.get_ai_defense_call()
        possession_side = game.possession
        off_obj = home_team if game.possession == "home" else away_team
        def_obj = away_team if game.possession == "home" else home_team
        result = game.run_play(offense_call, defense_call, offense_team=off_obj, defense_team=def_obj)

        record_play(stats_map, home_team, away_team, home_dc, away_dc, possession_side, offense_call, result)

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

    return (game.score_home, game.score_away, game.ot_winner, stats_map)


def run_playoff(
    teams: Dict[str, Any],
    standings: Dict[str, Dict[str, Any]],
    team_names: List[str],
    output_lines: Optional[List[str]] = None,
    season_player_stats: Optional[Dict[int, Any]] = None,
    num_teams: int = 8,
) -> Tuple[str, List[Dict[str, Any]]]:
    """
    Run playoff. Supports 4-team (1v4, 2v3) or 8-team (1v8, 2v7, 3v6, 4v5).
    Expects standings to have wins, losses, points_for, points_against per team.
    Updates standings. Returns (champion_name, bracket_results).
    """
    append = output_lines.append if output_lines is not None else lambda x: None
    # Keep regular-season standings/rankings stable while playoffs are in progress.
    update_standings = False
    num_teams = min(num_teams, 8)
    if num_teams not in (4, 8):
        num_teams = 4

    seeded = seed_teams(team_names, standings, top_n=num_teams)
    if len(seeded) < num_teams:
        append(f"Playoff: Not enough teams (need {num_teams}).")
        return (seeded[0][1] if seeded else "", [])

    names = [name for _, name in seeded]
    bracket_results: List[Dict[str, Any]] = []

    if num_teams == 4:
        # 1v4, 2v3 → championship
        append("")
        append("PLAYOFFS (1v4, 2v3)")
        append("-" * 50)
        append(f"Seeds: 1 {names[0]} | 2 {names[1]} | 3 {names[2]} | 4 {names[3]}")
        append("")

        h1, a1 = teams[names[0]], teams[names[3]]
        score1, score2, ot1, st1 = run_playoff_game(h1, a1)
        w1 = names[0] if (ot1 == "home" or score1 > score2) else names[3]
        l1 = names[3] if w1 == names[0] else names[0]
        append(f"Semifinal: {names[0]} {score1} - {names[3]} {score2}  (Winner: {w1})")
        if season_player_stats is not None:
            merge_game_stats_into_season(season_player_stats, st1)
        if update_standings:
            standings[names[0]]["points_for"] += score1
            standings[names[0]]["points_against"] += score2
            standings[names[3]]["points_for"] += score2
            standings[names[3]]["points_against"] += score1
            standings[w1]["wins"] += 1
            standings[l1]["losses"] += 1
        bracket_results.append({"round": "Semifinal", "home": names[0], "away": names[3], "home_score": score1, "away_score": score2, "winner": w1})

        h2, a2 = teams[names[1]], teams[names[2]]
        score3, score4, ot2, st2 = run_playoff_game(h2, a2)
        w2 = names[1] if (ot2 == "home" or score3 > score4) else names[2]
        l2 = names[2] if w2 == names[1] else names[1]
        append(f"Semifinal: {names[1]} {score3} - {names[2]} {score4}  (Winner: {w2})")
        if season_player_stats is not None:
            merge_game_stats_into_season(season_player_stats, st2)
        if update_standings:
            standings[names[1]]["points_for"] += score3
            standings[names[1]]["points_against"] += score4
            standings[names[2]]["points_for"] += score4
            standings[names[2]]["points_against"] += score3
            standings[w2]["wins"] += 1
            standings[l2]["losses"] += 1
        bracket_results.append({"round": "Semifinal", "home": names[1], "away": names[2], "home_score": score3, "away_score": score4, "winner": w2})

        champ_home_name = w1
        champ_away_name = w2
    else:
        # 8-team: 1v8, 2v7, 3v6, 4v5 → semis → championship
        append("")
        append("PLAYOFFS (8-team: 1v8, 2v7, 3v6, 4v5)")
        append("-" * 50)
        append(f"Seeds: " + " | ".join(f"{i+1} {n}" for i, n in enumerate(names)))
        append("")

        qf = [(0, 7), (1, 6), (2, 5), (3, 4)]
        winners = []
        for i, (hi, ai) in enumerate(qf):
            hn, an = names[hi], names[ai]
            h, a = teams[hn], teams[an]
            sh, sa, ot, st = run_playoff_game(h, a)
            w = hn if (ot == "home" or sh > sa) else an
            l = an if w == hn else hn
            append(f"Quarterfinal: {hn} {sh} - {an} {sa}  (Winner: {w})")
            if season_player_stats is not None:
                merge_game_stats_into_season(season_player_stats, st)
            if update_standings:
                standings[hn]["points_for"] += sh
                standings[hn]["points_against"] += sa
                standings[an]["points_for"] += sa
                standings[an]["points_against"] += sh
                standings[w]["wins"] += 1
                standings[l]["losses"] += 1
            bracket_results.append({"round": "Quarterfinal", "home": hn, "away": an, "home_score": sh, "away_score": sa, "winner": w})
            winners.append(w)

        append("")
        append("SEMIFINALS")
        append("-" * 50)
        # Semi: W1v8 vs W4v5, W2v7 vs W3v6
        sf = [(0, 3), (1, 2)]
        semi_winners = []
        for i, (wi, wj) in enumerate(sf):
            wh, wa = winners[wi], winners[wj]
            h, a = teams[wh], teams[wa]
            sh, sa, ot, st = run_playoff_game(h, a)
            w = wh if (ot == "home" or sh > sa) else wa
            l = wa if w == wh else wh
            append(f"Semifinal: {wh} {sh} - {wa} {sa}  (Winner: {w})")
            if season_player_stats is not None:
                merge_game_stats_into_season(season_player_stats, st)
            if update_standings:
                standings[wh]["points_for"] += sh
                standings[wh]["points_against"] += sa
                standings[wa]["points_for"] += sa
                standings[wa]["points_against"] += sh
                standings[w]["wins"] += 1
                standings[l]["losses"] += 1
            bracket_results.append({"round": "Semifinal", "home": wh, "away": wa, "home_score": sh, "away_score": sa, "winner": w})
            semi_winners.append(w)

        champ_home_name = semi_winners[0]
        champ_away_name = semi_winners[1]

    append("")
    append("CHAMPIONSHIP")
    append("-" * 50)
    champ_home = teams[champ_home_name]
    champ_away = teams[champ_away_name]
    score_ch, score_ca, otc, stats_champ = run_playoff_game(champ_home, champ_away)
    champion = champ_home_name if (otc == "home" or score_ch > score_ca) else champ_away_name
    runner_up = champ_away_name if champion == champ_home_name else champ_home_name
    append(f"Championship: {champ_home_name} {score_ch} - {champ_away_name} {score_ca}")
    append(f"CHAMPION: {champion}")
    if season_player_stats is not None:
        merge_game_stats_into_season(season_player_stats, stats_champ)
    if update_standings:
        standings[champ_home_name]["points_for"] += score_ch
        standings[champ_home_name]["points_against"] += score_ca
        standings[champ_away_name]["points_for"] += score_ca
        standings[champ_away_name]["points_against"] += score_ch
        standings[champion]["wins"] += 1
        standings[runner_up]["losses"] += 1
    bracket_results.append({"round": "Championship", "home": champ_home_name, "away": champ_away_name, "home_score": score_ch, "away_score": score_ca, "winner": champion})

    return (champion, bracket_results)
