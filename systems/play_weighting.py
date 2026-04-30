"""
Per-play weighting by roster attributes.
Scores each play by how well the team's personnel fit the play
(e.g. option plays favor mobile QB; zone coverage favors DB coverage; pressure favors DL pass rush).
"""

from typing import Any, Dict, List, Optional, Tuple, Union

from models.player import RATING_ATTR_MAX, RATING_ATTR_MIN

# Type: list of (position_key, [attribute_names])
# position_key: "QB", "RB", "WR", "TE", "OL", "DL", "LB", "DB"
PlaySpec = List[Tuple[str, List[str]]]

# Play id -> which positions and attributes make this play effective
PLAY_OFFENSIVE_WEIGHTS: Dict[str, PlaySpec] = {
    # Dual - Inside Run
    "dual_inside_zone": [("RB", ["vision", "speed", "break_tackle"]), ("OL", ["run_blocking", "strength"])],
    "dual_read_option": [("QB", ["speed", "agility", "decisions"]), ("RB", ["speed", "vision"])],
    "dual_trap": [("RB", ["vision", "strength"]), ("OL", ["run_blocking", "strength"])],
    # Outside Run
    "dual_oz": [("RB", ["speed", "agility", "vision"]), ("OL", ["run_blocking"])],
    "dual_speed_option": [("QB", ["speed", "agility"]), ("RB", ["speed", "elusiveness"])],
    "dual_q_sweep": [("QB", ["speed", "agility", "elusiveness"])],
    # Quick Game
    "dual_slants": [("QB", ["throw_accuracy", "decisions"]), ("WR", ["route_running", "catching", "agility"])],
    "dual_hitches": [("QB", ["throw_accuracy", "decisions"]), ("WR", ["route_running", "catching"])],
    "dual_bubbles": [("WR", ["catching", "agility", "speed"]), ("QB", ["throw_accuracy"])],
    # Medium
    "dual_smash": [("QB", ["throw_accuracy", "decisions"]), ("WR", ["route_running", "catching"])],
    "dual_levels": [("QB", ["throw_accuracy", "decisions"]), ("WR", ["route_running", "catching"])],
    "dual_shallow": [("QB", ["throw_accuracy", "decisions"]), ("WR", ["route_running", "catching", "speed"])],
    # Deep
    "dual_verts": [("QB", ["throw_power", "throw_accuracy"]), ("WR", ["speed", "catching", "route_running"])],
    "dual_scissors": [("QB", ["throw_power", "throw_accuracy"]), ("WR", ["speed", "route_running", "catching"])],
    "dual_missile": [("QB", ["throw_power", "throw_accuracy"]), ("WR", ["speed", "catching"])],
    # Play Action
    "dual_boot": [("QB", ["throw_accuracy", "agility"]), ("WR", ["route_running", "catching"])],
    # Pro formation (Pro-only plays)
    "pro_fb_trap": [("RB", ["vision", "strength"]), ("OL", ["run_blocking", "strength"])],
    "pro_iso": [("RB", ["vision", "break_tackle", "strength"]), ("OL", ["run_blocking", "strength"])],
    "pro_dive": [("RB", ["vision", "speed"]), ("OL", ["run_blocking"])],
    "pro_power_g": [("RB", ["speed", "strength", "vision"]), ("OL", ["run_blocking"])],
    "pro_toss_sweep": [("RB", ["speed", "agility"]), ("OL", ["run_blocking"])],
    "pro_counter": [("RB", ["vision", "agility", "speed"]), ("OL", ["run_blocking"])],
    "pro_slants": [("QB", ["throw_accuracy", "decisions"]), ("WR", ["route_running", "catching", "agility"])],
    "pro_hitches": [("QB", ["throw_accuracy", "decisions"]), ("WR", ["route_running", "catching"])],
    "pro_hank": [("QB", ["throw_accuracy", "decisions"]), ("WR", ["route_running", "catching"])],
    "pro_te_post": [("QB", ["throw_accuracy", "throw_power"]), ("TE", ["route_running", "catching"])],
    "pro_levels": [("QB", ["throw_accuracy", "decisions"]), ("WR", ["route_running", "catching"])],
    "pro_curl_flat": [("QB", ["throw_accuracy", "decisions"]), ("WR", ["route_running", "catching"])],
    "pro_deep_post": [("QB", ["throw_power", "throw_accuracy"]), ("WR", ["speed", "route_running", "catching"])],
    "pro_verticals": [("QB", ["throw_power", "throw_accuracy"]), ("WR", ["speed", "catching", "route_running"])],
    "pro_post_corner": [("QB", ["throw_power", "throw_accuracy"]), ("WR", ["speed", "route_running", "catching"])],
    "pro_flood": [("QB", ["throw_accuracy", "agility"]), ("WR", ["route_running", "catching"])],
    "pro_boot": [("QB", ["throw_accuracy", "agility"]), ("WR", ["route_running", "catching"])],
    # Twins formation (Twins-only plays)
    "twins_iso": [("RB", ["vision", "break_tackle", "strength"]), ("OL", ["run_blocking", "strength"])],
    "twins_trap": [("RB", ["vision", "strength"]), ("OL", ["run_blocking", "strength"])],
    "twins_dive": [("RB", ["vision", "speed"]), ("OL", ["run_blocking"])],
    "twins_toss_st": [("RB", ["speed", "agility"]), ("OL", ["run_blocking"])],
    "twins_toss_wk": [("RB", ["speed", "agility"]), ("OL", ["run_blocking"])],
    "twins_power_g": [("RB", ["speed", "strength", "vision"]), ("OL", ["run_blocking"])],
    "twins_dbl_slants": [("QB", ["throw_accuracy", "decisions"]), ("WR", ["route_running", "catching", "agility"])],
    "twins_hitches": [("QB", ["throw_accuracy", "decisions"]), ("WR", ["route_running", "catching"])],
    "twins_slant_flat": [("QB", ["throw_accuracy", "decisions"]), ("WR", ["route_running", "catching"])],
    "twins_sprint_smash": [("QB", ["throw_accuracy", "decisions"]), ("WR", ["route_running", "catching"])],
    "twins_flood": [("QB", ["throw_accuracy", "decisions"]), ("WR", ["route_running", "catching"])],
    "twins_dagger": [("QB", ["throw_accuracy", "throw_power"]), ("WR", ["route_running", "catching", "speed"])],
    "twins_post_wheel": [("QB", ["throw_power", "throw_accuracy"]), ("WR", ["speed", "route_running", "catching"])],
    "twins_post_dig": [("QB", ["throw_power", "throw_accuracy"]), ("WR", ["route_running", "catching", "speed"])],
    "twins_verticals": [("QB", ["throw_power", "throw_accuracy"]), ("WR", ["speed", "catching", "route_running"])],
    "twins_boot": [("QB", ["throw_accuracy", "agility"]), ("WR", ["route_running", "catching"])],
    "twins_flood_pa": [("QB", ["throw_accuracy", "agility"]), ("WR", ["route_running", "catching"])],
    # Trey Wing (1 RB, 2 TE, 2 WR)
    "trey_wing_inside_zone": [("RB", ["vision", "speed", "break_tackle"]), ("OL", ["run_blocking", "strength"])],
    "trey_wing_power": [("RB", ["vision", "strength", "break_tackle"]), ("OL", ["run_blocking", "strength"])],
    "trey_wing_counter": [("RB", ["vision", "agility", "speed"]), ("OL", ["run_blocking", "strength"])],
    "trey_wing_stretch": [("RB", ["speed", "vision"]), ("OL", ["run_blocking"])],
    "trey_wing_speed_option": [("QB", ["speed", "agility"]), ("RB", ["speed", "elusiveness"])],
    "trey_wing_counter_sweep": [("RB", ["speed", "agility", "vision"]), ("OL", ["run_blocking"])],
    "trey_wing_stick": [("QB", ["throw_accuracy", "decisions"]), ("TE", ["route_running", "catching"]), ("WR", ["route_running", "catching"])],
    "trey_wing_slant_flat": [("QB", ["throw_accuracy", "decisions"]), ("WR", ["route_running", "catching", "agility"]), ("TE", ["route_running", "catching"])],
    "trey_wing_hitches": [("QB", ["throw_accuracy", "decisions"]), ("WR", ["route_running", "catching"])],
    "trey_wing_mesh": [("QB", ["throw_accuracy", "decisions"]), ("WR", ["route_running", "catching", "agility"]), ("TE", ["route_running", "catching"])],
    "trey_wing_drive": [("QB", ["throw_accuracy", "decisions"]), ("WR", ["route_running", "catching"]), ("TE", ["route_running", "catching"])],
    "trey_wing_y_cross": [("QB", ["throw_accuracy", "throw_power"]), ("TE", ["route_running", "catching"]), ("WR", ["route_running", "catching", "speed"])],
    "trey_wing_play_action_post": [("QB", ["throw_accuracy", "throw_power", "agility"]), ("TE", ["route_running", "catching"]), ("WR", ["speed", "route_running", "catching"])],
    "trey_wing_double_move_sluggo": [("QB", ["throw_power", "throw_accuracy"]), ("WR", ["route_running", "speed", "catching"])],
    "trey_wing_4_verts": [("QB", ["throw_power", "throw_accuracy"]), ("WR", ["speed", "catching", "route_running"]), ("TE", ["route_running", "catching"])],
    # Wing (1 RB, 2 TE, 2 WR)
    "wing_belly": [("RB", ["vision", "strength", "break_tackle"]), ("OL", ["run_blocking", "strength"])],
    "wing_trap": [("RB", ["vision", "strength"]), ("OL", ["run_blocking", "strength"])],
    "wing_counter": [("RB", ["vision", "agility", "speed"]), ("OL", ["run_blocking", "strength"])],
    "wing_buck_sweep": [("RB", ["speed", "agility", "vision"]), ("OL", ["run_blocking"])],
    "wing_jet_sweep": [("WR", ["speed", "agility", "elusiveness"]), ("OL", ["run_blocking"])],
    "wing_reverse": [("WR", ["speed", "agility", "vision"]), ("RB", ["speed", "blocking"])],
    "wing_stick": [("QB", ["throw_accuracy", "decisions"]), ("TE", ["route_running", "catching"]), ("WR", ["route_running", "catching"])],
    "wing_slant_flat": [("QB", ["throw_accuracy", "decisions"]), ("WR", ["route_running", "catching", "agility"]), ("TE", ["route_running", "catching"])],
    "wing_quick_out": [("QB", ["throw_accuracy", "decisions"]), ("WR", ["route_running", "speed", "catching"])],
    "wing_flood": [("QB", ["throw_accuracy", "decisions"]), ("WR", ["route_running", "catching"]), ("TE", ["route_running", "catching"])],
    "wing_smash": [("QB", ["throw_accuracy", "throw_power"]), ("WR", ["route_running", "catching"]), ("TE", ["route_running", "catching"])],
    "wing_boot_cross": [("QB", ["throw_accuracy", "agility"]), ("WR", ["route_running", "catching"]), ("TE", ["route_running", "catching"])],
    "wing_post_wheel": [("QB", ["throw_power", "throw_accuracy"]), ("WR", ["speed", "route_running", "catching"]), ("RB", ["speed", "catching"])],
    "wing_wheel_route": [("QB", ["throw_accuracy", "throw_power"]), ("RB", ["speed", "catching", "agility"]), ("TE", ["route_running", "catching"])],
    "wing_flood_shot": [("QB", ["throw_power", "throw_accuracy"]), ("WR", ["speed", "route_running", "catching"]), ("TE", ["route_running", "catching"])],
    # Flexbone (3 RB, 0 TE, 2 WR)
    "flexbone_fullback_dive": [("RB", ["vision", "strength", "break_tackle"]), ("OL", ["run_blocking", "strength"])],
    "flexbone_midline": [("QB", ["decisions", "speed", "agility"]), ("RB", ["vision", "strength"]), ("OL", ["run_blocking"])],
    "flexbone_triple_option_dive": [("QB", ["decisions", "agility"]), ("RB", ["vision", "speed"]), ("OL", ["run_blocking"])],
    "flexbone_rocket_toss": [("RB", ["speed", "agility", "elusiveness"]), ("OL", ["run_blocking"])],
    "flexbone_speed_option": [("QB", ["speed", "agility", "decisions"]), ("RB", ["speed", "elusiveness"])],
    "flexbone_triple_option_pitch": [("QB", ["decisions", "speed", "agility"]), ("RB", ["speed", "vision", "elusiveness"])],
    "flexbone_quick_hitch": [("QB", ["throw_accuracy", "decisions"]), ("WR", ["route_running", "catching"])],
    "flexbone_play_action_hitch": [("QB", ["throw_accuracy", "agility"]), ("WR", ["route_running", "catching"])],
    "flexbone_rocket_screen": [("QB", ["throw_accuracy", "decisions"]), ("RB", ["speed", "catching", "agility"]), ("WR", ["blocking"])],
    "flexbone_play_action_post": [("QB", ["throw_power", "throw_accuracy", "agility"]), ("WR", ["speed", "route_running", "catching"])],
    "flexbone_seam_read": [("QB", ["throw_accuracy", "decisions"]), ("WR", ["route_running", "catching"])],
    "flexbone_switch_verticals_medium": [("QB", ["throw_power", "throw_accuracy"]), ("WR", ["speed", "route_running", "catching"])],
    "flexbone_play_action_go": [("QB", ["throw_power", "throw_accuracy", "agility"]), ("WR", ["speed", "route_running", "catching"])],
    "flexbone_switch_verticals_deep": [("QB", ["throw_power", "throw_accuracy"]), ("WR", ["speed", "route_running", "catching"])],
    "flexbone_rocket_play_action": [("QB", ["throw_accuracy", "agility"]), ("WR", ["route_running", "speed", "catching"]), ("RB", ["speed", "catching"])],
    # Double Wing (3 RB, 2 TE, 0 WR)
    "double_wing_wedge": [("RB", ["strength", "vision", "break_tackle"]), ("OL", ["run_blocking", "strength"])],
    "double_wing_trap": [("RB", ["vision", "strength"]), ("OL", ["run_blocking", "strength"])],
    "double_wing_counter": [("RB", ["vision", "agility", "speed"]), ("OL", ["run_blocking", "strength"])],
    "double_wing_sweep": [("RB", ["speed", "agility", "vision"]), ("OL", ["run_blocking"])],
    "double_wing_toss_crack": [("RB", ["speed", "agility"]), ("OL", ["run_blocking"]), ("TE", ["blocking"])],
    "double_wing_counter_sweep": [("RB", ["speed", "agility", "vision"]), ("OL", ["run_blocking"])],
    "double_wing_quick_slant": [("QB", ["throw_accuracy", "decisions"]), ("TE", ["route_running", "catching"])],
    "double_wing_boot_flat": [("QB", ["throw_accuracy", "agility"]), ("TE", ["route_running", "catching"])],
    "double_wing_te_pop_pass": [("QB", ["throw_accuracy", "decisions"]), ("TE", ["route_running", "catching"])],
    "double_wing_boot_flood": [("QB", ["throw_accuracy", "agility"]), ("TE", ["route_running", "catching"])],
    "double_wing_te_corner": [("QB", ["throw_accuracy", "throw_power"]), ("TE", ["route_running", "catching"])],
    "double_wing_post_wheel": [("QB", ["throw_power", "throw_accuracy"]), ("TE", ["route_running", "catching"]), ("RB", ["speed", "catching"])],
    "double_wing_te_seam": [("QB", ["throw_power", "throw_accuracy"]), ("TE", ["route_running", "catching", "speed"])],
    "double_wing_post_corner": [("QB", ["throw_power", "throw_accuracy"]), ("TE", ["route_running", "catching"])],
    "double_wing_te_pop_go": [("QB", ["throw_power", "throw_accuracy"]), ("TE", ["route_running", "speed", "catching"])],
    # Power I (3 RB, 1 TE, 1 WR)
    "power_i_iso": [("RB", ["vision", "break_tackle", "strength"]), ("OL", ["run_blocking", "strength"])],
    "power_i_power": [("RB", ["vision", "strength", "break_tackle"]), ("OL", ["run_blocking", "strength"])],
    "power_i_counter": [("RB", ["vision", "agility", "speed"]), ("OL", ["run_blocking", "strength"])],
    "power_i_toss_sweep": [("RB", ["speed", "agility"]), ("OL", ["run_blocking"])],
    "power_i_stretch": [("RB", ["speed", "vision"]), ("OL", ["run_blocking"])],
    "power_i_counter_toss": [("RB", ["speed", "agility", "vision"]), ("OL", ["run_blocking"])],
    "power_i_stick": [("QB", ["throw_accuracy", "decisions"]), ("TE", ["route_running", "catching"]), ("WR", ["route_running", "catching"])],
    "power_i_slant_flat": [("QB", ["throw_accuracy", "decisions"]), ("WR", ["route_running", "catching", "agility"]), ("TE", ["route_running", "catching"])],
    "power_i_quick_out": [("QB", ["throw_accuracy", "decisions"]), ("WR", ["route_running", "speed", "catching"])],
    "power_i_flood": [("QB", ["throw_accuracy", "decisions"]), ("WR", ["route_running", "catching"]), ("TE", ["route_running", "catching"])],
    "power_i_curl_flat": [("QB", ["throw_accuracy", "decisions"]), ("WR", ["route_running", "catching"]), ("TE", ["route_running", "catching"])],
    "power_i_dig": [("QB", ["throw_accuracy", "throw_power"]), ("WR", ["route_running", "catching", "speed"])],
    "power_i_play_action_post": [("QB", ["throw_power", "throw_accuracy", "agility"]), ("TE", ["route_running", "catching"]), ("WR", ["speed", "route_running", "catching"])],
    "power_i_go_route": [("QB", ["throw_power", "throw_accuracy"]), ("WR", ["speed", "route_running", "catching"])],
    "power_i_deep_cross": [("QB", ["throw_power", "throw_accuracy"]), ("WR", ["route_running", "catching", "speed"])],
    # Wing T (3 RB, 1 TE, 1 WR)
    "wing_t_belly": [("RB", ["vision", "strength", "break_tackle"]), ("OL", ["run_blocking", "strength"])],
    "wing_t_trap": [("RB", ["vision", "strength"]), ("OL", ["run_blocking", "strength"])],
    "wing_t_counter": [("RB", ["vision", "agility", "speed"]), ("OL", ["run_blocking", "strength"])],
    "wing_t_buck_sweep": [("RB", ["speed", "agility", "vision"]), ("OL", ["run_blocking"])],
    "wing_t_jet_sweep": [("RB", ["speed", "agility", "elusiveness"]), ("OL", ["run_blocking"])],
    "wing_t_waggle_run": [("RB", ["speed", "agility", "vision"]), ("QB", ["speed", "agility"])],
    "wing_t_waggle_quick": [("QB", ["throw_accuracy", "agility"]), ("WR", ["route_running", "catching"]), ("TE", ["route_running", "catching"])],
    "wing_t_boot_pass": [("QB", ["throw_accuracy", "agility"]), ("TE", ["route_running", "catching"]), ("WR", ["route_running", "catching"])],
    "wing_t_quick_screen": [("QB", ["throw_accuracy", "decisions"]), ("RB", ["speed", "catching"]), ("WR", ["blocking"])],
    "wing_t_waggle": [("QB", ["throw_accuracy", "agility"]), ("WR", ["route_running", "catching"]), ("TE", ["route_running", "catching"])],
    "wing_t_flood": [("QB", ["throw_accuracy", "decisions"]), ("WR", ["route_running", "catching"]), ("TE", ["route_running", "catching"])],
    "wing_t_boot_drag": [("QB", ["throw_accuracy", "agility"]), ("TE", ["route_running", "catching"]), ("WR", ["route_running", "catching"])],
    "wing_t_waggle_post": [("QB", ["throw_power", "throw_accuracy", "agility"]), ("WR", ["speed", "route_running", "catching"]), ("TE", ["route_running", "catching"])],
    "wing_t_post_wheel": [("QB", ["throw_power", "throw_accuracy"]), ("WR", ["speed", "route_running", "catching"]), ("TE", ["route_running", "catching"])],
    "wing_t_half_roll_shot": [("QB", ["throw_power", "throw_accuracy", "agility"]), ("WR", ["speed", "route_running", "catching"])],
    # Doubles (1 RB, 1 TE, 3 WR)
    "doubles_inside_zone": [("RB", ["vision", "speed", "break_tackle"]), ("OL", ["run_blocking", "strength"])],
    "doubles_duo": [("RB", ["vision", "strength"]), ("OL", ["run_blocking", "strength"])],
    "doubles_split_zone": [("RB", ["vision", "speed"]), ("OL", ["run_blocking"])],
    "doubles_outside_zone": [("RB", ["speed", "agility", "vision"]), ("OL", ["run_blocking"])],
    "doubles_jet_sweep": [("WR", ["speed", "agility", "elusiveness"]), ("OL", ["run_blocking"])],
    "doubles_orbit_motion_sweep": [("RB", ["speed", "agility", "vision"]), ("WR", ["speed", "agility"]), ("OL", ["run_blocking"])],
    "doubles_stick": [("QB", ["throw_accuracy", "decisions"]), ("TE", ["route_running", "catching"]), ("WR", ["route_running", "catching"])],
    "doubles_slant_flat": [("QB", ["throw_accuracy", "decisions"]), ("WR", ["route_running", "catching", "agility"]), ("TE", ["route_running", "catching"])],
    "doubles_bubble_screen": [("WR", ["catching", "agility", "speed"]), ("QB", ["throw_accuracy"])],
    "doubles_mesh": [("QB", ["throw_accuracy", "decisions"]), ("WR", ["route_running", "catching", "agility"]), ("TE", ["route_running", "catching"])],
    "doubles_smash": [("QB", ["throw_accuracy", "decisions"]), ("WR", ["route_running", "catching"])],
    "doubles_y_cross": [("QB", ["throw_accuracy", "throw_power"]), ("TE", ["route_running", "catching"]), ("WR", ["route_running", "catching", "speed"])],
    "doubles_4_verticals": [("QB", ["throw_power", "throw_accuracy"]), ("WR", ["speed", "catching", "route_running"]), ("TE", ["route_running", "catching"])],
    "doubles_post_dig_shot": [("QB", ["throw_power", "throw_accuracy"]), ("WR", ["route_running", "catching", "speed"])],
    "doubles_fade_go": [("QB", ["throw_power", "throw_accuracy"]), ("WR", ["speed", "route_running", "catching"])],
}

# Defense: zone coverage = DB coverage/speed; man = DB coverage/agility; pressure = DL pass_rush, LB blitz
PLAY_DEFENSIVE_WEIGHTS: Dict[str, PlaySpec] = {
    # Zones - coverage and range
    "43_cover_3": [("DB", ["coverage", "speed", "football_iq"]), ("LB", ["coverage", "run_defense"])],
    "43_cover_4": [("DB", ["coverage", "speed"]), ("LB", ["coverage"])],
    "43_cover_2": [("DB", ["coverage", "speed"]), ("LB", ["coverage", "run_defense"])],
    # Man - DBs on an island
    "43_1_strong": [("DB", ["coverage", "agility", "speed"])],
    "43_1_weak": [("DB", ["coverage", "agility"]), ("LB", ["coverage"])],
    # Zone Pressure - DL + zone behind
    "43_saw_cover_3": [("DL", ["pass_rush", "run_defense"]), ("LB", ["blitz", "run_defense"]), ("DB", ["coverage"])],
    # Man Pressure - DL pass rush, DBs in man
    "43_mag_cover_1": [("DL", ["pass_rush"]), ("DB", ["coverage", "agility"])],
    "43_spark_cover_0": [("DL", ["pass_rush"]), ("LB", ["blitz", "pass_rush"]), ("DB", ["coverage", "speed"])],
    # Nickel formation
    "nickel_cover_4": [("DB", ["coverage", "speed"]), ("LB", ["coverage", "run_defense"])],
    "nickel_cover_3": [("DB", ["coverage", "speed", "football_iq"]), ("LB", ["coverage", "run_defense"])],
    "nickel_cover_2": [("DB", ["coverage", "speed"]), ("LB", ["coverage"])],
    "nickel_1_rat": [("DB", ["coverage", "agility", "speed"])],
    "nickel_2_man": [("DB", ["coverage", "agility"]), ("LB", ["coverage"])],
    "nickel_favre": [("DL", ["pass_rush", "run_defense"]), ("LB", ["blitz", "coverage"]), ("DB", ["coverage"])],
    "nickel_war_trey": [("DL", ["pass_rush"]), ("LB", ["blitz", "run_defense"]), ("DB", ["coverage"])],
    "nickel_war_blue": [("DL", ["pass_rush"]), ("DB", ["coverage", "agility"])],
    "nickel_saw_blue": [("DL", ["pass_rush"]), ("LB", ["blitz"]), ("DB", ["coverage", "agility"])],
}

# Position key -> roster positions that belong to this group
POSITION_GROUPS: Dict[str, Tuple[str, ...]] = {
    "QB": ("QB",),
    "RB": ("RB",),
    "WR": ("WR",),
    "TE": ("TE",),
    "OL": ("OL",),
    "DL": ("DE", "DT"),
    "LB": ("LB",),
    "DB": ("CB", "S"),
}


def _get_players_at_position(roster: List[Any], position_key: str) -> List[Any]:
    """Return players whose primary (or secondary for two-way) matches the position group."""
    positions = POSITION_GROUPS.get(position_key, (position_key,))
    out = []
    for p in roster:
        pos = getattr(p, "position", None)
        sec = getattr(p, "secondary_position", None)
        if pos in positions or sec in positions:
            out.append(p)
    return out


def _rate_player_for_attrs(player: Any, attr_names: List[str]) -> float:
    """Average of the given attributes for this player (RATING_ATTR_MIN–RATING_ATTR_MAX scale)."""
    total = 0
    count = 0
    for name in attr_names:
        val = getattr(player, name, None)
        if val is not None:
            total += max(RATING_ATTR_MIN, min(RATING_ATTR_MAX, val))
            count += 1
    return total / count if count else 50.0


def get_position_rating(team: Any, position_key: str, attr_names: List[str]) -> float:
    """
    Rate how well this team's personnel at the given position (group) fit the attributes.
    Uses best player for single-position groups, average for multi-position groups (DL, DB).
    Returns 1-100 (50 if no players).
    """
    roster = getattr(team, "roster", [])
    if not roster:
        return 50.0
    players = _get_players_at_position(roster, position_key)
    if not players:
        return 50.0
    # For single position (QB, RB, etc.) use best player; for DL/LB/DB use average of group
    if position_key in ("QB", "RB", "WR", "TE", "OL"):
        best = max(players, key=lambda p: _rate_player_for_attrs(p, attr_names))
        return _rate_player_for_attrs(best, attr_names)
    # DL, LB, DB: average the attribute rating across the group (so good DL boosts pressure plays)
    ratings = [_rate_player_for_attrs(p, attr_names) for p in players]
    return sum(ratings) / len(ratings) if ratings else 50.0


def get_offensive_play_score(team: Any, play_id: str) -> float:
    """
    Score 1-100 for how well this team's roster fits the offensive play.
    Higher = more likely to call this play when that category is chosen.
    """
    spec = PLAY_OFFENSIVE_WEIGHTS.get(play_id)
    if not spec:
        return 50.0
    ratings = [get_position_rating(team, pos, attrs) for (pos, attrs) in spec]
    return sum(ratings) / len(ratings) if ratings else 50.0


def _defensive_weight_spec(play_id: str):
    """Resolve weight table entry, including cloned sub-package plays (Dime, 5-2, stack, 6-2)."""
    spec = PLAY_DEFENSIVE_WEIGHTS.get(play_id)
    if spec is not None:
        return spec
    if play_id.startswith("dime_"):
        return PLAY_DEFENSIVE_WEIGHTS.get(play_id[5:])
    if play_id.startswith("52_"):
        return PLAY_DEFENSIVE_WEIGHTS.get(play_id[3:])
    if play_id.startswith("stk_"):
        return PLAY_DEFENSIVE_WEIGHTS.get(play_id[4:])
    if play_id.startswith("stk3h_"):
        return PLAY_DEFENSIVE_WEIGHTS.get(play_id[6:])
    if play_id.startswith("62_"):
        return PLAY_DEFENSIVE_WEIGHTS.get(play_id[3:])
    return None


def get_defensive_play_score(team: Any, play_id: str) -> float:
    """
    Score 1-100 for how well this team's roster fits the defensive play.
    Zone/Man coverage plays favor DB coverage and speed; pressure plays favor DL pass_rush and LB blitz.
    """
    spec = _defensive_weight_spec(play_id)
    if not spec:
        return 50.0
    ratings = [get_position_rating(team, pos, attrs) for (pos, attrs) in spec]
    return sum(ratings) / len(ratings) if ratings else 50.0
