"""
Power-of-two single-elimination playoff bracket.

Supports any bracket size that is a power of 2 (4, 8, 16, 32, ...). Seeding
is by wins then point differential; round pairings always pair slot ``i``
with slot ``N-1-i`` so the highest seed remaining is matched with the
lowest seed remaining (standard fixed bracket — same shape as a typical
state high-school football bracket).

Round names are derived algorithmically from the bracket size:
    4   -> Semifinal -> Championship
    8   -> Quarterfinal -> Semifinal -> Championship
    16  -> Round of 16 -> Quarterfinal -> Semifinal -> Championship
    32  -> Round of 32 -> Round of 16 -> Quarterfinal -> Semifinal -> Championship

Player game stats are tracked and appended to output when output_lines is provided.
"""

import random
from typing import Any, Dict, List, Optional, Tuple

from engine.game_engine import Game
from systems.team_ratings import calculate_team_ratings
from systems.depth_chart import build_depth_chart
from systems.game_stats import create_game_stats, record_play, format_game_box_score, merge_game_stats_into_season
from systems.program_progression import (
    apply_program_delta_to_team,
    game_progression_delta,
    team_composite_strength,
)


# ---------------------------------------------------------------------------
# Bracket-shape helpers (size-agnostic)
# ---------------------------------------------------------------------------


def _is_power_of_two(n: int) -> bool:
    return n >= 2 and (n & (n - 1)) == 0


def round_name_for_size(num_slots_in_round: int) -> str:
    """Round name for a round that contains ``num_slots_in_round`` teams.

    A round with 2 teams is the Championship; 4 -> Semifinal; 8 -> Quarterfinal;
    16+ -> "Round of N".  Used to produce stable strings stored on
    ``bracket_results[*]['round']``.
    """
    if num_slots_in_round == 2:
        return "Championship"
    if num_slots_in_round == 4:
        return "Semifinal"
    if num_slots_in_round == 8:
        return "Quarterfinal"
    return f"Round of {int(num_slots_in_round)}"


def round_names_for_bracket(bracket_size: int) -> List[str]:
    """Ordered round names from first round to championship for ``bracket_size``."""
    if not _is_power_of_two(bracket_size):
        raise ValueError(f"bracket_size must be a power of 2 >= 2, got {bracket_size}")
    out: List[str] = []
    n = int(bracket_size)
    while n >= 2:
        out.append(round_name_for_size(n))
        n //= 2
    return out


def round_pairings_for_size(num_slots: int) -> List[Tuple[int, int]]:
    """Standard fixed-bracket pairings: slot ``i`` plays slot ``num_slots - 1 - i``.

    Used identically for the first round (with seeded names) and for every
    subsequent round (with the prior round's winners), which is why the
    fixed-bracket structure cleanly recurses.
    """
    if not _is_power_of_two(num_slots):
        raise ValueError(f"num_slots must be a power of 2 >= 2, got {num_slots}")
    return [(i, num_slots - 1 - i) for i in range(num_slots // 2)]


def next_playoff_round_name(
    bracket_results: List[Dict[str, Any]],
    bracket_size: int,
) -> str:
    """Round label for the next game to be added to ``bracket_results``.

    Walks the round name list and returns the first round whose recorded
    game count is below the round's required pair count.  Used by the
    coach-played path to label a freshly-finished game without having to
    pass ``round_name`` in from the caller.
    """
    if not isinstance(bracket_results, list):
        bracket_results = []
    names = round_names_for_bracket(bracket_size)
    remaining = int(bracket_size)
    for name in names:
        needed = remaining // 2
        played = sum(1 for r in bracket_results if isinstance(r, dict) and r.get("round") == name)
        if played < needed:
            return name
        remaining = needed
    return names[-1]


# Stable round-priority map for "this team's furthest round reached" labels.
# Higher value = deeper run.  Includes future power-of-two sizes (so the same
# table can grade brackets that go all the way down to a Round of 64+) and
# the regional bracket rounds.
#
# Regional layering rationale (priority = "rounds remaining until the
# championship", which is the same across both regional systems):
#   "Regional Quarterfinal" sits next to "Round of 32" — losing here means
#   four rounds remain (Reg SF, Reg Final, Semifinal, Championship); only
#   produced by the 8-per-region system.
#   "Regional Semifinal" sits next to "Round of 16" — three rounds remain.
#   "Regional Final" sits next to "Quarterfinal" — winning means you're
#   one of the regional champions left (two rounds remain).
#   "Semifinal" / "Championship" line up across all systems.
PLAYOFF_ROUND_PRIORITY: Dict[str, int] = {
    "Round of 64": 1,
    "Round of 32": 2,
    "Regional Quarterfinal": 2,
    "Round of 16": 3,
    "Regional Semifinal": 3,
    "Quarterfinal": 4,
    "Regional Final": 4,
    "Semifinal": 5,
    "Championship": 6,
}


def _same_matchup(rh: Any, ra: Any, team_a: str, team_b: str) -> bool:
    """True if a bracket row is the same two teams (order may differ for
    coach-played games which follow the engine home/away)."""
    h, a = str(rh or ""), str(ra or "")
    return (h == team_a and a == team_b) or (h == team_b and a == team_a)


def run_next_playoff_round(
    teams: Dict[str, Any],
    standings: Dict[str, Dict[str, Any]],
    seeded_names: List[str],
    bracket_results: List[Dict[str, Any]],
    season_player_stats: Optional[Dict[int, Any]] = None,
    output_lines: Optional[List[str]] = None,
) -> Tuple[Optional[str], bool]:
    """
    Run the next *incomplete* round of a single-elimination bracket of any
    power-of-two size (4 / 8 / 16 / ...).  Mutates ``standings`` and
    ``bracket_results`` in place.

    ``seeded_names`` must be the bracket-size team names in seed order 1..N.
    Returns ``(champion_name_or_none, playoffs_fully_complete)``.

    The function inspects already-recorded games per round and only sims the
    games that are missing — so user-played games can be interleaved with
    AI-simulated games without losing or duplicating bracket entries.
    """
    append = output_lines.append if output_lines is not None else (lambda x: None)
    update_standings = False  # Standings stay frozen during the postseason.

    bracket_size = len(seeded_names)
    if not _is_power_of_two(bracket_size):
        raise ValueError(
            f"playoff bracket size must be a power of 2 >= 2, got {bracket_size}"
        )
    round_names = round_names_for_bracket(bracket_size)

    # Final round already played -> we're done.
    final_results = [r for r in bracket_results if r.get("round") == round_names[-1]]
    if final_results:
        return (str(final_results[0].get("winner") or ""), True)

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

    # Walk rounds first-to-last. Each round's "current_slots" is built from
    # the prior round's recorded winners (in slot/seed order).
    current_slots: List[str] = list(seeded_names)
    for round_idx, round_name in enumerate(round_names):
        pairings = round_pairings_for_size(len(current_slots))
        recorded_this_round = [r for r in bracket_results if r.get("round") == round_name]

        if len(recorded_this_round) < len(pairings):
            # Heading is only printed at the start of a round.
            if len(recorded_this_round) == 0:
                heading = "CHAMPIONSHIP" if round_name == "Championship" else f"PLAYOFFS — {round_name}s"
                append("")
                append(heading)
                append("-" * 50)
            for hi, ai in pairings:
                hn, an = current_slots[hi], current_slots[ai]
                already = [r for r in bracket_results if r.get("round") == round_name]
                if any(_same_matchup(r.get("home"), r.get("away"), hn, an) for r in already):
                    continue
                if round_name == "Championship":
                    append(f"Championship: {hn} vs {an}")
                else:
                    append(f"{round_name}: {hn} vs {an}")
                champ_or_winner = _apply_game(hn, an, round_name)
                if round_name == "Championship":
                    append(f"CHAMPION: {champ_or_winner}")
            if round_name == "Championship":
                champ_row = next(
                    (r for r in bracket_results if r.get("round") == "Championship"),
                    None,
                )
                return (str(champ_row.get("winner")) if champ_row else None, True)
            return (None, False)

        # Round fully recorded: collect winners in slot order to feed the next round.
        winners_this_round: List[str] = []
        for hi, ai in pairings:
            hn, an = current_slots[hi], current_slots[ai]
            found = next(
                (r for r in recorded_this_round
                 if _same_matchup(r.get("home"), r.get("away"), hn, an)),
                None,
            )
            if not found or not found.get("winner"):
                raise ValueError(
                    f"Invalid bracket: missing/incomplete {round_name} for {hn} vs {an}"
                )
            winners_this_round.append(str(found["winner"]))
        current_slots = winners_this_round

    # If we reach here every round is full and the championship is recorded.
    champ_row = next(
        (r for r in bracket_results if r.get("round") == round_names[-1]),
        None,
    )
    return (str(champ_row.get("winner")) if champ_row else None, True)


def run_next_playoff_round_8(
    teams: Dict[str, Any],
    standings: Dict[str, Dict[str, Any]],
    seeded_names: List[str],
    bracket_results: List[Dict[str, Any]],
    season_player_stats: Optional[Dict[int, Any]] = None,
    output_lines: Optional[List[str]] = None,
) -> Tuple[Optional[str], bool]:
    """
    Backwards-compatible wrapper around :func:`run_next_playoff_round` that
    enforces the historical "8-team only" contract.  Prefer the generic
    function for new callers; this name is kept so existing imports keep
    working unchanged.
    """
    if len(seeded_names) != 8:
        raise ValueError("8-team playoff requires exactly 8 seeded teams")
    return run_next_playoff_round(
        teams,
        standings,
        seeded_names,
        bracket_results,
        season_player_stats,
        output_lines,
    )

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


def _ranking_key(standings: Dict[str, Dict[str, Any]], name: str) -> Tuple[int, int]:
    """Standard playoff seeding key: (-wins, -point_differential).

    Lower is better; pass directly to ``sorted(..., key=lambda n: _ranking_key(...))``.
    Used by both ``seed_teams`` and the regional bracket runner so a single
    "what does ranking mean" rule lives in one place.
    """
    s = standings.get(name, {})
    return (
        -int(s.get("wins", 0)),
        -(int(s.get("points_for", 0)) - int(s.get("points_against", 0))),
    )


# Suffixes used for in-region round labels.  The 4-per-region system uses
# only the last two ("Regional Semifinal", "Regional Final"); 8-per-region
# adds "Regional Quarterfinal" in front; 16-per-region would add
# "Regional Round of 16", and so on.  Round names are derived dynamically
# in :func:`regional_in_region_round_names` so the same runner handles every
# bracket size.
REGIONAL_STATE_ROUND_NAMES: Tuple[str, ...] = ("Semifinal", "Championship")


def _regional_round_name_for_size(num_teams_in_round: int) -> str:
    """In-region round label for a round that contains this many teams.

    ``2 -> "Regional Final"``, ``4 -> "Regional Semifinal"``,
    ``8 -> "Regional Quarterfinal"``, larger sizes fall back to
    ``"Regional Round of N"``.
    """
    if num_teams_in_round == 2:
        return "Regional Final"
    if num_teams_in_round == 4:
        return "Regional Semifinal"
    if num_teams_in_round == 8:
        return "Regional Quarterfinal"
    return f"Regional Round of {int(num_teams_in_round)}"


def regional_in_region_round_names(teams_per_region: int) -> List[str]:
    """Ordered in-region round names from first round to regional final.

    Examples:
        teams_per_region=4  -> ["Regional Semifinal", "Regional Final"]
        teams_per_region=8  -> ["Regional Quarterfinal", "Regional Semifinal", "Regional Final"]
        teams_per_region=16 -> ["Regional Round of 16", "Regional Quarterfinal", ...]
    """
    if teams_per_region < 2 or (teams_per_region & (teams_per_region - 1)):
        raise ValueError(
            f"teams_per_region must be a power of 2 >= 2, got {teams_per_region}"
        )
    out: List[str] = []
    n = int(teams_per_region)
    while n >= 2:
        out.append(_regional_round_name_for_size(n))
        n //= 2
    return out


def regional_full_round_names(teams_per_region: int) -> List[str]:
    """Full round-name sequence for a regional bracket: in-region rounds
    followed by the state ``Semifinal`` and ``Championship``."""
    return regional_in_region_round_names(teams_per_region) + list(REGIONAL_STATE_ROUND_NAMES)


# Backwards-compat alias: the original 4-per-region constant (kept so any
# external import still works after the runner generalisation).
REGIONAL_ROUND_NAMES: Tuple[str, ...] = tuple(regional_full_round_names(4))


def _standard_in_region_seed_layout(top_seeds: List[Any]) -> List[Any]:
    """Arrange the top-N seeds of one region for adjacent-pair bracket play.

    Uses the standard tournament-bracket recursion so that pairing slots
    ``(0,1)``, ``(2,3)``, ... at every round produces the correct standard
    bracket matchups.

    Layouts:
        N=2  -> [s1, s2]
        N=4  -> [s1, s4, s2, s3]
        N=8  -> [s1, s8, s4, s5, s2, s7, s3, s6]
        N=16 -> [s1, s16, s8, s9, s4, s13, s5, s12, s2, s15, s7, s10,
                 s3, s14, s6, s11]

    With this layout, R1 plays the standard first-round pairings (1v8,
    4v5, 2v7, 3v6 for N=8); R2 plays the standard SF pairings (the 1/8
    winner vs the 4/5 winner, etc.); R3 is the regional final.
    """
    n = len(top_seeds)
    if n == 1:
        return list(top_seeds)
    if n == 2:
        return list(top_seeds)
    if n & (n - 1):
        raise ValueError(f"region size must be a power of 2, got {n}")
    # Build seed *positions* (1-indexed) recursively, then materialise.
    def seed_positions(size: int) -> List[int]:
        if size == 1:
            return [1]
        half = seed_positions(size // 2)
        out: List[int] = []
        for s in half:
            out.append(s)
            out.append(size + 1 - s)
        return out

    positions = seed_positions(n)  # e.g. [1, 8, 4, 5, 2, 7, 3, 6] for n=8
    return [top_seeds[p - 1] for p in positions]


def seed_teams_regional(
    teams_by_region: Dict[str, List[str]],
    standings: Dict[str, Dict[str, Any]],
    teams_per_region: int = 4,
) -> List[Dict[str, Any]]:
    """Seed a regional playoff pool: top N from each region, arranged for
    adjacent-pair bracket play.

    Within each region the top ``teams_per_region`` teams are sorted by
    wins/PD. They are then arranged in slot order so that
    pairing slots ``(0,1)`` and ``(2,3)`` produces the 1v4 / 2v3 matchups —
    e.g. for ``teams_per_region == 4`` the layout per region is
    ``[s1, s4, s2, s3]``.  Regions are concatenated in alphabetical order
    so the slot list is deterministic.

    Returns a list of dicts ordered by overall slot (1..bracket_size):

        [{"seed": 1, "team": "...", "region": "North", "region_seed": 1},
         {"seed": 2, "team": "...", "region": "North", "region_seed": 4},
         ...]

    A region is silently skipped if it does not have at least
    ``teams_per_region`` teams; the caller should verify the resulting list
    is the expected size before starting the bracket.
    """
    if teams_per_region < 2 or (teams_per_region & (teams_per_region - 1)):
        raise ValueError(
            f"teams_per_region must be a power of 2 >= 2, got {teams_per_region}"
        )

    seeds: List[Dict[str, Any]] = []
    overall_slot = 1
    # Sort regions for stable, reproducible bracket layout across runs.
    for region_name in sorted(teams_by_region.keys()):
        pool = list(teams_by_region.get(region_name) or [])
        if len(pool) < teams_per_region:
            continue
        # Rank within the region using the same rule as the global seed_teams.
        ranked = sorted(pool, key=lambda n: _ranking_key(standings, n))
        top = ranked[:teams_per_region]
        # Standard bracket layout: each adjacent pair across every round
        # produces the correct standard matchup (1v4 / 2v3 for 4-team
        # regions; 1v8 / 4v5 / 2v7 / 3v6 for 8-team regions; etc.).
        arranged = _standard_in_region_seed_layout(top)
        # Re-derive the team's *display* region seed (1..N) from the team's
        # rank within ``ranked``, so the UI shows "1 seed" for the
        # highest-ranked team in each region regardless of slot order.
        seed_of: Dict[str, int] = {name: idx + 1 for idx, name in enumerate(top)}
        for name in arranged:
            seeds.append({
                "seed": overall_slot,
                "team": name,
                "region": region_name,
                "region_seed": seed_of[name],
            })
            overall_slot += 1
    return seeds


def _teams_per_region_from_seeds(seeded_entries: List[Dict[str, Any]]) -> int:
    """Infer ``teams_per_region`` from a regional seed list.

    All seeds carry a ``region_seed`` (1..N within their region); the max
    of those values is the per-region pool size.  Used so callers can stay
    size-agnostic (4-per-region vs 8-per-region etc.).
    """
    if not seeded_entries:
        return 0
    return max(int(e.get("region_seed", 0) or 0) for e in seeded_entries)


def _regional_expected_games_per_round(
    teams_per_region: int, num_regions: int
) -> Dict[str, int]:
    """Map ``round_name -> required games for that round`` for a regional bracket.

    In-region rounds halve the field each step; the state Semifinal pairs
    the regional champions (``num_regions / 2`` games) and the
    Championship is always 1 game.
    """
    out: Dict[str, int] = {}
    teams_in_round = int(teams_per_region)
    for name in regional_in_region_round_names(teams_per_region):
        out[name] = (teams_in_round // 2) * num_regions
        teams_in_round //= 2
    out["Semifinal"] = num_regions // 2
    out["Championship"] = 1
    return out


def _regional_state_sf_pairings(num_state_seeds: int) -> List[Tuple[int, int]]:
    """SF pairings after the state-seed re-rank: high-vs-low, middle-vs-middle.

    For 4 regional champions: ``[(0, 3), (1, 2)]``.  For larger pools
    (e.g. 8 regions) it generalises to ``[(0, N-1), (1, N-2), ...]``.
    """
    if num_state_seeds < 4:
        return [(0, 1)] if num_state_seeds == 2 else []
    return [(i, num_state_seeds - 1 - i) for i in range(num_state_seeds // 2)]


def run_next_playoff_round_regional(
    teams: Dict[str, Any],
    standings: Dict[str, Dict[str, Any]],
    seeded_entries: List[Dict[str, Any]],
    bracket_results: List[Dict[str, Any]],
    season_player_stats: Optional[Dict[int, Any]] = None,
    output_lines: Optional[List[str]] = None,
) -> Tuple[Optional[str], bool]:
    """Run the next *incomplete* round of a regional playoff bracket of any
    supported size (4-team, 8-team, 16-team, ... regions).

    Bracket structure for ``regions_per_class=R`` and ``teams_per_region=T``::

        Total bracket = R * T teams.
        In-region rounds (each region runs an independent T-team bracket):
            Round 1: T/2 games per region (R * T/2 total)
            ...
            Last in-region round: 1 game per region (R total) — Regional Final
        State Semifinal: R/2 games (re-seeded by overall wins/PD —
            highest vs lowest, middle vs middle).
        Championship: 1 game.

    Round names are derived dynamically:
        T=4  -> "Regional Semifinal" -> "Regional Final" -> "Semifinal" -> "Championship"
        T=8  -> "Regional Quarterfinal" -> "Regional Semifinal" -> "Regional Final" -> "Semifinal" -> "Championship"
        T=16 -> "Regional Round of 16" -> ... (same tail).

    ``seeded_entries`` is the slot-ordered list returned by
    :func:`seed_teams_regional`; element 0 is overall slot 1.
    """
    append = output_lines.append if output_lines is not None else (lambda x: None)

    bracket_size = len(seeded_entries)
    if bracket_size < 4 or bracket_size & (bracket_size - 1):
        raise ValueError(
            f"regional bracket size must be a power of 2 >= 4, got {bracket_size}"
        )
    teams_per_region = _teams_per_region_from_seeds(seeded_entries)
    if teams_per_region < 2 or (teams_per_region & (teams_per_region - 1)):
        raise ValueError(
            f"teams_per_region (from seeds) must be a power of 2 >= 2, got {teams_per_region}"
        )
    num_regions = bracket_size // teams_per_region
    if num_regions < 2 or (num_regions & (num_regions - 1)):
        raise ValueError(
            f"num_regions must be a power of 2 >= 2, got {num_regions}"
        )

    in_region_round_names = regional_in_region_round_names(teams_per_region)
    seeded_names = [str(e.get("team")) for e in seeded_entries]

    # Final round already played -> we're done.
    final_results = [r for r in bracket_results if r.get("round") == "Championship"]
    if final_results:
        return (str(final_results[0].get("winner") or ""), True)

    def _apply_game(hn: str, an: str, round_name: str) -> str:
        h, a = teams[hn], teams[an]
        sh, sa, ot, st = run_playoff_game(h, a)
        winner = hn if (ot == "home" or sh > sa) else an
        if season_player_stats is not None:
            merge_game_stats_into_season(season_player_stats, st)
        final_line = f"FINAL: {hn} {sh} - {an} {sa}{' (OT)' if ot else ''}"
        box_lines = [final_line] + format_game_box_score(st, hn, an)
        box_score_text = "\n".join([ln for ln in box_lines if ln is not None]).strip()
        game_log_text = "No detailed play log is recorded for AI-simulated playoff games yet."
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

    # ----- In-region rounds (adjacent-pair walking on the slot list) -----
    # ``current_slots`` always holds the teams advancing from the previous
    # round, in the same slot order they originally occupied.  Adjacent
    # pairing is correct for every round because the initial slot layout
    # came from :func:`_standard_in_region_seed_layout`.
    current_slots: List[str] = list(seeded_names)
    for round_name in in_region_round_names:
        pairs = [(i, i + 1) for i in range(0, len(current_slots), 2)]
        recorded_this_round = [r for r in bracket_results if r.get("round") == round_name]
        if len(recorded_this_round) < len(pairs):
            if len(recorded_this_round) == 0:
                append("")
                append(f"PLAYOFFS — {round_name}s")
                append("-" * 50)
            for hi, ai in pairs:
                hn, an = current_slots[hi], current_slots[ai]
                already = [r for r in bracket_results if r.get("round") == round_name]
                if any(_same_matchup(r.get("home"), r.get("away"), hn, an) for r in already):
                    continue
                append(f"{round_name}: {hn} vs {an}")
                _apply_game(hn, an, round_name)
            return (None, False)
        # Round fully recorded: collect winners in slot order for the next round.
        winners_this_round: List[str] = []
        for hi, ai in pairs:
            hn, an = current_slots[hi], current_slots[ai]
            found = next(
                (r for r in recorded_this_round
                 if _same_matchup(r.get("home"), r.get("away"), hn, an)),
                None,
            )
            if not found or not found.get("winner"):
                raise ValueError(
                    f"Invalid bracket: missing/incomplete {round_name} for {hn} vs {an}"
                )
            winners_this_round.append(str(found["winner"]))
        current_slots = winners_this_round

    # ``current_slots`` now holds the regional champions (one per region).
    regional_champions = current_slots

    # ----- State Semifinal: re-seed by overall record, pair high-vs-low / mid-vs-mid -----
    state_ranked = sorted(regional_champions, key=lambda n: _ranking_key(standings, n))
    sf_pairings = _regional_state_sf_pairings(len(state_ranked))
    sf_recorded = [r for r in bracket_results if r.get("round") == "Semifinal"]
    if len(sf_recorded) < len(sf_pairings):
        if len(sf_recorded) == 0:
            append("")
            append("PLAYOFFS — State Semifinals (re-seeded by overall record)")
            append("-" * 50)
        for hi, ai in sf_pairings:
            hn, an = state_ranked[hi], state_ranked[ai]
            already = [r for r in bracket_results if r.get("round") == "Semifinal"]
            if any(_same_matchup(r.get("home"), r.get("away"), hn, an) for r in already):
                continue
            append(f"Semifinal: {hn} vs {an}")
            _apply_game(hn, an, "Semifinal")
        return (None, False)

    sf_winners: List[str] = []
    for hi, ai in sf_pairings:
        hn, an = state_ranked[hi], state_ranked[ai]
        found = next(
            (r for r in sf_recorded if _same_matchup(r.get("home"), r.get("away"), hn, an)),
            None,
        )
        if not found or not found.get("winner"):
            raise ValueError(
                f"Invalid bracket: missing/incomplete Semifinal for {hn} vs {an}"
            )
        sf_winners.append(str(found["winner"]))

    # ----- Championship -----
    ch_recorded = [r for r in bracket_results if r.get("round") == "Championship"]
    if not ch_recorded:
        append("")
        append("CHAMPIONSHIP")
        append("-" * 50)
        wh, wa = sf_winners[0], sf_winners[1]
        append(f"Championship: {wh} vs {wa}")
        champ = _apply_game(wh, wa, "Championship")
        append(f"CHAMPION: {champ}")
        return (champ, True)

    return (str(ch_recorded[0].get("winner") or ""), True)


def next_regional_round_name(
    bracket_results: List[Dict[str, Any]],
    seeded_entries: Optional[List[Dict[str, Any]]] = None,
    *,
    teams_per_region: Optional[int] = None,
    num_regions: Optional[int] = None,
) -> str:
    """Round label for the next game to be appended to a regional bracket.

    Walks the regional round names (in-region rounds → state Semifinal →
    Championship) and returns the first one whose game count is below the
    expected number for this bracket's size.  Used by the coach-played path
    so a freshly-finished regional game can be labeled without the caller
    knowing where in the bracket they are.

    Either pass ``seeded_entries`` (the bracket's seed dicts; size info is
    inferred from them) or pass both ``teams_per_region`` and
    ``num_regions`` keyword args.  If neither is given, defaults to the
    legacy 4-per-region / 4-region layout for backwards compatibility.
    """
    if not isinstance(bracket_results, list):
        bracket_results = []
    if seeded_entries is not None and seeded_entries:
        tpr = _teams_per_region_from_seeds(seeded_entries)
        nr = max(1, len(seeded_entries) // max(1, tpr))
    elif teams_per_region is not None and num_regions is not None:
        tpr = int(teams_per_region)
        nr = int(num_regions)
    else:
        tpr = 4
        nr = 4
    expected = _regional_expected_games_per_round(tpr, nr)
    full_rounds = regional_full_round_names(tpr)
    for name in full_rounds:
        played = sum(1 for r in bracket_results if isinstance(r, dict) and r.get("round") == name)
        if played < expected.get(name, 0):
            return name
    return full_rounds[-1]


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
            if game.fourth_down_decision() in ("punt", "fg"):
                result = game.run_play()
                if isinstance(result, dict) and (result.get("first_down") is False) and (result.get("yards") == 0) and game.down != 4:
                    continue
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
            continue

        if result.get("needs_2pt"):
            game.attempt_two_point(offense_call, defense_call)
            game.setup_ot_possession()
            game.check_ot_period_end()
            continue

        if result.get("ot_possession_ended"):
            game.check_ot_period_end()

        game.advance_quarter()

    sh, sa = int(game.score_home), int(game.score_away)
    h_str = team_composite_strength(home_ratings)
    a_str = team_composite_strength(away_ratings)
    rng = random.Random()
    d_home = game_progression_delta(
        team_score=sh, opp_score=sa, team_strength=h_str, opp_strength=a_str, rng=rng
    )
    d_away = game_progression_delta(
        team_score=sa, opp_score=sh, team_strength=a_str, opp_strength=h_str, rng=rng
    )
    apply_program_delta_to_team(home_team, d_home)
    apply_program_delta_to_team(away_team, d_away)

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
    Run a full single-elimination playoff for any power-of-two bracket size
    (4 / 8 / 16 / 32 / ...). Expects ``standings`` to have wins, losses,
    points_for, points_against per team. Returns
    ``(champion_name, bracket_results)``.

    Internally this just seeds the pool and then drives
    :func:`run_next_playoff_round` until the bracket is complete, so the same
    pairing/round logic powers both the all-at-once simulator and the
    incremental coach-played path.
    """
    append = output_lines.append if output_lines is not None else (lambda x: None)

    # Normalize to a power of two (round down to the nearest valid size).
    requested = max(2, int(num_teams))
    valid_sizes = [s for s in (2, 4, 8, 16, 32, 64) if s <= requested]
    bracket_size = valid_sizes[-1] if valid_sizes else 4
    if not _is_power_of_two(bracket_size):
        bracket_size = 4

    seeded = seed_teams(team_names, standings, top_n=bracket_size)
    if len(seeded) < bracket_size:
        append(f"Playoff: Not enough teams (need {bracket_size}).")
        return (seeded[0][1] if seeded else "", [])

    names = [name for _, name in seeded]
    bracket_results: List[Dict[str, Any]] = []

    append("")
    append(f"PLAYOFFS ({bracket_size}-team bracket)")
    append("-" * 50)
    append("Seeds: " + " | ".join(f"{i + 1} {n}" for i, n in enumerate(names)))
    append("")

    # Drive the generic round runner until the championship is decided.
    # Each call plays exactly one round (all of its games), so for an
    # 8-team bracket this loops 3 times; for 16 it loops 4 times.
    champion_name: Optional[str] = None
    completed = False
    safety = bracket_size  # bound the loop in case of a bug; bracket has log2(N) rounds
    while not completed and safety > 0:
        safety -= 1
        champion_name, completed = run_next_playoff_round(
            teams,
            standings,
            names,
            bracket_results,
            season_player_stats,
            output_lines,
        )

    return (str(champion_name or ""), bracket_results)
