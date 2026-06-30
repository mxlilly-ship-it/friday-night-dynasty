"""
Offseason 7-on-7 passing tournaments (sim-only, no game engine).

Format: 8 teams, two groups of 4, round-robin within group (3 games) plus one
cross-group game (4 group games per team). Top 4 by record advance to
single-elimination semifinals and a final.
"""

from __future__ import annotations

import random
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Tuple

if TYPE_CHECKING:
    from models.team import Team

TOURNAMENT_TIERS: Dict[str, Dict[str, Any]] = {
    "area": {
        "label": "Area",
        "description": "Local programs — easiest competition.",
        "prestige_lo": -5,
        "prestige_hi": 0,
        "opponent_rating_mod": -5,
    },
    "regional": {
        "label": "Regional",
        "description": "Area rivals and mid-tier programs.",
        "prestige_lo": -2,
        "prestige_hi": 3,
        "opponent_rating_mod": 0,
    },
    "state": {
        "label": "State",
        "description": "Elite statewide programs — hardest field.",
        "prestige_lo": -1,
        "prestige_hi": 8,
        "opponent_rating_mod": 5,
    },
}

VALID_TOURNAMENT_TIERS = frozenset(TOURNAMENT_TIERS.keys())


def _clamp_rating(v: float) -> int:
    return max(25, min(95, int(round(v))))


def _player_qb_score(p: Any) -> float:
    return (
        float(getattr(p, "throw_accuracy", 50))
        + float(getattr(p, "throw_power", 50))
        + float(getattr(p, "decisions", 50))
        + float(getattr(p, "speed", 50)) * 0.35
    ) / 3.35


def _player_receiver_score(p: Any) -> float:
    return (
        float(getattr(p, "catching", 50))
        + float(getattr(p, "route_running", 50))
        + float(getattr(p, "speed", 50))
        + float(getattr(p, "agility", 50)) * 0.5
    ) / 3.5


def _player_coverage_score(p: Any) -> float:
    return (
        float(getattr(p, "coverage", 50))
        + float(getattr(p, "speed", 50))
        + float(getattr(p, "agility", 50))
        + float(getattr(p, "tackling", 50)) * 0.4
    ) / 3.4


def _is_qb(p: Any) -> bool:
    pos = str(getattr(p, "position", "") or "")
    sec = str(getattr(p, "secondary_position", "") or "")
    return pos == "QB" or sec == "QB"


def _is_receiver(p: Any) -> bool:
    pos = str(getattr(p, "position", "") or "")
    sec = str(getattr(p, "secondary_position", "") or "")
    return pos in ("WR", "TE", "RB") or sec in ("WR", "TE", "RB")


def _is_coverage(p: Any) -> bool:
    pos = str(getattr(p, "position", "") or "")
    sec = str(getattr(p, "secondary_position", "") or "")
    return pos in ("CB", "S", "LB") or sec in ("CB", "S", "LB")


def seven_on_seven_offense_rating(team: "Team", rating_mod: float = 0.0) -> int:
    """Passing-only offensive unit rating for 7-on-7."""
    roster = list(getattr(team, "roster", None) or [])
    qbs = [p for p in roster if _is_qb(p)]
    receivers = [p for p in roster if _is_receiver(p)]

    qb_score = max((_player_qb_score(p) for p in qbs), default=48.0)
    if receivers:
        rec_sorted = sorted(receivers, key=_player_receiver_score, reverse=True)[:3]
        rec_score = sum(_player_receiver_score(p) for p in rec_sorted) / len(rec_sorted)
    else:
        rec_score = 45.0

    raw = qb_score * 0.44 + rec_score * 0.56
    prestige = int(getattr(team, "prestige", 5) or 5)
    raw *= 0.88 + (prestige - 5) * 0.025
    return _clamp_rating(raw + rating_mod)


def seven_on_seven_defense_rating(team: "Team", rating_mod: float = 0.0) -> int:
    """Pass coverage unit rating for 7-on-7."""
    roster = list(getattr(team, "roster", None) or [])
    coverage = [p for p in roster if _is_coverage(p)]
    if coverage:
        top = sorted(coverage, key=_player_coverage_score, reverse=True)[:4]
        raw = sum(_player_coverage_score(p) for p in top) / len(top)
    else:
        raw = 45.0

    prestige = int(getattr(team, "prestige", 5) or 5)
    raw *= 0.88 + (prestige - 5) * 0.022
    return _clamp_rating(raw + rating_mod)


def _team_rating_mod(tier: str, team_name: str, user_team_name: str) -> float:
    if team_name == user_team_name:
        return 0.0
    return float(TOURNAMENT_TIERS[tier]["opponent_rating_mod"])


def _select_tournament_field(
    teams: Dict[str, "Team"],
    user_team_name: str,
    tier: str,
    rng: random.Random,
) -> List[str]:
    cfg = TOURNAMENT_TIERS[tier]
    lo = int(cfg["prestige_lo"])
    hi = int(cfg["prestige_hi"])
    user = teams[user_team_name]
    user_prestige = int(getattr(user, "prestige", 5) or 5)

    others = [(name, teams[name]) for name in teams if name != user_team_name]

    def sort_key(item: Tuple[str, "Team"]) -> Tuple[int, float, int]:
        _name, t = item
        p = int(getattr(t, "prestige", 5) or 5)
        delta = p - user_prestige
        if delta < lo:
            return (1, abs(delta - lo), p)
        if delta > hi:
            return (1, abs(delta - hi), -p)
        if tier == "state":
            return (0, -p, rng.random())
        if tier == "area":
            return (0, abs(delta) + max(0, delta) * 0.5, p)
        return (0, abs(delta), -p)

    ranked = sorted(others, key=sort_key)
    chosen: List[str] = [name for name, _ in ranked[:7]]
    if len(chosen) < 7:
        rest = [name for name, _ in others if name not in chosen]
        rng.shuffle(rest)
        chosen.extend(rest[: 7 - len(chosen)])
    rng.shuffle(chosen)
    return [user_team_name] + chosen[:7]


def _group_stage_pairings(team_names: List[str]) -> List[Tuple[str, str]]:
    """Eight teams: 3 in-group games + 1 crossover = 4 games per team."""
    if len(team_names) != 8:
        raise ValueError("7-on-7 tournament requires exactly 8 teams")
    group_a = team_names[0:4]
    group_b = team_names[4:8]
    games: List[Tuple[str, str]] = []
    for i in range(4):
        for j in range(i + 1, 4):
            games.append((group_a[i], group_a[j]))
    for i in range(4):
        for j in range(i + 1, 4):
            games.append((group_b[i], group_b[j]))
    for i in range(4):
        games.append((group_a[i], group_b[i]))
    return games


def _empty_record() -> Dict[str, int]:
    return {"w": 0, "l": 0, "pf": 0, "pa": 0}


def _simulate_possession(
    offense_rating: int,
    defense_rating: int,
    rng: random.Random,
) -> Tuple[int, Dict[str, int]]:
    """One passing possession; returns points scored and stat fragment."""
    edge = (offense_rating - defense_rating) / 25.0
    td_prob = max(0.14, min(0.56, 0.30 + edge * 0.14))
    int_prob = max(0.05, min(0.16, 0.10 - edge * 0.025))

    pass_yds = rng.randint(18, 52)
    att = rng.randint(3, 6)
    comp = max(1, min(att, int(round(att * (0.52 + edge * 0.08 + rng.uniform(-0.08, 0.08))))))

    roll = rng.random()
    if roll < int_prob:
        return 0, {"pass_yds": pass_yds, "comp": comp, "att": att, "td": 0, "int": 1}
    if roll < int_prob + td_prob:
        return 7, {"pass_yds": pass_yds + rng.randint(12, 28), "comp": comp, "att": att, "td": 1, "int": 0}
    return 0, {"pass_yds": pass_yds, "comp": comp, "att": att, "td": 0, "int": 0}


def _simulate_match(
    home_name: str,
    away_name: str,
    teams: Dict[str, "Team"],
    tier: str,
    user_team_name: str,
    rng: random.Random,
) -> Dict[str, Any]:
    home = teams[home_name]
    away = teams[away_name]
    home_off_mod = _team_rating_mod(tier, home_name, user_team_name)
    away_off_mod = _team_rating_mod(tier, away_name, user_team_name)
    home_def_mod = _team_rating_mod(tier, home_name, user_team_name)
    away_def_mod = _team_rating_mod(tier, away_name, user_team_name)

    home_off = seven_on_seven_offense_rating(home, home_off_mod)
    home_def = seven_on_seven_defense_rating(home, home_def_mod)
    away_off = seven_on_seven_offense_rating(away, away_off_mod)
    away_def = seven_on_seven_defense_rating(away, away_def_mod)

    home_score = 0
    away_score = 0
    home_stats = {"pass_yds": 0, "comp": 0, "att": 0, "td": 0, "int": 0}
    away_stats = {"pass_yds": 0, "comp": 0, "att": 0, "td": 0, "int": 0}

    drives = rng.randint(7, 9)
    for _ in range(drives):
        pts, frag = _simulate_possession(home_off, away_def, rng)
        home_score += pts
        for k, v in frag.items():
            home_stats[k] += v
        pts, frag = _simulate_possession(away_off, home_def, rng)
        away_score += pts
        for k, v in frag.items():
            away_stats[k] += v

    # Group standings require a W/L for every game; regulation ties go to OT.
    ot_possessions = 0
    while home_score == away_score and ot_possessions < 24:
        pts, frag = _simulate_possession(home_off, away_def, rng)
        home_score += pts
        for k, v in frag.items():
            home_stats[k] += v
        if home_score != away_score:
            break
        pts, frag = _simulate_possession(away_off, home_def, rng)
        away_score += pts
        for k, v in frag.items():
            away_stats[k] += v
        ot_possessions += 2
    if home_score == away_score:
        if rng.random() < 0.5:
            home_score += 7
        else:
            away_score += 7

    return {
        "home": home_name,
        "away": away_name,
        "home_score": home_score,
        "away_score": away_score,
        "home_stats": home_stats,
        "away_stats": away_stats,
        "phase": "group",
    }


def _match_winner(result: Dict[str, Any], rng: random.Random) -> str:
    hs = int(result["home_score"])
    as_ = int(result["away_score"])
    if hs > as_:
        return str(result["home"])
    if as_ > hs:
        return str(result["away"])
    return str(result["home"]) if rng.random() < 0.5 else str(result["away"])


def _apply_result(records: Dict[str, Dict[str, int]], result: Dict[str, Any]) -> None:
    home = result["home"]
    away = result["away"]
    hs = int(result["home_score"])
    as_ = int(result["away_score"])
    records[home]["pf"] += hs
    records[home]["pa"] += as_
    records[away]["pf"] += as_
    records[away]["pa"] += hs
    if hs > as_:
        records[home]["w"] += 1
        records[away]["l"] += 1
    elif as_ > hs:
        records[away]["w"] += 1
        records[home]["l"] += 1


def _standings_list(records: Dict[str, Dict[str, int]]) -> List[Dict[str, Any]]:
    rows = []
    for name, rec in records.items():
        rows.append(
            {
                "team": name,
                "w": rec["w"],
                "l": rec["l"],
                "pf": rec["pf"],
                "pa": rec["pa"],
                "diff": rec["pf"] - rec["pa"],
            }
        )
    rows.sort(key=lambda r: (-r["w"], -r["diff"], -r["pf"], r["team"]))
    for i, row in enumerate(rows, start=1):
        row["seed"] = i
    return rows


def _simulate_knockout_match(
    home_name: str,
    away_name: str,
    teams: Dict[str, "Team"],
    tier: str,
    user_team_name: str,
    rng: random.Random,
    phase: str,
) -> Dict[str, Any]:
    result = _simulate_match(home_name, away_name, teams, tier, user_team_name, rng)
    result["phase"] = phase
    return result


def _user_finish(user_team: str, champion: str, semifinals: List[Dict[str, Any]], rng: random.Random) -> str:
    if champion == user_team:
        return "Champion"
    for sf in semifinals:
        if user_team in (sf["home"], sf["away"]):
            winner = _match_winner(sf, rng)
            if winner != user_team:
                return "Semifinalist"
    return "Group stage"


def run_seven_on_seven_tournament(
    teams: Dict[str, "Team"],
    user_team_name: str,
    tier: str,
    *,
    seed: Optional[int] = None,
) -> Dict[str, Any]:
    """
    Run a full 7-on-7 tournament for the user's chosen tier.
    Returns a JSON-serializable payload for save state + UI.
    """
    tier_key = str(tier or "").strip().lower()
    if tier_key not in VALID_TOURNAMENT_TIERS:
        raise ValueError("Invalid 7-on-7 tournament tier. Choose area, regional, or state.")
    if not user_team_name or user_team_name not in teams:
        raise ValueError("User team not found for 7-on-7 tournament.")

    rng = random.Random(seed if seed is not None else random.randrange(1 << 30))
    field = _select_tournament_field(teams, user_team_name, tier_key, rng)
    group_a = field[0:4]
    group_b = field[4:8]

    records = {name: _empty_record() for name in field}
    group_games: List[Dict[str, Any]] = []

    for home, away in _group_stage_pairings(field):
        result = _simulate_match(home, away, teams, tier_key, user_team_name, rng)
        result["user_involved"] = user_team_name in (home, away)
        _apply_result(records, result)
        group_games.append(result)

    standings = _standings_list(records)
    top4 = [row["team"] for row in standings[:4]]

    semifinals: List[Dict[str, Any]] = []
    sf1 = _simulate_knockout_match(top4[0], top4[3], teams, tier_key, user_team_name, rng, "semifinal")
    sf2 = _simulate_knockout_match(top4[1], top4[2], teams, tier_key, user_team_name, rng, "semifinal")
    semifinals.extend([sf1, sf2])

    sf1_winner = _match_winner(sf1, rng)
    sf2_winner = _match_winner(sf2, rng)
    final = _simulate_knockout_match(sf1_winner, sf2_winner, teams, tier_key, user_team_name, rng, "final")
    champion = _match_winner(final, rng)

    user_rec = records[user_team_name]
    tier_cfg = TOURNAMENT_TIERS[tier_key]

    return {
        "tier": tier_key,
        "tier_label": tier_cfg["label"],
        "tier_description": tier_cfg["description"],
        "teams": field,
        "group_a": group_a,
        "group_b": group_b,
        "group_games": group_games,
        "standings": standings,
        "semifinals": semifinals,
        "final": final,
        "champion": champion,
        "user_team": user_team_name,
        "user_record": f"{user_rec['w']}-{user_rec['l']}",
        "user_finish": _user_finish(user_team_name, champion, semifinals, rng),
        "resolved": True,
    }
