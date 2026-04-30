"""
Depth chart system for high school football.
Handles two-way players (on both offense and defense) and fatigue-based substitution.
"""

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Dict, List, Optional, Tuple

if TYPE_CHECKING:
    from models.player import Player
    from models.team import Team


def _format_player_line(p: "Player", include_grades: bool = True) -> str:
    """Format a depth chart line: name, secondary pos, and Overall | Off | Def grades."""
    from systems import team_ratings
    two_way = f" / {p.secondary_position}" if p.secondary_position else ""
    if not include_grades:
        return f"{p.name}{two_way}"
    overall = team_ratings.calculate_player_overall(p)
    off = team_ratings.calculate_player_offense_overall(p)
    def_ = team_ratings.calculate_player_defense_overall(p)
    return f"{p.name}{two_way} (Overall {overall} | Off {off} | Def {def_})"

# Position groupings for offense/defense depth charts
OFFENSE_POSITIONS = ["QB", "RB", "WR", "OL", "TE"]
DEFENSE_POSITIONS = ["DE", "DT", "LB", "CB", "S"]
SPECIALIST_POSITIONS = ["K", "P"]

# Max depth slots per position (typical high school)
POSITION_DEPTH = {
    "QB": 2, "RB": 4, "WR": 6, "OL": 8, "TE": 2,
    "DE": 4, "DT": 3, "LB": 5, "CB": 4, "S": 3,
    "K": 1, "P": 1,
}

# Two-way conversion thresholds when filling opposite-side depth.
# Example: strong offense player can be placed on defense (or vice versa)
# even without an explicit secondary position, if they grade well enough.
TWO_WAY_SIDE_OVERALL_THRESHOLD = 68
TWO_WAY_POSITION_FIT_THRESHOLD = 62

# Fatigue thresholds
FATIGUE_SUB_THRESHOLD = 30   # Sub out when fatigue drops below this
FATIGUE_INITIAL = 100
FATIGUE_DRAIN_PER_PLAY = 2   # Base drain; reduced by stamina


def _position_rating_offense(player: "Player", pos: str) -> float:
    """Rating for a player at an offensive position (1-100)."""
    if pos == "QB":
        return (player.throw_power + player.throw_accuracy + player.decisions + player.football_iq) / 4
    if pos == "RB":
        return (player.speed + player.break_tackle + player.vision + player.ball_security + player.catching) / 5
    if pos in ("WR", "TE"):
        return (player.catching + player.route_running + player.speed + player.agility) / 4
    if pos == "OL":
        return (player.run_blocking + player.pass_blocking + player.strength) / 3
    return 0


def _position_rating_defense(player: "Player", pos: str) -> float:
    """Rating for a player at a defensive position (1-100)."""
    if pos in ("DE", "DT"):
        return (player.pass_rush + player.run_defense + player.block_shedding + player.strength) / 4
    if pos == "LB":
        return (player.tackling + player.pursuit + player.coverage + player.run_defense) / 4
    if pos in ("CB", "S"):
        return (player.coverage + player.speed + player.agility + player.tackling) / 4
    return 0


def _position_rating_specialist(player: "Player", pos: str) -> float:
    """Rating for K/P."""
    if pos in ("K", "P"):
        return (player.kick_power + player.kick_accuracy) / 2
    return 0


def _can_play_position(player: "Player", pos: str) -> bool:
    """Check if player can play this position (primary or secondary)."""
    return player.position == pos or player.secondary_position == pos


def _best_offense_position(player: "Player") -> str:
    """Best offensive position by fit rating."""
    return max(OFFENSE_POSITIONS, key=lambda pos: _position_rating_offense(player, pos))


def _best_defense_position(player: "Player") -> str:
    """Best defensive position by fit rating."""
    return max(DEFENSE_POSITIONS, key=lambda pos: _position_rating_defense(player, pos))


def _has_side_position(player: "Player", side: str) -> bool:
    """Whether player has a tagged position on the given side."""
    positions = OFFENSE_POSITIONS if side == "offense" else DEFENSE_POSITIONS
    return (player.position in positions) or ((player.secondary_position or "") in positions)


def _sort_key_for_depth(player: "Player", pos: str, side: str, natural: bool) -> tuple:
    """
    Sort natural position players first, then by overall, then by position fit.
    'overall' is primary ranking to satisfy "best overall starts at position".
    """
    from systems import team_ratings

    overall = (
        team_ratings.calculate_player_offense_overall(player)
        if side == "offense"
        else team_ratings.calculate_player_defense_overall(player)
    )
    if side == "offense":
        pos_fit = _position_rating_offense(player, pos)
    else:
        pos_fit = _position_rating_defense(player, pos)
    return (1 if natural else 0, overall, pos_fit)


def _force_fill_position(team: "Team", selected: List["Player"], pos: str, side: str, slots: int) -> List["Player"]:
    """
    Emergency fill when a position still lacks depth after natural + thresholded two-way candidates.
    For OL specifically, prioritize DL conversions next so OL reaches 8.
    """
    from systems import team_ratings

    if len(selected) >= slots:
        return selected

    roster = team.roster or []
    remaining = [p for p in roster if p not in selected]
    pool: List["Player"] = []

    if side == "offense":
        # OL emergency: pull best DL bodies first if available
        if pos == "OL":
            dl = [p for p in remaining if p.position in ("DE", "DT") or p.secondary_position in ("DE", "DT")]
            dl.sort(
                key=lambda p: (
                    team_ratings.calculate_player_offense_overall(p),
                    _position_rating_offense(p, "OL"),
                ),
                reverse=True,
            )
            for p in dl:
                if p not in pool:
                    pool.append(p)

        # Then general best offense-side conversions by OL fit/overall
        remaining2 = [p for p in remaining if p not in pool]
        remaining2.sort(
            key=lambda p: (
                team_ratings.calculate_player_offense_overall(p),
                _position_rating_offense(p, pos),
            ),
            reverse=True,
        )
        pool.extend(remaining2)
    else:
        # Defense emergency fill by defense overall + position fit
        remaining.sort(
            key=lambda p: (
                team_ratings.calculate_player_defense_overall(p),
                _position_rating_defense(p, pos),
            ),
            reverse=True,
        )
        pool.extend(remaining)

    for p in pool:
        if p not in selected:
            selected.append(p)
        if len(selected) >= slots:
            break
    return selected


def _two_way_conversion_candidates(team: "Team", pos: str, side: str) -> List["Player"]:
    """
    Cross-side conversion candidates:
    - offense chart can include defense players who grade well on offense
    - defense chart can include offense players who grade well on defense
    Player is only considered at their BEST converted position.
    """
    from systems import team_ratings

    roster = team.roster or []
    out: List["Player"] = []
    for p in roster:
        if _can_play_position(p, pos):
            continue  # already a natural candidate for this position

        if side == "offense":
            # Consider defense-native players converting to offense
            if _has_side_position(p, "offense"):
                continue
            side_overall = team_ratings.calculate_player_offense_overall(p)
            best_pos = _best_offense_position(p)
            fit = _position_rating_offense(p, best_pos)
        else:
            # Consider offense-native players converting to defense
            if _has_side_position(p, "defense"):
                continue
            side_overall = team_ratings.calculate_player_defense_overall(p)
            best_pos = _best_defense_position(p)
            fit = _position_rating_defense(p, best_pos)

        if (
            best_pos == pos
            and side_overall >= TWO_WAY_SIDE_OVERALL_THRESHOLD
            and fit >= TWO_WAY_POSITION_FIT_THRESHOLD
        ):
            out.append(p)
    return out


@dataclass
class DepthChart:
    """Depth chart: ranked players by position for offense, defense, and specialists."""

    offense: Dict[str, List["Player"]] = field(default_factory=dict)
    defense: Dict[str, List["Player"]] = field(default_factory=dict)
    specialists: Dict[str, List["Player"]] = field(default_factory=dict)

    def get_starter(self, position: str, side: str, slot: int = 0) -> Optional["Player"]:
        """Get player at position/side/depth. side = 'offense', 'defense', 'specialists'."""
        chart = getattr(self, side, {})
        players = chart.get(position, [])
        if 0 <= slot < len(players):
            return players[slot]
        return None

    def get_next_available(
        self, position: str, side: str, exclude: Optional["Player"] = None, exclude_fatigued: Optional[set] = None
    ) -> Optional["Player"]:
        """Get next available player at position (for substitution). exclude_fatigued: set of player ids (int) to skip."""
        chart = getattr(self, side, {})
        players = chart.get(position, [])
        fatigued_ids = exclude_fatigued if exclude_fatigued is not None else set()
        for p in players:
            if p is exclude or (fatigued_ids and id(p) in fatigued_ids):
                continue
            return p
        return None

    def to_text(self, team: Optional["Team"] = None) -> str:
        """Format depth chart as readable text. If team provided, appends TWO-WAY PLAYERS section."""
        lines = []
        lines.append("OFFENSE")
        lines.append("-" * 50)
        for pos in OFFENSE_POSITIONS:
            players = self.offense.get(pos, [])
            limit = POSITION_DEPTH.get(pos, 4)
            for i, p in enumerate(players[:limit], 1):
                lines.append(f"  {pos}{i}: {_format_player_line(p)}")
        lines.append("")
        lines.append("DEFENSE")
        lines.append("-" * 50)
        for pos in DEFENSE_POSITIONS:
            players = self.defense.get(pos, [])
            limit = POSITION_DEPTH.get(pos, 4)
            for i, p in enumerate(players[:limit], 1):
                lines.append(f"  {pos}{i}: {_format_player_line(p)}")
        lines.append("")
        lines.append("SPECIALISTS")
        lines.append("-" * 50)
        for pos in SPECIALIST_POSITIONS:
            players = self.specialists.get(pos, [])
            for i, p in enumerate(players, 1):
                lines.append(f"  {pos}{i}: {_format_player_line(p, include_grades=False)}")
        if team and team.roster:
            from systems import team_ratings
            offense_players = [p for players in self.offense.values() for p in players]
            defense_players = [p for players in self.defense.values() for p in players]
            offense_ids = {id(p) for p in offense_players}
            defense_ids = {id(p) for p in defense_players}
            # Two-way = appears on at least one offense slot and one defense slot.
            # This includes explicit two-way tags and strong cross-side conversions.
            two_way_players = [p for p in team.roster if id(p) in offense_ids and id(p) in defense_ids]
            if two_way_players:
                lines.append("")
                lines.append("TWO-WAY PLAYERS")
                lines.append("-" * 50)
                for p in sorted(two_way_players, key=lambda x: (
                    -team_ratings.calculate_player_overall(x),
                    -team_ratings.calculate_player_offense_overall(x),
                    -team_ratings.calculate_player_defense_overall(x),
                )):
                    overall = team_ratings.calculate_player_overall(p)
                    off = team_ratings.calculate_player_offense_overall(p)
                    def_ = team_ratings.calculate_player_defense_overall(p)
                    off_pos = team_ratings.get_player_offense_position(p) or "?"
                    def_pos = team_ratings.get_player_defense_position(p) or "?"
                    lines.append(f"  {p.name}: Overall {overall} | Off {off} ({off_pos}) | Def {def_} ({def_pos})")
        return "\n".join(lines)


def _roster_by_name(roster: List["Player"]) -> Dict[str, "Player"]:
    """Map player name -> Player for lookup."""
    return {p.name: p for p in roster if p and getattr(p, "name", None)}


def _apply_user_depth_order(
    team: "Team",
    pos: str,
    side: str,
    auto_selected: List["Player"],
    roster: List["Player"],
) -> List["Player"]:
    """
    If team has depth_chart_order for this position, use it. Otherwise return auto_selected.
    User order: list of player names. We resolve to Player objects and fill remaining with auto.
    """
    order = getattr(team, "depth_chart_order", None) or {}
    names = order.get(pos)
    if not names or not isinstance(names, list):
        return auto_selected

    by_name = _roster_by_name(roster)
    selected: List["Player"] = []
    for n in names:
        if isinstance(n, str) and n.strip():
            p = by_name.get(n.strip())
            if p and p not in selected:
                selected.append(p)

    slots = POSITION_DEPTH.get(pos, 4)
    if len(selected) >= slots:
        return selected[:slots]

    used = set(id(p) for p in selected)
    for p in auto_selected:
        if id(p) not in used:
            selected.append(p)
            used.add(id(p))
        if len(selected) >= slots:
            break
    return selected[:slots]


def build_depth_chart(team: "Team") -> DepthChart:
    """
    Build depth chart from roster. Two-way players appear on both offense and defense.
    Players are ranked by position rating (best first).
    When team.depth_chart_order is set, user order is used for each position.
    """
    dc = DepthChart()
    roster = team.roster or []

    for pos in OFFENSE_POSITIONS:
        natural = [
            p for p in roster
            if _can_play_position(p, pos) and _position_rating_offense(p, pos) > 0
        ]
        natural.sort(key=lambda p: _sort_key_for_depth(p, pos, "offense", natural=True), reverse=True)

        slots = POSITION_DEPTH.get(pos, 4)
        selected = natural[:slots]

        if len(selected) < slots:
            cross = _two_way_conversion_candidates(team, pos, "offense")
            cross.sort(key=lambda p: _sort_key_for_depth(p, pos, "offense", natural=False), reverse=True)
            for p in cross:
                if p not in selected:
                    selected.append(p)
                if len(selected) >= slots:
                    break

        selected = _force_fill_position(team, selected, pos, "offense", slots)
        dc.offense[pos] = _apply_user_depth_order(team, pos, "offense", selected, roster)

    for pos in DEFENSE_POSITIONS:
        natural = [
            p for p in roster
            if _can_play_position(p, pos) and _position_rating_defense(p, pos) > 0
        ]
        natural.sort(key=lambda p: _sort_key_for_depth(p, pos, "defense", natural=True), reverse=True)

        slots = POSITION_DEPTH.get(pos, 4)
        selected = natural[:slots]

        if len(selected) < slots:
            cross = _two_way_conversion_candidates(team, pos, "defense")
            cross.sort(key=lambda p: _sort_key_for_depth(p, pos, "defense", natural=False), reverse=True)
            for p in cross:
                if p not in selected:
                    selected.append(p)
                if len(selected) >= slots:
                    break

        selected = _force_fill_position(team, selected, pos, "defense", slots)
        dc.defense[pos] = _apply_user_depth_order(team, pos, "defense", selected, roster)

    for pos in SPECIALIST_POSITIONS:
        candidates = [
            p for p in roster
            if (p.position == pos or (p.kick_power > 55 and p.kick_accuracy > 55))
            and _position_rating_specialist(p, pos) > 0
        ]
        candidates.sort(key=lambda p: _position_rating_specialist(p, pos), reverse=True)
        dc.specialists[pos] = candidates[: POSITION_DEPTH.get(pos, 1)]

    return dc


# ---------- FATIGUE & SUBSTITUTION ----------

@dataclass
class FatigueTracker:
    """
    Tracks player fatigue during a game.
    Stamina (1-100) reduces fatigue drain. Sub when fatigue < FATIGUE_SUB_THRESHOLD.
    """

    fatigue: Dict[int, float] = field(default_factory=dict)  # id(player) -> fatigue (0-100)

    def init_players(self, players: List["Player"]) -> None:
        """Initialize fatigue for players (call at game start)."""
        for p in players:
            self.fatigue[id(p)] = float(FATIGUE_INITIAL)

    def get_fatigue(self, player: "Player") -> float:
        """Current fatigue (0-100). Default 100 if not tracked."""
        return self.fatigue.get(id(player), float(FATIGUE_INITIAL))

    def drain_fatigue(self, player: "Player", play_count: int = 1) -> float:
        """
        Drain fatigue after play(s). Stamina reduces drain.
        Returns new fatigue level.
        """
        key = id(player)
        current = self.fatigue.get(key, float(FATIGUE_INITIAL))
        # Higher stamina = slower drain (stamina 100 -> half drain)
        stamina_factor = 1.0 - (player.stamina / 200)  # 0.5 to 1.0
        drain = FATIGUE_DRAIN_PER_PLAY * play_count * stamina_factor
        new_fatigue = max(0, current - drain)
        self.fatigue[key] = new_fatigue
        return new_fatigue

    def is_fatigued(self, player: "Player") -> bool:
        """True if player should be subbed (fatigue below threshold)."""
        return self.get_fatigue(player) < FATIGUE_SUB_THRESHOLD

    def get_fatigued_players(self, players: List["Player"]) -> set:
        """Set of player ids (int) currently below fatigue threshold. Use ids so Player is never put in a set (unhashable)."""
        return {id(p) for p in players if self.is_fatigued(p)}

    def recover_series(self, players: List["Player"], amount: float = 5) -> None:
        """Recover fatigue between series (e.g., when possession changes)."""
        for p in players:
            key = id(p)
            if key in self.fatigue:
                self.fatigue[key] = min(FATIGUE_INITIAL, self.fatigue[key] + amount)


def get_substitution(
    depth_chart: DepthChart,
    position: str,
    side: str,
    current_player: "Player",
    fatigued_players: set,
) -> Optional["Player"]:
    """
    Get substitute when current player is fatigued.
    fatigued_players: set of player ids (from tracker.get_fatigued_players()).
    Returns next available player on depth chart at that position.
    """
    return depth_chart.get_next_available(
        position, side, exclude=current_player, exclude_fatigued=fatigued_players
    )


def record_fatigue_substitution(
    current_player: "Player",
    substitute: "Player",
    position: str,
    side: str,
) -> str:
    """Return a note string for logging a fatigue sub."""
    return f"[FATIGUE SUB] {current_player.name} out, {substitute.name} in at {position} ({side})"
