"""
In-game stamina and fatigue system.
Players start at 100 stamina; fatigue costs drain it by position and play type.
Low stamina reduces performance; bench recovery and subs keep rotations realistic.
"""

import random
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Set, Tuple

from models.player import RATING_ATTR_MAX, RATING_ATTR_MIN

if TYPE_CHECKING:
    from models.player import Player
    from models.team import Team

# Base: everyone starts at 100
STAMINA_INITIAL = 100

# Position fatigue cost per play (min, max). Higher player.stamina rating = lower cost (scale toward min).
# Skill: RB 6-9, WR 4-6, TE 5-7, QB 2-4. Line: OL 4-6, DL 6-8. Defense: LB 5-7, DB 4-6.
POSITION_FATIGUE_RANGE: Dict[str, Tuple[int, int]] = {
    "QB": (2, 4),
    "RB": (6, 9),
    "WR": (4, 6),
    "TE": (5, 7),
    "OL": (4, 6),
    "DE": (6, 8),
    "DT": (6, 8),
    "LB": (5, 7),
    "CB": (4, 6),
    "S": (4, 6),
}

# Play type multipliers
MULT_RUN = 1.1
MULT_PASS = 1.0
MULT_DEEP_PASS = 1.2
MULT_QB_SCRAMBLE = 1.4
EXTRA_LONG_RUN = 2   # 10+ yard run
EXTRA_NO_HUDDLE = 1

# Drive accumulation (plays on current drive)
DRIVE_BONUS_6_PLAYS = 1
DRIVE_BONUS_10_PLAYS = 2
DRIVE_BONUS_14_PLAYS = 3

# Performance impact: stamina band -> multiplier (1.0 = normal, 0.8 = -20%)
PERF_80_100 = 1.0
PERF_60_79 = 0.97   # -3%
PERF_40_59 = 0.93   # -7%
PERF_20_39 = 0.88   # -12%
PERF_0_19 = 0.80    # -20% + higher injury chance

# Bench recovery per play off field
RECOVERY_SKILL = 6   # RB, WR, TE
RECOVERY_LINEMEN = 5 # OL, DL
RECOVERY_QB = 4
RECOVERY_LB = 5
RECOVERY_DB = 6

RECOVERY_TIMEOUT = 5
RECOVERY_QUARTER = 15
RECOVERY_HALFTIME = 35

# Special rules
RB_CARRIES_THRESHOLD = 25
RB_EXTRA_FATIGUE_PER_CARRY = 2
DL_CONSECUTIVE_THRESHOLD = 5
DL_EXTRA_FATIGUE = 2

# Default sub thresholds (sub when current stamina below this). User can override per team/coach.
DEFAULT_SUB_THRESHOLDS: Dict[str, int] = {
    "QB": 50,
    "RB": 60,
    "WR": 65,
    "TE": 60,
    "OL": 55,
    "DE": 70,
    "DT": 70,
    "LB": 65,
    "CB": 65,
    "S": 65,
}


def _position_fatigue_range(position: str) -> Tuple[int, int]:
    """Get (min, max) fatigue cost for position. DL uses DE/DT."""
    if position in ("DE", "DT"):
        return POSITION_FATIGUE_RANGE.get("DE", (6, 8))
    return POSITION_FATIGUE_RANGE.get(position, (5, 7))


def _stamina_scale(stamina_rating: int) -> float:
    """0-1: higher stamina rating = lower fatigue (closer to min of range)."""
    lo, hi = RATING_ATTR_MIN, RATING_ATTR_MAX
    s = max(lo, min(hi, stamina_rating))
    span = max(1, hi - lo)
    return (s - lo) / float(span)


def _base_fatigue_cost(player: "Player", position: str) -> float:
    """Base fatigue cost for this player at position. Depends on player.stamina rating."""
    lo, hi = _position_fatigue_range(position)
    t = _stamina_scale(getattr(player, "stamina", 50))
    return lo + (1.0 - t) * (hi - lo)


@dataclass
class PlayFatigueContext:
    """Context for one play: used to compute fatigue cost and drive bonuses."""
    is_run: bool = False
    is_pass: bool = True
    is_deep_pass: bool = False
    is_qb_scramble: bool = False
    is_long_run: bool = False   # 10+ yards
    no_huddle: bool = False
    drive_plays: int = 0        # plays on this drive so far
    rb_carries_this_game: int = 0  # for RB 25+ rule
    dl_consecutive_plays: int = 0   # for DL 5 consecutive rule


@dataclass
class GameStaminaTracker:
    """
    Tracks current stamina (0-100) for all players in a game.
    Start at 100; fatigue costs subtract. Recovery adds.
    """
    stamina: Dict[int, float] = field(default_factory=dict)  # id(player) -> 0-100
    # Current on-field lineup (position -> player) so we know who to drain and who subs in
    current_offense: Dict[str, "Player"] = field(default_factory=dict)
    current_defense: Dict[str, "Player"] = field(default_factory=dict)
    # Tracking for special rules
    rush_attempts: Dict[int, int] = field(default_factory=dict)  # id(player) -> carries
    consecutive_def_plays: Dict[int, int] = field(default_factory=dict)  # id(player) -> consecutive

    def init_players(self, players: List["Player"]) -> None:
        """Set everyone to 100 stamina at game start."""
        for p in players:
            self.stamina[id(p)] = float(STAMINA_INITIAL)
            self.rush_attempts[id(p)] = 0
            self.consecutive_def_plays[id(p)] = 0

    def get_stamina(self, player: "Player") -> float:
        """Current stamina 0-100. Default 100 if not tracked."""
        return self.stamina.get(id(player), float(STAMINA_INITIAL))

    def set_stamina(self, player: "Player", value: float) -> None:
        self.stamina[id(player)] = max(0, min(100, value))

    def drain(
        self,
        player: "Player",
        position: str,
        ctx: PlayFatigueContext,
        is_offense: bool,
    ) -> float:
        """
        Apply fatigue cost for one player on this play. Returns new stamina.
        """
        cost = _base_fatigue_cost(player, position)
        mult = MULT_PASS
        if ctx.is_run:
            mult = MULT_RUN
        elif ctx.is_qb_scramble:
            mult = MULT_QB_SCRAMBLE
        elif ctx.is_deep_pass:
            mult = MULT_DEEP_PASS
        cost *= mult
        if ctx.is_long_run and position == "RB":
            cost += EXTRA_LONG_RUN
        if ctx.no_huddle:
            cost += EXTRA_NO_HUDDLE
        # Drive accumulation
        if ctx.drive_plays >= 14:
            cost += DRIVE_BONUS_14_PLAYS
        elif ctx.drive_plays >= 10:
            cost += DRIVE_BONUS_10_PLAYS
        elif ctx.drive_plays >= 6:
            cost += DRIVE_BONUS_6_PLAYS
        # RB 25+ carries
        if position == "RB" and ctx.rb_carries_this_game >= RB_CARRIES_THRESHOLD:
            cost += RB_EXTRA_FATIGUE_PER_CARRY
        # DL 5 consecutive
        if not is_offense and position in ("DE", "DT") and ctx.dl_consecutive_plays >= DL_CONSECUTIVE_THRESHOLD:
            cost += DL_EXTRA_FATIGUE

        current = self.get_stamina(player)
        new_val = max(0, current - cost)
        self.set_stamina(player, new_val)
        return new_val

    def get_performance_multiplier(self, player: "Player") -> float:
        """Multiplier for effective attributes (1.0 = normal). Use when rating player for play outcome."""
        s = self.get_stamina(player)
        if s >= 80:
            return PERF_80_100
        if s >= 60:
            return PERF_60_79
        if s >= 40:
            return PERF_40_59
        if s >= 20:
            return PERF_20_39
        return PERF_0_19

    def get_injury_risk_modifier(self, player: "Player") -> float:
        """At 0-19 stamina, higher injury chance. Return multiplier for injury roll (e.g. 1.5)."""
        s = self.get_stamina(player)
        if s < 20:
            return 1.0 + (20 - s) / 40.0  # up to 1.5 at 0
        return 1.0

    # ---------- Recovery ----------
    def recover_bench(self, player: "Player", position: str, plays_off: int = 1) -> float:
        """Recover stamina while on bench. Returns new stamina."""
        if position == "QB":
            amount = RECOVERY_QB * plays_off
        elif position in ("OL", "DE", "DT"):
            amount = RECOVERY_LINEMEN * plays_off
        elif position == "LB":
            amount = RECOVERY_LB * plays_off
        else:
            amount = RECOVERY_SKILL * plays_off
        current = self.get_stamina(player)
        new_val = min(STAMINA_INITIAL, current + amount)
        self.set_stamina(player, new_val)
        return new_val

    def recover_timeout(self, players: List["Player"]) -> None:
        for p in players:
            if id(p) in self.stamina:
                self.set_stamina(p, min(STAMINA_INITIAL, self.get_stamina(p) + RECOVERY_TIMEOUT))

    def recover_quarter_break(self, players: List["Player"]) -> None:
        for p in players:
            if id(p) in self.stamina:
                self.set_stamina(p, min(STAMINA_INITIAL, self.get_stamina(p) + RECOVERY_QUARTER))

    def recover_halftime(self, players: List["Player"]) -> None:
        for p in players:
            if id(p) in self.stamina:
                self.set_stamina(p, min(STAMINA_INITIAL, self.get_stamina(p) + RECOVERY_HALFTIME))

    # ---------- Substitution ----------
    def get_sub_threshold(self, position: str, team: Optional["Team"] = None) -> int:
        """Sub when stamina below this. Check team.sub_stamina_thresholds[position] if present."""
        if team is not None:
            thresholds = getattr(team, "sub_stamina_thresholds", None) or getattr(
                getattr(team, "coach", None), "sub_stamina_thresholds", None
            )
            if isinstance(thresholds, dict) and position in thresholds:
                return int(thresholds[position])
        return DEFAULT_SUB_THRESHOLDS.get(position, 60)

    def should_sub(self, player: "Player", position: str, team: Optional["Team"] = None) -> bool:
        """True if this player should be subbed out (stamina below threshold)."""
        return self.get_stamina(player) < self.get_sub_threshold(position, team)

    def get_players_to_sub(
        self,
        lineup_off: Dict[str, "Player"],
        lineup_def: Dict[str, "Player"],
        depth_chart: Any,
        team: Optional["Team"] = None,
    ) -> Dict[str, Tuple["Player", "Player"]]:
        """
        Returns dict position -> (current_player, substitute) for any position
        where current player is below sub threshold. Requires depth_chart to find next available.
        """
        subs = {}
        if depth_chart is None:
            return subs
        for pos, player in lineup_off.items():
            if player is None:
                continue
            if self.should_sub(player, pos, team):
                next_p = depth_chart.get_next_available(pos, "offense", exclude=player, exclude_fatigued=None)
                if next_p is not None and next_p != player:
                    subs[pos] = (player, next_p)
        for pos, player in lineup_def.items():
            if player is None:
                continue
            if self.should_sub(player, pos, team):
                next_p = depth_chart.get_next_available(pos, "defense", exclude=player, exclude_fatigued=None)
                if next_p is not None and next_p != player:
                    subs[pos] = (player, next_p)
        return subs


def build_current_lineup_from_depth_chart(dc: Any) -> Tuple[Dict[str, "Player"], Dict[str, "Player"]]:
    """Build offense and defense lineup (position -> starter at slot 0) from depth chart."""
    off = {}
    def_ = {}
    for pos in getattr(dc, "offense", {}):
        p = dc.get_starter(pos, "offense", 0)
        if p is not None:
            off[pos] = p
    for pos in getattr(dc, "defense", {}):
        p = dc.get_starter(pos, "defense", 0)
        if p is not None:
            def_[pos] = p
    return off, def_


def apply_substitution(
    lineup_off: Dict[str, "Player"],
    lineup_def: Dict[str, "Player"],
    position: str,
    new_player: "Player",
) -> None:
    """Put new_player on field at position. Mutates lineup_off or lineup_def."""
    from systems.depth_chart import OFFENSE_POSITIONS, DEFENSE_POSITIONS
    if position in OFFENSE_POSITIONS and position in lineup_off:
        lineup_off[position] = new_player
    elif position in DEFENSE_POSITIONS and position in lineup_def:
        lineup_def[position] = new_player


def effective_attribute(value: int, multiplier: float) -> int:
    """Apply stamina performance multiplier to an attribute (e.g. speed 90 at 0.93 -> 83)."""
    return max(RATING_ATTR_MIN, min(RATING_ATTR_MAX, int(round(value * multiplier))))


def process_after_play(
    offense_tracker: "GameStaminaTracker",
    defense_tracker: "GameStaminaTracker",
    offense_lineup_off: Dict[str, "Player"],
    offense_lineup_def: Dict[str, "Player"],
    defense_lineup_off: Dict[str, "Player"],
    defense_lineup_def: Dict[str, "Player"],
    offense_depth_chart: Any,
    defense_depth_chart: Any,
    offense_team: Optional["Team"] = None,
    defense_team: Optional["Team"] = None,
    ctx: Optional[PlayFatigueContext] = None,
    ball_carrier: Optional["Player"] = None,
) -> None:
    """
    Run after each play: drain on-field players, recover bench, apply subs.
    offense_team has the ball (their offense lineup + defense_team's defense lineup get drained).
    ctx provides play type; ball_carrier is the RB (if run) for carry count / 25+ rule.
    """
    ctx = ctx or PlayFatigueContext()
    # Drain offense (team with ball)
    for pos, player in offense_lineup_off.items():
        if player is not None:
            if pos == "RB":
                ctx.rb_carries_this_game = offense_tracker.rush_attempts.get(id(player), 0)
            offense_tracker.drain(player, pos, ctx, is_offense=True)
            if pos == "RB" and ball_carrier is player:
                offense_tracker.rush_attempts[id(player)] = offense_tracker.rush_attempts.get(id(player), 0) + 1
    for pos, player in defense_lineup_def.items():
        if player is not None:
            defense_tracker.drain(player, pos, ctx, is_offense=False)
            prev = defense_tracker.consecutive_def_plays.get(id(player), 0)
            defense_tracker.consecutive_def_plays[id(player)] = prev + 1
            if pos in ("DE", "DT"):
                ctx.dl_consecutive_plays = prev + 1
    # Reset consecutive for units that weren't on field this play
    for p in offense_lineup_def.values():
        if p is not None:
            offense_tracker.consecutive_def_plays[id(p)] = 0
    for p in defense_lineup_off.values():
        if p is not None:
            defense_tracker.consecutive_def_plays[id(p)] = 0
    # Bench recovery: all roster players not in current offense+defense lineups get one play recovery
    def recover_bench_roster(tracker: "GameStaminaTracker", roster: List["Player"], on_field: Set[int]) -> None:
        for p in roster:
            if id(p) in on_field:
                continue
            pos = getattr(p, "position", "") or ""
            if not pos:
                continue
            tracker.recover_bench(p, pos, 1)
    on_field_off = {id(p) for p in offense_lineup_off.values() if p is not None} | {id(p) for p in defense_lineup_def.values() if p is not None}
    on_field_def = {id(p) for p in defense_lineup_off.values() if p is not None} | {id(p) for p in offense_lineup_def.values() if p is not None}
    if offense_team and offense_team.roster:
        recover_bench_roster(offense_tracker, offense_team.roster, on_field_off)
    if defense_team and defense_team.roster:
        recover_bench_roster(defense_tracker, defense_team.roster, on_field_def)
    # Subs: offense team
    subs_off = offense_tracker.get_players_to_sub(offense_lineup_off, offense_lineup_def, offense_depth_chart, offense_team)
    for pos, (_, new_p) in subs_off.items():
        apply_substitution(offense_lineup_off, offense_lineup_def, pos, new_p)
    subs_def = defense_tracker.get_players_to_sub(defense_lineup_off, defense_lineup_def, defense_depth_chart, defense_team)
    for pos, (_, new_p) in subs_def.items():
        apply_substitution(defense_lineup_off, defense_lineup_def, pos, new_p)
