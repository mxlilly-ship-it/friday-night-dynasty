"""
Player generator for high school football program.
Generates players with archetypes, community influence, two-way capability, and kicking.
Current ratings use RATING_ATTR_MIN–RATING_ATTR_MAX (see models.player); weak prestige programs
get wider tails into non-athlete / developmental play (roughly overall 10–20 / 21–39).
Potential follows tier baseline: Bench 40-55, Role 56-65, Solid 66-75,
All-State 76-85 (<10%), Elite 86-95 (<3%), Generational 96+ (very rare).
Influenced by community type, prestige, classification, and coach player_development.
Height/weight use broad HS bands (skill vs line), correlated rolls, archetype build hints,
and community bias (e.g. blue-collar lines / some RBs run heavier).
Age-14 (incoming ninth grade) players use lower base skills and lighter archetype/floor boosts;
recruited freshmen also pass recruiting_system dampening so current overalls stay raw vs potential.
"""

import random
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple, Any

from models.player import Player, RATING_ATTR_MAX, RATING_ATTR_MIN
from models.community import CommunityType, get_community_rating


# Archetype: (attr_name, modifier) where modifier is boost/diminish offset
# Modifiers: "++" = +15, "+" = +10, "moderate" = +0, "-" = -10
MODIFIERS = {"++": 15, "+": 10, "moderate": 0, "low": -10, "-": -10}

# Position groups
POSITION_GROUPS = {
    "QB": "offense",
    "RB": "offense",
    "WR": "offense",
    "OL": "offense",
    "TE": "offense",
    "DE": "defense",
    "DT": "defense",
    "LB": "defense",
    "CB": "defense",
    "S": "defense",
    "K": "specialist",
    "P": "specialist",
}

# Archetypes by position: archetype_name -> {attr: modifier}
ARCHETYPES: Dict[str, Dict[str, Tuple[str, int]]] = {
    # QB
    "Pro-Style QB": {
        "throw_accuracy": 10,
        "football_iq": 10,
        "decisions": 10,
        "speed": 0,  # moderate
    },
    "Dual-Threat QB": {
        "speed": 10,
        "agility": 10,
        "elusiveness": 10,
        "throw_power": 0,  # moderate
    },
    "Gunslinger QB": {
        "throw_power": 10,
        "throw_accuracy": 0,
        "composure": -10,
        "decisions": -10,
    },
    "Game Manager": {
        "football_iq": 10,
        "decisions": 10,
        "throw_accuracy": 10,
        "speed": -10,  # low
    },
    # RB
    "Power Back": {
        "strength": 10,
        "run_blocking": 10,
        "toughness": 10,
    },
    "Speed Back": {
        "speed": 10,
        "acceleration": 10,
        "elusiveness": 10,
    },
    "All-Purpose Back": {
        "agility": 10,
        "catching": 10,
        "vision": 10,
        "speed": 0,
    },
    "Breakaway Threat": {
        "speed": 15,  # ++
        "break_tackle": 10,
        "vision": 0,
    },
    # WR
    "Possession Receiver": {
        "catching": 10,
        "route_running": 10,
        "composure": 10,
    },
    "Deep Threat": {
        "speed": 10,
        "acceleration": 10,
        "elusiveness": 10,
    },
    "Slot Receiver": {
        "agility": 10,
        "route_running": 10,
        "football_iq": 10,
    },
    "All-Around WR": {
        "catching": 10,
        "speed": 10,
        "route_running": 0,
    },
    # OL (Awareness -> football_iq)
    "Pass Protector": {
        "pass_blocking": 10,
        "strength": 10,
        "football_iq": 10,  # Awareness
    },
    "Run Blocker": {
        "run_blocking": 10,
        "strength": 10,
        "effort": 10,
    },
    "Balanced OL": {},  # balanced
    # DE
    "Pass Rusher": {
        "pass_rush": 10,
        "speed": 10,
        "acceleration": 10,
        "block_shedding": 10,
    },
    "Run Stopper DE": {
        "run_defense": 10,
        "strength": 10,
        "tackling": 10,
        "pursuit": 10,
    },
    # DT
    "Plugger": {
        "run_defense": 10,
        "strength": 10,
        "block_shedding": 10,
        "tackling": 10,
    },
    "Penetrator": {
        "pass_rush": 10,
        "acceleration": 10,
        "football_iq": 0,
    },
    # LB
    "Coverage LB": {
        "coverage": 10,
        "speed": 10,
        "agility": 10,
        "football_iq": 10,
    },
    "Run Stopper LB": {
        "tackling": 10,
        "strength": 10,
        "pursuit": 10,
    },
    "Blitzer LB": {
        "pass_rush": 10,
        "acceleration": 10,
        "composure": -10,
    },
    "Balanced LB": {},
    # CB
    "Shutdown CB": {
        "coverage": 15,  # ++
        "speed": 10,
        "agility": 10,
        "composure": 10,
    },
    "Man Corner": {
        "coverage": 10,
        "speed": 10,
        "tackling": 0,
    },
    "Zone Corner": {
        "coverage": 10,
        "football_iq": 10,  # Awareness
    },
    "All-Around CB": {},
    # Specialists
    "Kicker": {
        "kick_power": 15,
        "kick_accuracy": 15,
    },
    "Punter": {
        "kick_power": 12,
        "kick_accuracy": 12,
    },
}

# Position -> list of archetypes
POSITION_ARCHETYPES: Dict[str, List[str]] = {
    "QB": ["Pro-Style QB", "Dual-Threat QB", "Gunslinger QB", "Game Manager"],
    "RB": ["Power Back", "Speed Back", "All-Purpose Back", "Breakaway Threat"],
    "WR": ["Possession Receiver", "Deep Threat", "Slot Receiver", "All-Around WR"],
    "OL": ["Pass Protector", "Run Blocker", "Balanced OL"],
    "TE": ["Possession Receiver", "Run Blocker", "All-Around WR"],  # hybrid
    "DE": ["Pass Rusher", "Run Stopper DE"],
    "DT": ["Plugger", "Penetrator"],
    "LB": ["Coverage LB", "Run Stopper LB", "Blitzer LB", "Balanced LB"],
    "CB": ["Shutdown CB", "Man Corner", "Zone Corner", "All-Around CB"],
    "S": ["Shutdown CB", "Run Stopper LB", "Coverage LB"],  # hybrid
    "K": ["Kicker"],
    "P": ["Punter"],
}

# Two-way pairings: primary -> common secondary positions (high school players play both ways)
TWO_WAY_PAIRS = {
    "QB": ["LB", "S"],  # QBs often play LB or S when on defense (athletic, football IQ)
    "RB": ["CB", "S", "LB"],
    "WR": ["CB", "S"],
    "OL": ["DT", "DE"],
    "TE": ["DE", "LB"],
    "DE": ["OL", "TE"],
    "DT": ["OL"],
    "LB": ["RB", "TE"],
    "CB": ["WR", "RB"],
    "S": ["WR", "RB"],
    "K": [],  # specialists rarely play other ways
    "P": [],
}

# Potential tier distribution (matches overall chart: most bench/role, few All-State/Elite, rare Generational)
# (min, max, weight) - weight = relative chance to land in this tier
POTENTIAL_TIER_WEIGHTS = [
    (40, 55, 40),   # Bench / developmental
    (56, 65, 34),   # Role player
    (66, 75, 18),   # Solid starter
    (76, 85, 7),    # All-State (<10%)
    (86, 95, 1),    # Elite (<3%)
    (96, 100, 0),   # Generational - handled separately, very rare
]
GENERATIONAL_CHANCE = 0.003  # ~0.3% - may be 0-1 in entire league

# Basic name pools (expand as needed)
FIRST_NAMES = [
    "James", "John", "Michael", "David", "William", "Robert", "Christopher",
    "Matthew", "Daniel", "Anthony", "Mark", "Donald", "Steven", "Paul",
    "Andrew", "Joshua", "Kenneth", "Kevin", "Brian", "George", "Timothy",
    "Tyler", "Jacob", "Mason", "Ethan", "Noah", "Lucas", "Logan", "Jackson",
]
LAST_NAMES = [
    "Smith", "Johnson", "Williams", "Brown", "Jones", "Garcia", "Miller",
    "Davis", "Rodriguez", "Martinez", "Wilson", "Anderson", "Taylor",
    "Thomas", "Moore", "Jackson", "Martin", "Lee", "Thompson", "White",
]


def _roll_base(base: int = 50, variance: int = 15) -> int:
    """Roll a base rating with variance."""
    return base + random.randint(-variance, variance)


def _apply_community_modifier(
    base_value: int, community_type: CommunityType, talent_weight: float = 0.7
) -> int:
    """Adjust base value based on community talent pool (1-10). Stronger spread: football factory +12, rural -5."""
    talent = get_community_rating(community_type, "talent_pool")
    # Talent 5 = neutral, 9 (football factory) = +11, 4 (rural) = -3
    modifier = int((talent - 5) * 2.8 * talent_weight)
    return base_value + modifier


def _roll_potential_from_tiers() -> int:
    """Roll potential using tier distribution. Returns 40-100. Generational very rare."""
    if random.random() < GENERATIONAL_CHANCE:
        return random.randint(96, 100)
    total_weight = sum(w for _, _, w in POTENTIAL_TIER_WEIGHTS if w > 0)
    r = random.randint(1, total_weight)
    for min_ovr, max_ovr, weight in POTENTIAL_TIER_WEIGHTS:
        if weight <= 0:
            continue
        if r <= weight:
            return random.randint(min_ovr, max_ovr)
        r -= weight
    return random.randint(40, 55)


def _potential_modifier(
    community_type: CommunityType,
    team_prestige: int,
    classification: Optional[str],
    coach_player_dev: Optional[int],
) -> int:
    """
    Modifier to add to rolled potential. Stronger spread: elite programs +12, weak -6.
    """
    # Community talent_pool (1-10): 5=0, 9=+6, 4=-3
    talent = get_community_rating(community_type, "talent_pool")
    mod = int((talent - 5) * 1.5)
    # Prestige (1-15): 5=0, 15=+6, 3=-2
    mod += max(-3, min(6, (team_prestige - 5)))
    # Classification: 6A/5A = +1, 4A/3A = 0, 2A/1A = -1
    if classification:
        class_bonus = {"6A": 2, "5A": 1, "4A": 0, "3A": 0, "2A": -1, "1A": -1}.get(
            classification.upper(), 0
        )
        mod += class_bonus
    # Coach player_development (1-10): 5=0, 10=+3
    if coach_player_dev is not None:
        mod += max(0, (coach_player_dev - 5) // 2)
    return max(-10, min(14, mod))


def _apply_weak_program_depth_tail(
    attrs: Dict[str, int],
    skill_attrs: List[str],
    team_prestige: int,
    position: str,
) -> None:
    """
    Pull a slice of each roster toward very low current ratings on weak programs.
    Skips specialists so kicking remains viable.
    """
    if position in ("K", "P") or team_prestige >= 10:
        return
    weak = max(0.0, (9.5 - float(team_prestige)) / 9.5)
    r = random.random()
    na_thr = 0.035 + weak * 0.12
    dev_thr = na_thr + 0.10 + weak * 0.22
    if r < na_thr:
        for attr in skill_attrs:
            attrs[attr] -= random.randint(8, 22)
    elif r < dev_thr:
        for attr in skill_attrs:
            attrs[attr] -= random.randint(3, 13)


# Size bands (inches / lbs), aligned with broad HS ranges:
# Skill (RB/CB/S/K/P): 5'4"-6'7" (64-79), 135-245 lb — lots of body-type variety.
# WR is intentionally narrower to avoid unrealistic tall outliers in bulk generation.
# QB: same height band; weight floor a bit higher (typical QB builds).
# Linemen (OL/DE/DT): 5'7"-6'6" (67-78), 205-350 lb.
# LB / TE: intermediate "tweener" bands.
# Rolls are correlated (tall ↔ heavier) within the band, then archetype + community nudges.
_POSITION_SIZE_BOUNDS: Dict[str, Tuple[int, int, int, int]] = {
    "QB": (64, 79, 155, 245),
    # Keep RBs in realistic HS range; very tall backs should be uncommon.
    "RB": (64, 76, 135, 245),
    # Most HS WRs should cluster around 5'9"–6'1", with a rare 6'3"+ tail.
    "WR": (65, 76, 145, 225),
    "CB": (64, 79, 135, 245),
    "S": (64, 79, 135, 245),
    "K": (64, 79, 135, 245),
    "P": (64, 79, 135, 245),
    "OL": (67, 78, 205, 350),
    "DE": (67, 78, 205, 350),
    "DT": (67, 78, 205, 350),
    "LB": (67, 76, 195, 250),
    "TE": (70, 79, 200, 270),
}

# (delta_height_low, delta_height_high), (delta_weight_low, delta_weight_high)
_ARCHETYPE_SIZE_DELTAS: Dict[str, Tuple[Tuple[int, int], Tuple[int, int]]] = {
    "Power Back": ((0, 1), (8, 28)),
    "Speed Back": ((-2, 0), (-18, -2)),
    "All-Purpose Back": ((-1, 1), (-6, 10)),
    "Breakaway Threat": ((-1, 1), (-14, 4)),
    "Possession Receiver": ((0, 1), (2, 16)),
    "Deep Threat": ((0, 1), (-10, 6)),
    "Slot Receiver": ((-2, 0), (-14, -2)),
    "All-Around WR": ((-1, 1), (-4, 8)),
    "Pro-Style QB": ((0, 2), (0, 14)),
    "Dual-Threat QB": ((-1, 1), (-8, 6)),
    "Gunslinger QB": ((0, 2), (0, 12)),
    "Game Manager": ((0, 1), (-4, 10)),
    "Pass Protector": ((0, 2), (4, 22)),
    "Run Blocker": ((0, 2), (8, 28)),
    "Pass Rusher": ((0, 1), (-6, 10)),
    "Run Stopper DE": ((0, 1), (10, 32)),
    "Plugger": ((0, 2), (14, 42)),
    "Penetrator": ((0, 1), (-8, 8)),
    "Coverage LB": ((-1, 1), (-8, 4)),
    "Run Stopper LB": ((0, 1), (6, 22)),
    "Blitzer LB": ((0, 1), (2, 14)),
    "Shutdown CB": ((0, 2), (4, 16)),
    "Man Corner": ((0, 1), (-4, 10)),
    "Zone Corner": ((0, 1), (-2, 8)),
    "Kicker": ((-1, 1), (-10, 4)),
    "Punter": ((0, 2), (-6, 8)),
}


def _position_size_bounds(position: str) -> Tuple[int, int, int, int]:
    """Return (height_min, height_max, weight_min, weight_max) in inches / pounds."""
    return _POSITION_SIZE_BOUNDS.get(position, (66, 76, 160, 260))


def _archetype_size_delta(archetype: str) -> Tuple[int, int]:
    row = _ARCHETYPE_SIZE_DELTAS.get(archetype or "")
    if not row:
        return 0, 0
    (h0, h1), (w0, w1) = row
    return random.randint(h0, h1), random.randint(w0, w1)


def _roll_correlated_height_weight(
    h_min: int, h_max: int, w_min: int, w_max: int
) -> Tuple[int, int]:
    """Uniform build percentile maps to height; weight follows with Gaussian noise (realistic spread)."""
    if h_max <= h_min:
        height = h_min
    else:
        t = random.random()
        height = h_min + int(round(t * (h_max - h_min)))
    span_w = w_max - w_min
    if span_w <= 0:
        weight = w_min
    else:
        t_h = (height - h_min) / max(1, (h_max - h_min))
        center_w = w_min + t_h * span_w
        sigma = max(5.5, span_w * 0.17)
        weight = int(random.gauss(center_w, sigma))
        weight = max(w_min, min(w_max, weight))
    return height, weight


def _apply_community_size_bias(
    position: str,
    community_type: CommunityType,
    height: int,
    weight: int,
    h_min: int,
    h_max: int,
    w_min: int,
    w_max: int,
) -> Tuple[int, int]:
    """Slight shifts by community (blue-collar → more mass on lines / some RB-LB types)."""
    h, w = height, weight
    if community_type == CommunityType.BLUE_COLLAR:
        if position in ("OL", "DT", "DE"):
            w += random.randint(4, 28)
            if random.random() < 0.42:
                h += 1
        elif position in ("LB", "TE"):
            w += random.randint(0, 16)
        elif position == "RB" and random.random() < 0.38:
            w += random.randint(6, 22)
    elif community_type == CommunityType.FOOTBALL_FACTORY:
        # Slightly more "prototype" length on perimeter / edge
        if position in ("WR", "CB", "S", "TE", "DE") and random.random() < 0.24:
            h += 1
        if position in ("WR", "CB", "DE", "TE"):
            w += random.randint(-4, 12)
    elif community_type == CommunityType.AFFLUENT:
        # Nutrition / early growth: small bump to height chance for skill spots
        if position in ("QB", "WR", "TE") and random.random() < 0.12:
            h += 1
    elif community_type == CommunityType.RURAL:
        if position in ("OL", "DT", "LB") and random.random() < 0.2:
            w += random.randint(0, 12)
    return max(h_min, min(h_max, h)), max(w_min, min(w_max, w))


def roll_height_weight_for_position(
    position: str,
    community_type: CommunityType,
    archetype: str,
) -> Tuple[int, int]:
    """Public helper: correlated size roll + archetype + community (used by generators)."""
    h_min, h_max, w_min, w_max = _position_size_bounds(position)
    if position == "WR":
        # Keep most WRs in realistic HS bands while preserving a small tall-outlier tail.
        r = random.random()
        if r < 0.84:
            height = random.randint(69, 73)  # 5'9" - 6'1" majority
        elif r < 0.97:
            height = random.randint(74, 75)  # 6'2" - 6'3" uncommon
        else:
            height = 76  # 6'4" rare
        span_w = w_max - w_min
        if span_w <= 0:
            weight = w_min
        else:
            t_h = (height - h_min) / max(1, (h_max - h_min))
            center_w = w_min + t_h * span_w
            sigma = max(5.5, span_w * 0.17)
            weight = int(random.gauss(center_w, sigma))
            weight = max(w_min, min(w_max, weight))
    elif position == "RB":
        # RBs should overwhelmingly live in compact ranges, with rare 6'3"+ outliers.
        r = random.random()
        if r < 0.80:
            height = random.randint(67, 72)  # 5'7" - 6'0" majority
        elif r < 0.97:
            height = random.randint(73, 74)  # 6'1" - 6'2" uncommon
        else:
            height = random.randint(75, 76)  # 6'3" - 6'4" rare
        span_w = w_max - w_min
        if span_w <= 0:
            weight = w_min
        else:
            t_h = (height - h_min) / max(1, (h_max - h_min))
            center_w = w_min + t_h * span_w
            sigma = max(5.5, span_w * 0.17)
            weight = int(random.gauss(center_w, sigma))
            weight = max(w_min, min(w_max, weight))
    else:
        height, weight = _roll_correlated_height_weight(h_min, h_max, w_min, w_max)
    dh, dw = _archetype_size_delta(archetype)
    height += dh
    weight += dw
    height = max(h_min, min(h_max, height))
    weight = max(w_min, min(w_max, weight))
    return _apply_community_size_bias(
        position, community_type, height, weight, h_min, h_max, w_min, w_max
    )


def generate_name() -> str:
    """Generate a random player name."""
    return f"{random.choice(FIRST_NAMES)} {random.choice(LAST_NAMES)}"


def generate_player(
    position: str,
    community_type: CommunityType = CommunityType.SUBURBAN,
    archetype: Optional[str] = None,
    name: Optional[str] = None,
    age: Optional[int] = None,
    secondary_position: Optional[str] = None,
    has_kicking: bool = False,
    team_prestige: int = 5,
    classification: Optional[str] = None,
    coach: Optional[Any] = None,
) -> Player:
    """
    Generate a single player.

    - position: Primary position (QB, RB, WR, OL, TE, DE, DT, LB, CB, S, K, P)
    - community_type: Influences talent level, potential, and attribute distribution
    - archetype: If None, picks randomly from position's archetypes
    - secondary_position: For two-way players (e.g., RB who also plays CB)
    - has_kicking: Whether player has kick/punt ability
    - team_prestige: Affects potential ceiling and talent floor
    - classification: 1A-6A; larger schools (5A/6A) attract slightly better talent
    - coach: Team coach; player_development skill affects potential distribution
    """
    name = name or generate_name()
    age = age if age is not None else random.randint(14, 18)
    year = min(12, 9 + max(0, age - 14))  # 14->9, 15->10, 16->11, 17-18->12
    # Incoming ninth graders should be raw: low current ratings, room to grow (potential handled separately).
    young_freshman = age <= 14

    coach_dev = getattr(coach, "player_development", None) if coach else None

    archetypes = POSITION_ARCHETYPES.get(position, ["Balanced OL"])
    archetype = archetype or random.choice(archetypes)
    boosts = ARCHETYPES.get(archetype, {})

    # Base attributes: center shifts by prestige + talent; low prestige sits lower (more 10–39 bodies).
    talent = get_community_rating(community_type, "talent_pool")
    if young_freshman:
        # HS freshmen: mostly not game-ready; keep current skills well below varsity starters.
        base = 38 + int((team_prestige - 5) * 0.32) + int((talent - 5) * 0.3)
        base = max(22, min(46, base))
        talent_weight = 0.32
    else:
        base = 45 + int((team_prestige - 5) * 2.65) + int((talent - 5) * 0.55)
        base = max(24, min(59, base))
        talent_weight = 0.72  # Stronger community influence
    attrs: Dict[str, int] = {}
    skill_attrs = [
        "speed", "agility", "acceleration", "strength", "balance", "jumping",
        "stamina", "injury", "frame",
        "toughness", "effort", "football_iq", "coachability", "confidence",
        "discipline", "leadership", "composure",
        "throw_power", "throw_accuracy", "decisions", "catching",
        "run_blocking", "pass_blocking", "vision", "ball_security",
        "break_tackle", "elusiveness", "route_running", "coverage",
        "blitz", "pass_rush", "run_defense", "pursuit", "tackling", "block_shedding",
        "kick_power", "kick_accuracy",
        "growth_rate", "consistency", "late_bloomer", "early_bloomer",
    ]
    var_boost = max(0, 7 - min(team_prestige, 7)) * 2
    for attr in skill_attrs:
        val = _roll_base(base, variance=(18 + var_boost // 2) if young_freshman else (14 + var_boost))
        val = _apply_community_modifier(val, community_type, talent_weight=talent_weight)
        b = boosts.get(attr, 0)
        if young_freshman:
            val += int(b * 0.5) if b else 0
        else:
            val += b
        attrs[attr] = val

    # Potential: tier-based (Bench 40-55, Role 56-65, Solid 66-75, All-State 76-85, Elite 86-95, Generational 96+)
    potential = _roll_potential_from_tiers()
    potential += _potential_modifier(community_type, team_prestige, classification, coach_dev)
    # Small random variance (±2) so similar programs still get variety
    potential += random.randint(-2, 2)
    attrs["potential"] = max(40, min(RATING_ATTR_MAX, potential))

    # Growth_rate: influenced by community facilities and coach player_development
    facilities = get_community_rating(community_type, "facilities")
    coach_bonus = (coach_dev - 5) if coach_dev is not None else 0
    attrs["growth_rate"] = max(RATING_ATTR_MIN, min(RATING_ATTR_MAX, attrs["growth_rate"] + (facilities - 5) + coach_bonus))

    # Position-specific base tweaks (emphasize relevant attributes)
    pos_emphasis = {
        "QB": ["throw_power", "throw_accuracy", "decisions", "football_iq"],
        "RB": ["speed", "vision", "break_tackle", "ball_security"],
        "WR": ["catching", "route_running", "speed", "agility"],
        "OL": ["run_blocking", "pass_blocking", "strength"],
        "TE": ["catching", "run_blocking", "strength"],
        "DE": ["pass_rush", "block_shedding", "speed"],
        "DT": ["strength", "run_defense", "block_shedding"],
        "LB": ["tackling", "pursuit", "coverage"],
        "CB": ["coverage", "speed", "agility"],
        "S": ["coverage", "tackling", "football_iq"],
        "K": ["kick_power", "kick_accuracy"],
        "P": ["kick_power", "kick_accuracy"],
    }
    pos_boost_hi = 4 if young_freshman else 8
    for attr in pos_emphasis.get(position, []):
        attrs[attr] = min(RATING_ATTR_MAX, attrs[attr] + random.randint(0, pos_boost_hi))

    # Prestige floor: stronger programs pull lows toward a higher bar; weak programs leave more room for tails.
    prestige_floor = max(0, min(12, int((team_prestige - 2) * 1.6)))
    if young_freshman:
        prestige_floor = min(5, prestige_floor // 2)
        floor_target = 40 + min(4, max(0, team_prestige - 3))
    else:
        floor_target = 42 + (max(0, team_prestige - 3) * 5) // 4
        floor_target = min(52, int(floor_target))
    for attr in skill_attrs:
        if attrs[attr] < floor_target and prestige_floor > 0:
            attrs[attr] = min(floor_target, attrs[attr] + random.randint(0, prestige_floor))

    _apply_weak_program_depth_tail(attrs, skill_attrs, team_prestige, position)

    # Size by position (correlated H/W, archetype + community bias)
    height, weight = roll_height_weight_for_position(position, community_type, archetype)

    # Peak age (14-18)
    peak_age = random.randint(14, 18)

    # Two-way: boost secondary position attributes
    if secondary_position and secondary_position in POSITION_ARCHETYPES:
        sec_archs = POSITION_ARCHETYPES[secondary_position]
        sec_archetype = random.choice(sec_archs)
        sec_boosts = ARCHETYPES.get(sec_archetype, {})
        sec_div = 3 if young_freshman else 2
        for attr, delta in sec_boosts.items():
            attrs[attr] = attrs.get(attr, 50) + delta // sec_div  # lighter secondary boost for young freshmen

    # Kicking ability (any player can have it)
    if has_kicking or position in ("K", "P"):
        if position in ("K", "P"):
            pass  # already boosted by archetype
        else:
            attrs["kick_power"] = min(RATING_ATTR_MAX, attrs["kick_power"] + random.randint(5, 20))
            attrs["kick_accuracy"] = min(RATING_ATTR_MAX, attrs["kick_accuracy"] + random.randint(5, 20))

    # Build Player
    rating_attrs = {k: v for k, v in attrs.items() if k not in ("height", "weight", "peak_age")}
    return Player(
        name=name,
        age=age,
        year=year,
        position=position,
        secondary_position=secondary_position,
        height=height,
        weight=weight,
        peak_age=peak_age,
        **rating_attrs,
    )


def generate_roster(
    community_type: CommunityType,
    team_prestige: int = 5,
    roster_size: int = 50,
    two_way_chance: float = 0.4,
    kicking_chance: float = 0.15,
) -> List[Player]:
    """Generate a full roster with position distribution and two-way/kicking variety."""
    # Rough position distribution for a high school team
    POSITION_COUNTS = {
        "QB": 2, "RB": 4, "WR": 6, "OL": 8, "TE": 2,
        "DE": 4, "DT": 3, "LB": 5, "CB": 4, "S": 3,
        "K": 1, "P": 1,
    }
    players: List[Player] = []
    for pos, count in POSITION_COUNTS.items():
        for _ in range(count):
            sec = None
            if random.random() < two_way_chance and pos in TWO_WAY_PAIRS and TWO_WAY_PAIRS[pos]:
                sec = random.choice(TWO_WAY_PAIRS[pos])
            kick = random.random() < kicking_chance or pos in ("K", "P")
            p = generate_player(
                position=pos,
                community_type=community_type,
                name=None,
                secondary_position=sec,
                has_kicking=kick,
                team_prestige=team_prestige,
            )
            players.append(p)
    return players
