"""
Calculate team overall ratings (offense, defense, run, pass) from roster.
Used to feed the game engine for simulation.

Overall tier baseline (helps weigh ratings and evaluate talent).
Includes non-athlete / developmental bands below traditional bench.
"""

from typing import TYPE_CHECKING, Dict, List, Optional, Tuple

from models.community import get_community_rating
from models.player import RATING_ATTR_MAX, RATING_ATTR_MIN

if TYPE_CHECKING:
    from models.player import Player
    from models.team import Team


def _get_prestige_community_multiplier(prestige: int, talent_pool: int) -> float:
    """
    Program strength multiplier. Elite (prestige 15, football factory) ~1.5x;
    weak (prestige 3, rural) ~0.85x. Target: Martinsburg 80s, Preston ~45-50.
    """
    mult = 0.82 + (prestige - 3) * 0.04 + (talent_pool - 4) * 0.05
    return max(0.75, min(1.6, mult))

# Overall tier baseline: (min_ovr, max_ovr, tier_name), low → high.
# Non-athlete / developmental expand the bottom; bench and up unchanged vs legacy bands.
OVERALL_TIERS: List[Tuple[int, int, str]] = [
    (10, 20, "Non-athlete"),
    (21, 39, "Developmental"),
    (40, 55, "Bench / developmental"),
    (56, 65, "Role player"),
    (66, 75, "Solid starter"),
    (76, 85, "All-State"),        # Less than 10% of league
    (86, 95, "Elite"),            # Less than 3% of league
    (96, 100, "Generational"),    # Very few; may be 0–1 in league at a time
]


def get_overall_tier(overall: int) -> str:
    """Return tier label for an overall rating (10–20 non-athlete, 21–39 developmental, 40+ bench+)."""
    ovr = max(RATING_ATTR_MIN, min(RATING_ATTR_MAX, int(overall)))
    for min_ovr, max_ovr, label in OVERALL_TIERS:
        if min_ovr <= ovr <= max_ovr:
            return label
    return "Non-athlete"


def get_overall_tier_range(overall: int) -> Tuple[str, int, int]:
    """Return (tier_label, min_ovr, max_ovr) for an overall rating."""
    ovr = max(RATING_ATTR_MIN, min(RATING_ATTR_MAX, int(overall)))
    for min_ovr, max_ovr, label in OVERALL_TIERS:
        if min_ovr <= ovr <= max_ovr:
            return (label, min_ovr, max_ovr)
    return ("Non-athlete", 10, 20)


def _player_offense_contribution(p: "Player") -> float:
    """Offensive contribution based on position."""
    if p.position == "QB":
        return (p.throw_power + p.throw_accuracy + p.decisions + p.football_iq) / 4
    if p.position in ("RB",):
        return (p.speed + p.break_tackle + p.vision + p.ball_security + p.catching) / 5
    if p.position in ("WR", "TE"):
        return (p.catching + p.route_running + p.speed + p.agility) / 4
    if p.position == "OL":
        return (p.run_blocking + p.pass_blocking + p.strength) / 3
    if p.secondary_position and p.secondary_position in ("RB", "WR", "TE"):
        return (p.catching + p.speed + p.vision) / 3 * 0.5  # half weight for two-way
    return 0


def _player_defense_contribution(p: "Player") -> float:
    """Defensive contribution based on position."""
    if p.position in ("DE", "DT"):
        return (p.pass_rush + p.run_defense + p.block_shedding + p.strength) / 4
    if p.position == "LB":
        return (p.tackling + p.pursuit + p.coverage + p.run_defense) / 4
    if p.position in ("CB", "S"):
        return (p.coverage + p.speed + p.agility + p.tackling) / 4
    if p.secondary_position and p.secondary_position in ("DE", "DT", "LB", "CB", "S"):
        return (p.tackling + p.coverage + p.speed) / 3 * 0.5  # half weight for two-way
    return 0


def _player_run_contribution(p: "Player") -> float:
    """Run game contribution (offense)."""
    if p.position == "QB":
        return (p.speed + p.agility + p.elusiveness) / 3 * 0.3  # dual-threat factor
    if p.position == "RB":
        return (p.speed + p.break_tackle + p.vision + p.strength) / 4
    if p.position in ("WR", "TE"):
        return p.run_blocking * 0.5  # WR/TE blocking
    if p.position == "OL":
        return (p.run_blocking + p.strength) / 2
    return 0


def _player_pass_contribution(p: "Player") -> float:
    """Pass game contribution (offense)."""
    if p.position == "QB":
        return (p.throw_power + p.throw_accuracy + p.decisions) / 3
    if p.position in ("WR", "TE"):
        return (p.catching + p.route_running + p.speed) / 3
    if p.position == "RB":
        return p.catching * 0.5  # check-down / screen
    if p.position == "OL":
        return (p.pass_blocking + p.strength) / 2
    return 0


# Starters weighted 2x, backups 0.5x (~11 starters per side)
STARTER_COUNT = 11
STARTER_WEIGHT = 2.0
BACKUP_WEIGHT = 0.5


def _weighted_avg_starters(
    items: List[Tuple[float, float, float, float]],
) -> Tuple[float, float, float, float]:
    """
    items = (off_contrib, def_contrib, run_contrib, pass_contrib) per player.
    Sort by relevance, weight top STARTER_COUNT 2x, rest 0.5x.
    """
    off_items = [(o, d, r, p) for o, d, r, p in items if o > 0]
    def_items = [(o, d, r, p) for o, d, r, p in items if d > 0]
    run_items = [(o, d, r, p) for o, d, r, p in items if r > 0]
    pass_items = [(o, d, r, p) for o, d, r, p in items if p > 0]

    def _avg_weighted(vals: List[float], sort_key_vals: List[float]) -> float:
        if not vals:
            return 50.0
        paired = list(zip(vals, sort_key_vals))
        paired.sort(key=lambda x: x[1], reverse=True)
        weights = [STARTER_WEIGHT] * min(STARTER_COUNT, len(paired)) + [BACKUP_WEIGHT] * max(0, len(paired) - STARTER_COUNT)
        total = sum(v * w for (v, _), w in zip(paired, weights))
        denom = sum(weights)
        return total / denom if denom else 50.0

    offense = _avg_weighted([o for o, d, r, p in off_items], [o for o, d, r, p in off_items]) if off_items else 50.0
    defense = _avg_weighted([d for o, d, r, p in def_items], [d for o, d, r, p in def_items]) if def_items else 50.0
    run = _avg_weighted([r for o, d, r, p in run_items], [r for o, d, r, p in run_items]) if run_items else 50.0
    pass_ = _avg_weighted([p for o, d, r, p in pass_items], [p for o, d, r, p in pass_items]) if pass_items else 50.0
    return (offense, defense, run, pass_)


def calculate_team_ratings(team: "Team") -> Dict[str, int]:
    """
    Calculate offense, defense, run, pass ratings (1-100) from roster.
    Uses starter-weighted averaging (top 11 per side weighted 2x, backups 0.5x).
    """
    roster = team.roster
    if not roster:
        return {"offense": 50, "defense": 50, "run": 50, "pass": 50}

    items: List[Tuple[float, float, float, float]] = [
        (
            _player_offense_contribution(p),
            _player_defense_contribution(p),
            _player_run_contribution(p),
            _player_pass_contribution(p),
        )
        for p in roster
    ]
    offense, defense, run, pass_ = _weighted_avg_starters(items)

    # Prestige/community multiplier: elite programs (Martinsburg) scale up, weak (Preston) scale down
    prestige = getattr(team, "prestige", 5) or 5
    talent_pool = get_community_rating(team.community_type, "talent_pool")
    mult = _get_prestige_community_multiplier(prestige, talent_pool)
    offense = offense * mult
    defense = defense * mult
    run = run * mult
    pass_ = pass_ * mult

    # Scale to game engine range (roughly 20-95) - clamp 1-100
    def _clamp(v: float) -> int:
        return max(20, min(95, int(round(v))))

    return {
        "offense": _clamp(offense),
        "defense": _clamp(defense),
        "run": _clamp(run),
        "pass": _clamp(pass_),
    }


def _avg_attr(players: List["Player"], attr: str, default: float = 50.0) -> float:
    """Average a player attribute across a list of players."""
    if not players:
        return default
    vals = [float(getattr(p, attr, default)) for p in players]
    return sum(vals) / len(vals) if vals else default


def calculate_turnover_profile(team: "Team") -> Dict[str, int]:
    """
    Build turnover-related ratings (1-100) from roster attributes.
    Used by game engine to tune INT/FUM rates.
    """
    roster = team.roster or []
    if not roster:
        return {
            "qb_decisions": 50,
            "qb_arm_strength": 50,
            "off_ball_security": 50,
            "off_discipline": 50,
            "def_coverage": 50,
            "def_tackling": 50,
            "def_pass_rush": 50,
        }

    qbs = [p for p in roster if p.position == "QB" or p.secondary_position == "QB"]
    skill = [p for p in roster if p.position in ("QB", "RB", "WR", "TE") or p.secondary_position in ("QB", "RB", "WR", "TE")]
    coverage_players = [p for p in roster if p.position in ("CB", "S", "LB") or p.secondary_position in ("CB", "S", "LB")]
    tackling_players = [p for p in roster if p.position in ("DE", "DT", "LB", "CB", "S") or p.secondary_position in ("DE", "DT", "LB", "CB", "S")]
    rush_players = [p for p in roster if p.position in ("DE", "DT", "LB") or p.secondary_position in ("DE", "DT", "LB")]

    def _clamp(v: float) -> int:
        return max(20, min(95, int(round(v))))

    if qbs:
        qb_best = max(qbs, key=lambda p: (p.decisions + p.throw_power + p.discipline))
        qb_decisions = float(qb_best.decisions)
        qb_arm_strength = float(qb_best.throw_power)
        # QB scramble base rate from mobility (Pocket 1-3%, Average 4-6%, Dual-Threat 6-8%, Elite 9-12%)
        qb_mobility = (qb_best.speed + qb_best.agility + qb_best.elusiveness) / 3.0
        if qb_mobility < 42:
            qb_scramble_base = 0.02  # Pocket
        elif qb_mobility < 55:
            qb_scramble_base = 0.045  # Average
        elif qb_mobility < 70:
            qb_scramble_base = 0.07   # Dual-Threat
        else:
            qb_scramble_base = 0.105  # Elite runner
        qb_scramble_base = max(0.01, min(0.12, qb_scramble_base))
    else:
        qb_decisions = 50.0
        qb_arm_strength = 50.0
        qb_scramble_base = 0.04

    off_ball_security = (_avg_attr(skill, "ball_security") * 0.65) + (_avg_attr(skill, "discipline") * 0.35)
    off_discipline = _avg_attr(skill, "discipline")

    def_coverage = (_avg_attr(coverage_players, "coverage") * 0.65) + (_avg_attr(coverage_players, "football_iq") * 0.20) + (_avg_attr(coverage_players, "speed") * 0.15)
    def_tackling = (_avg_attr(tackling_players, "tackling") * 0.65) + (_avg_attr(tackling_players, "pursuit") * 0.20) + (_avg_attr(tackling_players, "discipline") * 0.15)
    def_pass_rush = (_avg_attr(rush_players, "pass_rush") * 0.65) + (_avg_attr(rush_players, "blitz") * 0.20) + (_avg_attr(rush_players, "block_shedding") * 0.15)

    return {
        "qb_decisions": _clamp(qb_decisions),
        "qb_arm_strength": _clamp(qb_arm_strength),
        "qb_scramble_base": qb_scramble_base,  # float 0.01-0.12 for scramble chance base
        "off_ball_security": _clamp(off_ball_security),
        "off_discipline": _clamp(off_discipline),
        "def_coverage": _clamp(def_coverage),
        "def_tackling": _clamp(def_tackling),
        "def_pass_rush": _clamp(def_pass_rush),
    }


def calculate_player_overall(player: "Player") -> int:
    """Calculate single player overall (1-100) based on primary position."""
    if player.position in ("QB", "RB", "WR", "OL", "TE"):
        contrib = _player_offense_contribution(player) * 0.6 + _player_run_contribution(player) * 0.2 + _player_pass_contribution(player) * 0.2
    elif player.position in ("DE", "DT", "LB", "CB", "S"):
        contrib = _player_defense_contribution(player)
    elif player.position in ("K", "P"):
        contrib = (player.kick_power + player.kick_accuracy) / 2
    else:
        contrib = 50
    return max(RATING_ATTR_MIN, min(RATING_ATTR_MAX, int(round(contrib))))


def _rate_at_offense_pos(p: "Player", pos: str) -> float:
    """Rate player as if they played this offensive position."""
    if pos == "QB":
        return (p.throw_power + p.throw_accuracy + p.decisions + p.football_iq) / 4
    if pos == "RB":
        return (p.speed + p.break_tackle + p.vision + p.ball_security + p.catching) / 5
    if pos in ("WR", "TE"):
        return (p.catching + p.route_running + p.speed + p.agility) / 4
    if pos == "OL":
        return (p.run_blocking + p.pass_blocking + p.strength) / 3
    return 0


def _rate_at_defense_pos(p: "Player", pos: str) -> float:
    """Rate player as if they played this defensive position."""
    if pos in ("DE", "DT"):
        return (p.pass_rush + p.run_defense + p.block_shedding + p.strength) / 4
    if pos == "LB":
        return (p.tackling + p.pursuit + p.coverage + p.run_defense) / 4
    if pos in ("CB", "S"):
        return (p.coverage + p.speed + p.agility + p.tackling) / 4
    return 0


def calculate_player_offense_overall(player: "Player") -> int:
    """
    Offensive overall (1-100). Uses best offensive position (primary or secondary).
    For pure defense/specialists with no offensive position, returns backup-style rating
    (e.g. DE as emergency TE based on blocking/catching).
    """
    best = 0
    for pos in ("QB", "RB", "WR", "TE", "OL"):
        if player.position == pos or player.secondary_position == pos:
            best = max(best, _rate_at_offense_pos(player, pos))
    if best > 0:
        return max(RATING_ATTR_MIN, min(RATING_ATTR_MAX, int(round(best))))
    # No offensive position: emergency/conversion rating (e.g. DL as TE)
    as_te = (player.run_blocking + player.strength + player.catching) / 3
    return max(RATING_ATTR_MIN, min(RATING_ATTR_MAX, int(round(as_te))))


def calculate_player_defense_overall(player: "Player") -> int:
    """
    Defensive overall (1-100). Uses best defensive position (primary or secondary).
    For pure offense/specialists with no defensive position, returns backup-style rating
    (e.g. QB/WR as emergency DB based on speed/coverage/tackling).
    """
    best = 0
    for pos in ("DE", "DT", "LB", "CB", "S"):
        if player.position == pos or player.secondary_position == pos:
            best = max(best, _rate_at_defense_pos(player, pos))
    if best > 0:
        return max(RATING_ATTR_MIN, min(RATING_ATTR_MAX, int(round(best))))
    # No defensive position: emergency DB conversion
    as_db = (player.coverage + player.speed + player.agility + player.tackling) / 4
    return max(RATING_ATTR_MIN, min(RATING_ATTR_MAX, int(round(as_db))))


OFFENSE_POSITIONS = ("QB", "RB", "WR", "TE", "OL")
DEFENSE_POSITIONS = ("DE", "DT", "LB", "CB", "S")


def _has_offense_position(player: "Player") -> bool:
    """True if primary or secondary is an offensive position."""
    return player.position in OFFENSE_POSITIONS or (player.secondary_position or "") in OFFENSE_POSITIONS


def _has_defense_position(player: "Player") -> bool:
    """True if primary or secondary is a defensive position."""
    return player.position in DEFENSE_POSITIONS or (player.secondary_position or "") in DEFENSE_POSITIONS


def is_two_way(player: "Player") -> bool:
    """True if player has both offensive and defensive positions (primary or secondary)."""
    return _has_offense_position(player) and _has_defense_position(player)


def get_player_offense_position(player: "Player") -> Optional[str]:
    """Best offensive position for display (primary or secondary). None if no offensive position."""
    if player.position in OFFENSE_POSITIONS:
        return player.position
    if (player.secondary_position or "") in OFFENSE_POSITIONS:
        return player.secondary_position
    return None


def get_player_defense_position(player: "Player") -> Optional[str]:
    """Best defensive position for display (primary or secondary). None if no defensive position."""
    if player.position in DEFENSE_POSITIONS:
        return player.position
    if (player.secondary_position or "") in DEFENSE_POSITIONS:
        return player.secondary_position
    return None
