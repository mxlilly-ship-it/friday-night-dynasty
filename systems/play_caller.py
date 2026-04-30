"""
Play caller: selects plays from a playbook based on game situation.
Used by the play engine when the call is computer- or coach-driven.
"""

import random
import re
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

from models.play import (
    Play,
    OffensivePlayCategory,
    DefensivePlayCategory,
)
from systems.playbook_system import Playbook

# Optional: per-play weighting by roster attributes
try:
    from systems.play_weighting import get_offensive_play_score, get_defensive_play_score
except ImportError:
    get_offensive_play_score = None  # type: ignore
    get_defensive_play_score = None  # type: ignore

try:
    from systems.game_plan import (
        CATEGORY_TO_OFFENSIVE,
        get_weights_from_game_plan,
        validate_game_plan,
    )
except ImportError:
    get_weights_from_game_plan = None  # type: ignore
    validate_game_plan = None  # type: ignore
    CATEGORY_TO_OFFENSIVE = {}  # type: ignore

try:
    from systems.gameplan_v2 import (
        get_offense_weights_from_plan as get_offense_weights_from_plan_v2,
        get_defense_weights_from_plan as get_defense_weights_from_plan_v2,
        validate_plan as validate_plan_v2,
        OFFENSE_CATEGORIES as OFFENSE_CATEGORIES_V2,
        DEFENSE_CATEGORIES as DEFENSE_CATEGORIES_V2,
        OFFENSE_CATEGORY_TO_ENUM,
    )
except ImportError:
    get_offense_weights_from_plan_v2 = None  # type: ignore
    get_defense_weights_from_plan_v2 = None  # type: ignore
    validate_plan_v2 = None  # type: ignore
    OFFENSE_CATEGORIES_V2 = []  # type: ignore
    DEFENSE_CATEGORIES_V2 = []  # type: ignore
    OFFENSE_CATEGORY_TO_ENUM = {}  # type: ignore

try:
    from systems.defensive_game_plan import (
        get_weights_from_defensive_game_plan,
        validate_defensive_game_plan,
    )
except ImportError:
    get_weights_from_defensive_game_plan = None  # type: ignore
    validate_defensive_game_plan = None  # type: ignore


@dataclass
class GameSituation:
    """
    Snapshot of game state when a play is being called.
    Used by the play caller to choose offense/defense plays.
    Optional run/pass/defense ratings let the caller bias toward team strengths.
    """
    down: int
    yards_to_go: int
    ball_position: int  # 0-100, own goal to opponent goal
    quarter: int
    time_remaining: int  # seconds
    score_offense: int   # team with the ball
    score_defense: int  # team without the ball
    # Optional: team strengths (from roster) – bias play choice toward what the team does well
    run_rating: Optional[int] = None    # offense run game strength (1-100)
    pass_rating: Optional[int] = None    # offense pass game strength (1-100)
    defense_rating: Optional[int] = None  # defense strength when calling defensive plays
    # Turnover context (used to reduce high-turnover game tails)
    offense_turnovers: int = 0
    defense_takeaways: int = 0
    # Optional: coach tendencies (offense = team with ball, defense = team without ball)
    coach_offense: Optional[Any] = None
    coach_defense: Optional[Any] = None


def build_situation_from_game(
    game: object,
    *,
    offense_team: Optional[Any] = None,
    defense_team: Optional[Any] = None,
) -> GameSituation:
    """
    Build a GameSituation from the game engine's Game object.
    Includes run_rating/pass_rating (offense) and defense_rating when set on the game.
    If offense_team/defense_team are provided, sets coach_offense/coach_defense from team.coach.
    """
    return GameSituation(
        down=game.down,
        yards_to_go=game.yards_to_go,
        ball_position=game.ball_position,
        quarter=game.quarter,
        time_remaining=game.time_remaining,
        score_offense=game.score_home if game.possession == "home" else game.score_away,
        score_defense=game.score_away if game.possession == "home" else game.score_home,
        run_rating=getattr(game, "run_rating", None),
        pass_rating=getattr(game, "pass_rating", None),
        defense_rating=getattr(game, "defense_rating", None),
        offense_turnovers=(
            (game.interceptions_home + game.fumbles_home)
            if game.possession == "home"
            else (game.interceptions_away + game.fumbles_away)
        ),
        defense_takeaways=(
            (game.interceptions_away + game.fumbles_away)
            if game.possession == "home"
            else (game.interceptions_home + game.fumbles_home)
        ),
        coach_offense=getattr(offense_team, "coach", None) if offense_team else None,
        coach_defense=getattr(defense_team, "coach", None) if defense_team else None,
    )


def pick_offensive_play(
    playbook: Playbook,
    situation: GameSituation,
    *,
    preferred_category: Optional[OffensivePlayCategory] = None,
    offense_team: Optional[Any] = None,
    rng: Optional[random.Random] = None,
) -> Optional[Play]:
    """
    Choose an offensive play from the playbook given the situation.
    If preferred_category is set, only picks from that category (if any plays exist).
    Otherwise uses situation to infer category (e.g. 3rd and long -> pass).
    If offense_team is provided, per-play weighting by roster attributes is applied
    (e.g. mobile QB favors option plays, strong WRs favor pass concepts).
    Returns None if the playbook has no offensive plays.
    """
    rng = rng or random
    candidates: List[Play] = []

    if preferred_category is not None:
        preferred_category = _coerce_offensive_category_key(preferred_category)
    if preferred_category is not None:
        candidates = playbook.get_offensive_plays_by_category(preferred_category)
    if not candidates:
        # Situation-based category selection; weighted by run_rating/pass_rating and coach
        category = _situation_to_offensive_category(situation, rng=rng)
        candidates = playbook.get_offensive_plays_by_category(category)
    if not candidates:
        # Fallback: any offensive play
        candidates = list(playbook.offensive_plays)

    # Season play selection: when team has locked-in plays, only pick from those in this category
    selection = getattr(offense_team, "season_offensive_play_selection", None) if offense_team else None
    weights_from_selection: Optional[Dict[str, float]] = None
    if selection and candidates:
        cat = candidates[0].offensive_category
        entries = _season_off_entries_for_category(selection, cat)
        if entries:
            selected_ids = {play_id for play_id, _ in entries}
            candidates = [p for p in candidates if p.id in selected_ids]
            weights_from_selection = {play_id: max(0.1, float(pct)) for play_id, pct in entries}

    if not candidates:
        return None
    # Use game plan percentages as weights when available
    if weights_from_selection:
        weights = [weights_from_selection.get(p.id, 1.0) for p in candidates]
        return rng.choices(candidates, weights=weights, k=1)[0]
    # Per-play weighting by roster fit when team is provided
    if offense_team and get_offensive_play_score is not None:
        weights = [max(1, get_offensive_play_score(offense_team, p.id)) for p in candidates]
        return rng.choices(candidates, weights=weights, k=1)[0]
    return rng.choice(candidates)


def pick_defensive_play(
    playbook: Playbook,
    situation: GameSituation,
    *,
    preferred_category: Optional[DefensivePlayCategory] = None,
    defense_team: Optional[Any] = None,
    rng: Optional[random.Random] = None,
) -> Optional[Play]:
    """
    Choose a defensive play from the playbook given the situation.
    If preferred_category is set, only picks from that category.
    Otherwise uses situation to infer (e.g. expect pass -> zone/man pressure).
    If defense_team is provided, per-play weighting is applied: zone/man coverage
    by DB skills, pressure plays by DL pass_rush and LB blitz.
    Returns None if the playbook has no defensive plays.
    """
    rng = rng or random
    candidates: List[Play] = []

    if preferred_category is not None:
        preferred_category = _coerce_defensive_category_key(preferred_category)
    if preferred_category is not None:
        candidates = playbook.get_defensive_plays_by_category(preferred_category)
    if not candidates:
        category = _situation_to_defensive_category(situation, rng=rng)
        candidates = playbook.get_defensive_plays_by_category(category)
    if not candidates:
        candidates = list(playbook.defensive_plays)

    # Season play selection: when team has locked-in plays, only pick from those in this category
    selection = getattr(defense_team, "season_defensive_play_selection", None) if defense_team else None
    weights_from_selection: Optional[Dict[str, float]] = None
    if selection and candidates:
        cat = candidates[0].defensive_category
        entries = _season_def_entries_for_category(selection, cat)
        if entries:
            selected_ids = {play_id for play_id, _ in entries}
            candidates = [p for p in candidates if p.id in selected_ids]
            weights_from_selection = {play_id: max(0.1, float(pct)) for play_id, pct in entries}

    if not candidates:
        return None
    # Use game plan percentages as weights when available
    if weights_from_selection:
        weights = [weights_from_selection.get(p.id, 1.0) for p in candidates]
        return rng.choices(candidates, weights=weights, k=1)[0]
    # Per-play weighting: zone/man by DB coverage; pressure by DL pass_rush, LB blitz
    if defense_team and get_defensive_play_score is not None:
        weights = [max(1, get_defensive_play_score(defense_team, p.id)) for p in candidates]
        return rng.choices(candidates, weights=weights, k=1)[0]
    return rng.choice(candidates)


# Coach tendency baseline splits: (inside_run, outside_run, short_pass, medium_pass, long_pass, play_action)
# Run % = (inside+outside)/total. Situational (2-min, 4-min, score) still applies.
COACH_TENDENCY_BASELINES = {
    "HEAVY_RUN": (44, 41, 4, 4, 4, 3),       # ~85% run / 15% pass
    "LEAN_RUN": (38, 34, 8, 8, 6, 6),        # ~72% run / 28% pass
    "BALANCED": (30, 27, 12, 12, 10, 9),     # ~57% run / 43% pass
    "LEAN_PASS": (25, 22, 14, 14, 12, 13),   # ~47% run / 53% pass
    "HEAVY_PASS": (20, 17, 16, 16, 18, 13),  # ~37% run / 63% pass
}


_ALL_OFFENSE_CATS: Tuple[OffensivePlayCategory, ...] = (
    OffensivePlayCategory.INSIDE_RUN,
    OffensivePlayCategory.OUTSIDE_RUN,
    OffensivePlayCategory.SHORT_PASS,
    OffensivePlayCategory.MEDIUM_PASS,
    OffensivePlayCategory.LONG_PASS,
    OffensivePlayCategory.PLAY_ACTION,
)

# Match member names inside repr / dotted strings (e.g. duplicate enum classes, logs).
_OFFENSE_ENUM_NAME_IN_STRING = re.compile(
    r"\b(INSIDE_RUN|OUTSIDE_RUN|SHORT_PASS|MEDIUM_PASS|LONG_PASS|PLAY_ACTION)\b"
)


def _lookup_offense_from_label_map(
    s: str, d: Dict[str, OffensivePlayCategory]
) -> Optional[OffensivePlayCategory]:
    if not d or not s:
        return None
    if s in d:
        return d[s]
    sl = s.casefold()
    for k, v in d.items():
        if k.casefold() == sl:
            return v
    return None


def _coerce_offensive_category_key(key: Any) -> Optional[OffensivePlayCategory]:
    """Map enum member, enum name, display label, or grid label to canonical OffensivePlayCategory."""
    if isinstance(key, OffensivePlayCategory):
        return key
    # Same member name from a different OffensivePlayCategory class (reload / import path).
    if isinstance(key, Enum) and key.__class__.__name__ == "OffensivePlayCategory":
        kn = getattr(key, "name", None)
        if kn:
            for c in _ALL_OFFENSE_CATS:
                if c.name == kn:
                    return c
    if isinstance(key, str):
        s = key.strip()
        for c in _ALL_OFFENSE_CATS:
            if s == c.name or s == c.value:
                return c
        sl = s.casefold()
        for c in _ALL_OFFENSE_CATS:
            if sl == c.name.casefold() or sl == str(c.value).casefold():
                return c
        oc = _lookup_offense_from_label_map(s, CATEGORY_TO_OFFENSIVE)
        if oc is not None:
            return oc
        oc2 = _lookup_offense_from_label_map(s, OFFENSE_CATEGORY_TO_ENUM)
        if oc2 is not None:
            return oc2
        m = _OFFENSE_ENUM_NAME_IN_STRING.search(s)
        if m:
            try:
                return OffensivePlayCategory[m.group(1)]
            except Exception:
                pass
    return None


def _normalize_offense_weights(
    weights: Optional[Dict[Any, Any]],
) -> Dict[OffensivePlayCategory, float]:
    """
    Canonical offensive weight map: exactly one float per OffensivePlayCategory.
    Merges string-labeled cells (e.g. \"Outside Run\") and drops stray keys so
    downstream code never KeyErrors on category enums (e.g. OUTSIDE_RUN, LONG_PASS).
    """
    out: Dict[OffensivePlayCategory, float] = {c: 0.0 for c in _ALL_OFFENSE_CATS}
    if not weights:
        return out
    for k, v in weights.items():
        cat = _coerce_offensive_category_key(k)
        if cat is None:
            continue
        try:
            out[cat] = max(0.0, out[cat] + float(v))
        except Exception:
            pass
    return out


def _season_off_entries_for_category(
    selection: Dict[str, Any],
    cat: Optional[OffensivePlayCategory],
) -> Optional[List[Tuple[str, float]]]:
    """Resolve play-selection list for an offensive category (enum name or display label)."""
    if not selection or cat is None:
        return None
    cat = _coerce_offensive_category_key(cat)
    if cat is None:
        return None
    for key in (cat.name, getattr(cat, "value", None)):
        if not key:
            continue
        ent = selection.get(key)
        if ent:
            return ent
    for k, ent in selection.items():
        ck = _coerce_offensive_category_key(k)
        if ck is not None and ck.name == cat.name and ent:
            return ent
    return None


_DEFENSE_ENUM_NAME_IN_STRING = re.compile(
    r"\b(ZONES|MANS|ZONE_PRESSURE|MAN_PRESSURE)\b"
)


def _coerce_defensive_category_key(key: Any) -> Optional[DefensivePlayCategory]:
    if isinstance(key, DefensivePlayCategory):
        return key
    if isinstance(key, Enum) and key.__class__.__name__ == "DefensivePlayCategory":
        kn = getattr(key, "name", None)
        if kn:
            for c in DefensivePlayCategory:
                if c.name == kn:
                    return c
    if isinstance(key, str):
        s = key.strip()
        for c in DefensivePlayCategory:
            if s == c.name or s == c.value:
                return c
        sl = s.casefold()
        for c in DefensivePlayCategory:
            if sl == c.name.casefold() or sl == str(c.value).casefold():
                return c
        m = _DEFENSE_ENUM_NAME_IN_STRING.search(s)
        if m:
            try:
                return DefensivePlayCategory[m.group(1)]
            except Exception:
                pass
    return None


def _season_def_entries_for_category(
    selection: Dict[str, Any],
    cat: Optional[DefensivePlayCategory],
) -> Optional[List[Tuple[str, float]]]:
    if not selection or cat is None:
        return None
    cat = _coerce_defensive_category_key(cat)
    if cat is None:
        return None
    for key in (cat.name, getattr(cat, "value", None)):
        if not key:
            continue
        ent = selection.get(key)
        if ent:
            return ent
    for k, ent in selection.items():
        ck = _coerce_defensive_category_key(k)
        if ck is not None and ck.name == cat.name and ent:
            return ent
    return None


def _get_coach_baseline(situation: GameSituation) -> Dict[OffensivePlayCategory, float]:
    """Base weights from coach tendency. Down/distance and situation adjust from here."""
    coach = getattr(situation, "coach_offense", None)
    style_name = "BALANCED"
    if coach is not None:
        style = getattr(coach, "offensive_style", None)
        if style is not None:
            style_name = getattr(style, "name", "BALANCED")
    baseline = COACH_TENDENCY_BASELINES.get(style_name, COACH_TENDENCY_BASELINES["BALANCED"])
    ir, orun, sp, mp, lp, pa = baseline
    return {
        OffensivePlayCategory.INSIDE_RUN: float(ir),
        OffensivePlayCategory.OUTSIDE_RUN: float(orun),
        OffensivePlayCategory.SHORT_PASS: float(sp),
        OffensivePlayCategory.MEDIUM_PASS: float(mp),
        OffensivePlayCategory.LONG_PASS: float(lp),
        OffensivePlayCategory.PLAY_ACTION: float(pa),
    }


def _base_offensive_weights(situation: GameSituation) -> Dict[OffensivePlayCategory, float]:
    """
    Start from coach tendency baseline (or game plan if coach has one), then shift by down/distance.
    When coach.game_plan is set and valid, use its (situation, area) cell as base weights.
    """
    coach = getattr(situation, "coach_offense", None)
    # V2 coach gameplan (score situation + field area + D&D buckets)
    game_plan_v2 = getattr(coach, "game_plan_v2_offense", None) if coach else None
    if (
        game_plan_v2 is not None
        and get_offense_weights_from_plan_v2 is not None
        and validate_plan_v2 is not None
    ):
        ok, _errs = validate_plan_v2(game_plan_v2, categories=OFFENSE_CATEGORIES_V2)
        if ok:
            weights = get_offense_weights_from_plan_v2(
                game_plan_v2,
                down=situation.down,
                yards_to_go=situation.yards_to_go,
                ball_position=situation.ball_position,
                score_for=situation.score_offense,
                score_against=situation.score_defense,
            )
            return _normalize_offense_weights(weights)
    game_plan = getattr(coach, "game_plan", None) if coach else None
    if (
        game_plan is not None
        and get_weights_from_game_plan is not None
        and validate_game_plan is not None
    ):
        ok, _ = validate_game_plan(game_plan)
        if ok:
            weights = get_weights_from_game_plan(
                game_plan,
                situation.down,
                situation.yards_to_go,
                situation.ball_position,
            )
            return _normalize_offense_weights(weights)

    d = situation.down
    ytg = situation.yards_to_go
    weights = _normalize_offense_weights(_get_coach_baseline(situation))

    # Down/distance shifts: multiply coach baseline by these factors (1.0 = no change)
    if d == 1:
        if ytg <= 3:
            # Short yardage: boost run, cut long pass
            weights[OffensivePlayCategory.INSIDE_RUN] *= 1.35
            weights[OffensivePlayCategory.OUTSIDE_RUN] *= 1.30
            weights[OffensivePlayCategory.LONG_PASS] *= 0.45
            weights[OffensivePlayCategory.PLAY_ACTION] *= 1.25
        elif ytg <= 6:
            weights[OffensivePlayCategory.INSIDE_RUN] *= 1.08
            weights[OffensivePlayCategory.OUTSIDE_RUN] *= 1.05
            weights[OffensivePlayCategory.LONG_PASS] *= 0.70
        else:
            # 1st and long: favor pass
            weights[OffensivePlayCategory.INSIDE_RUN] *= 0.60
            weights[OffensivePlayCategory.OUTSIDE_RUN] *= 0.60
            weights[OffensivePlayCategory.SHORT_PASS] *= 1.15
            weights[OffensivePlayCategory.MEDIUM_PASS] *= 1.25
            weights[OffensivePlayCategory.LONG_PASS] *= 1.45
    elif d == 2:
        if ytg <= 2:
            weights[OffensivePlayCategory.INSIDE_RUN] *= 1.45
            weights[OffensivePlayCategory.OUTSIDE_RUN] *= 1.40
            weights[OffensivePlayCategory.LONG_PASS] *= 0.35
            weights[OffensivePlayCategory.PLAY_ACTION] *= 1.50
        elif ytg <= 6:
            weights[OffensivePlayCategory.LONG_PASS] *= 0.85
        else:
            weights[OffensivePlayCategory.INSIDE_RUN] *= 0.45
            weights[OffensivePlayCategory.OUTSIDE_RUN] *= 0.50
            weights[OffensivePlayCategory.MEDIUM_PASS] *= 1.30
            weights[OffensivePlayCategory.LONG_PASS] *= 1.75
    elif d == 3:
        if ytg <= 2:
            weights[OffensivePlayCategory.INSIDE_RUN] *= 1.55
            weights[OffensivePlayCategory.OUTSIDE_RUN] *= 1.45
            weights[OffensivePlayCategory.LONG_PASS] *= 0.35
            weights[OffensivePlayCategory.PLAY_ACTION] *= 1.15
        elif ytg <= 4:
            weights[OffensivePlayCategory.INSIDE_RUN] *= 0.70
            weights[OffensivePlayCategory.OUTSIDE_RUN] *= 0.65
            weights[OffensivePlayCategory.SHORT_PASS] *= 1.55
            weights[OffensivePlayCategory.MEDIUM_PASS] *= 1.25
            weights[OffensivePlayCategory.LONG_PASS] *= 0.55
        elif ytg <= 7:
            weights[OffensivePlayCategory.INSIDE_RUN] *= 0.50
            weights[OffensivePlayCategory.OUTSIDE_RUN] *= 0.40
            weights[OffensivePlayCategory.SHORT_PASS] *= 1.30
            weights[OffensivePlayCategory.MEDIUM_PASS] *= 1.55
            weights[OffensivePlayCategory.LONG_PASS] *= 1.15
        else:
            # 3rd and long (8+): force pass-heavy
            weights[OffensivePlayCategory.INSIDE_RUN] *= 0.30
            weights[OffensivePlayCategory.OUTSIDE_RUN] *= 0.30
            weights[OffensivePlayCategory.SHORT_PASS] *= 1.10
            weights[OffensivePlayCategory.MEDIUM_PASS] *= 1.35
            weights[OffensivePlayCategory.LONG_PASS] *= 3.20
            weights[OffensivePlayCategory.PLAY_ACTION] *= 0.10
    elif d >= 4:
        if ytg <= 1:
            weights[OffensivePlayCategory.INSIDE_RUN] *= 1.85
            weights[OffensivePlayCategory.OUTSIDE_RUN] *= 1.50
            weights[OffensivePlayCategory.LONG_PASS] *= 0.20
            weights[OffensivePlayCategory.PLAY_ACTION] *= 1.00
        elif ytg <= 3:
            weights[OffensivePlayCategory.INSIDE_RUN] *= 0.70
            weights[OffensivePlayCategory.OUTSIDE_RUN] *= 0.65
            weights[OffensivePlayCategory.SHORT_PASS] *= 1.35
            weights[OffensivePlayCategory.MEDIUM_PASS] *= 1.40
            weights[OffensivePlayCategory.LONG_PASS] *= 0.85
        elif ytg <= 6:
            weights[OffensivePlayCategory.INSIDE_RUN] *= 0.30
            weights[OffensivePlayCategory.OUTSIDE_RUN] *= 0.30
            weights[OffensivePlayCategory.MEDIUM_PASS] *= 1.55
            weights[OffensivePlayCategory.LONG_PASS] *= 1.95
        else:
            weights[OffensivePlayCategory.INSIDE_RUN] *= 0.05
            weights[OffensivePlayCategory.OUTSIDE_RUN] *= 0.05
            weights[OffensivePlayCategory.SHORT_PASS] *= 1.15
            weights[OffensivePlayCategory.MEDIUM_PASS] *= 1.75
            weights[OffensivePlayCategory.LONG_PASS] *= 2.80
            weights[OffensivePlayCategory.PLAY_ACTION] *= 0.05
    return _normalize_offense_weights(weights)


def _apply_game_situation_adjustments(
    weights: Dict[OffensivePlayCategory, float],
    situation: GameSituation,
) -> Dict[OffensivePlayCategory, float]:
    """Adjust base weights by score, clock, and field position."""
    out = _normalize_offense_weights(weights)
    score_margin = situation.score_offense - situation.score_defense
    two_minute = situation.quarter == 4 and situation.time_remaining <= 2 * 60
    four_minute = situation.quarter == 4 and situation.time_remaining <= 4 * 60

    # Trailing: pass more to catch up
    if two_minute and score_margin < 0:
        out[OffensivePlayCategory.SHORT_PASS] *= 1.30
        out[OffensivePlayCategory.MEDIUM_PASS] *= 1.40
        out[OffensivePlayCategory.LONG_PASS] *= 1.45
        out[OffensivePlayCategory.INSIDE_RUN] *= 0.50
        out[OffensivePlayCategory.OUTSIDE_RUN] *= 0.55
        out[OffensivePlayCategory.PLAY_ACTION] *= 0.65
    elif situation.quarter >= 3 and score_margin <= -10:
        out[OffensivePlayCategory.SHORT_PASS] *= 1.15
        out[OffensivePlayCategory.MEDIUM_PASS] *= 1.25
        out[OffensivePlayCategory.LONG_PASS] *= 1.20
        out[OffensivePlayCategory.INSIDE_RUN] *= 0.80
        out[OffensivePlayCategory.OUTSIDE_RUN] *= 0.85

    # Protecting lead (2-min, 4-min): run more to kill clock
    if four_minute and score_margin > 0:
        run_boost = 1.50 if two_minute else 1.25
        out[OffensivePlayCategory.INSIDE_RUN] *= run_boost
        out[OffensivePlayCategory.OUTSIDE_RUN] *= run_boost
        out[OffensivePlayCategory.PLAY_ACTION] *= 1.15
        out[OffensivePlayCategory.LONG_PASS] *= 0.55
    elif situation.quarter >= 3 and score_margin >= 14:
        out[OffensivePlayCategory.INSIDE_RUN] *= 1.35
        out[OffensivePlayCategory.OUTSIDE_RUN] *= 1.25
        out[OffensivePlayCategory.PLAY_ACTION] *= 1.10
        out[OffensivePlayCategory.LONG_PASS] *= 0.60

    # Red zone tends to compress vertical game
    if situation.ball_position >= 80:
        out[OffensivePlayCategory.LONG_PASS] *= 0.60
        out[OffensivePlayCategory.SHORT_PASS] *= 1.10
        out[OffensivePlayCategory.INSIDE_RUN] *= 1.10

    # Turnover management: after multiple giveaways, coaches get more conservative.
    if situation.offense_turnovers >= 2:
        out[OffensivePlayCategory.LONG_PASS] *= 0.75
        out[OffensivePlayCategory.MEDIUM_PASS] *= 0.90
        out[OffensivePlayCategory.INSIDE_RUN] *= 1.10
        out[OffensivePlayCategory.OUTSIDE_RUN] *= 1.10
    if situation.offense_turnovers >= 3:
        out[OffensivePlayCategory.LONG_PASS] *= 0.50
        out[OffensivePlayCategory.MEDIUM_PASS] *= 0.80
        out[OffensivePlayCategory.SHORT_PASS] *= 0.95
        out[OffensivePlayCategory.INSIDE_RUN] *= 1.20
        out[OffensivePlayCategory.OUTSIDE_RUN] *= 1.20
        out[OffensivePlayCategory.PLAY_ACTION] *= 1.10

    return out


def _apply_offensive_style_adjustments(
    weights: Dict[OffensivePlayCategory, float],
    situation: GameSituation,
) -> Dict[OffensivePlayCategory, float]:
    """Adjust weights for team run/pass strengths. Coach tendency is applied in _get_coach_baseline."""
    out = _normalize_offense_weights(weights)

    # Team strength tendencies from roster-derived ratings
    run_rating = getattr(situation, "run_rating", None)
    pass_rating = getattr(situation, "pass_rating", None)
    if run_rating is not None and pass_rating is not None:
        diff = max(-40.0, min(40.0, float(run_rating - pass_rating)))
        run_bias = 1.0 + (diff / 100.0)
        pass_bias = 1.0 - (diff / 100.0)
        run_bias = max(0.65, min(1.35, run_bias))
        pass_bias = max(0.65, min(1.35, pass_bias))
        out[OffensivePlayCategory.INSIDE_RUN] *= run_bias
        out[OffensivePlayCategory.OUTSIDE_RUN] *= run_bias
        out[OffensivePlayCategory.PLAY_ACTION] *= (0.9 + (run_bias * 0.1))
        out[OffensivePlayCategory.SHORT_PASS] *= pass_bias
        out[OffensivePlayCategory.MEDIUM_PASS] *= pass_bias
        out[OffensivePlayCategory.LONG_PASS] *= pass_bias

    return out


def _choose_offensive_category_by_weights(
    weights: Dict[OffensivePlayCategory, float],
    rng: random.Random,
) -> OffensivePlayCategory:
    """Choose category from weighted mapping."""
    weights = _normalize_offense_weights(weights)
    categories = list(weights.keys())
    vals = [max(0.0, weights[c]) for c in categories]
    if sum(vals) <= 0:
        return OffensivePlayCategory.SHORT_PASS
    return rng.choices(categories, weights=vals, k=1)[0]


def _situation_to_offensive_category(
    situation: GameSituation, rng: Optional[random.Random] = None
) -> OffensivePlayCategory:
    """
    Down-and-distance offensive category logic with adjustments for:
    - score/time game situation
    - offensive coach style (Heavy Run, Lean Run, Balanced, Lean Pass, Heavy Pass)
    - roster strengths (run_rating vs pass_rating)
    """
    rng = rng or random
    weights = _normalize_offense_weights(_base_offensive_weights(situation))
    weights = _apply_game_situation_adjustments(weights, situation)
    weights = _apply_offensive_style_adjustments(weights, situation)
    return _choose_offensive_category_by_weights(weights, rng)


def _weighted_defensive_category(
    coverage_options: List[DefensivePlayCategory],
    pressure_options: List[DefensivePlayCategory],
    situation: GameSituation,
    rng: random.Random,
) -> DefensivePlayCategory:
    """
    Pick a defensive category. Weights pressure vs coverage by defense_rating and by
    coach defensive_style (HEAVY_PRESSURE, PRIMARY_ZONE, AGGRESSIVE_MAN, etc.).
    """
    defense_rating = getattr(situation, "defense_rating", None)
    cov_weight = max(25, 100 - defense_rating) if defense_rating is not None else 50.0
    press_weight = max(25, defense_rating) if defense_rating is not None else 50.0
    # Coach tendency
    coach = getattr(situation, "coach_defense", None)
    if coach is not None:
        style = getattr(coach, "defensive_style", None)
        if style is not None:
            style_name = getattr(style, "name", "")
            if style_name == "HEAVY_PRESSURE":
                press_weight *= 1.4
            elif style_name in ("PRIMARY_ZONE", "AGGRESSIVE_ZONE", "AGGRESSIVE_MAN", "CONSERVATIVE_MAN"):
                cov_weight *= 1.2
    if coverage_options and pressure_options:
        all_opts = coverage_options + pressure_options
        weights = [cov_weight] * len(coverage_options) + [press_weight] * len(pressure_options)
        return rng.choices(all_opts, weights=weights, k=1)[0]
    if coverage_options and pressure_options:
        return rng.choice(coverage_options + pressure_options)
    if coverage_options:
        return rng.choice(coverage_options)
    return rng.choice(pressure_options)


def _choose_defensive_category_by_weights(
    weights: Dict[DefensivePlayCategory, float],
    rng: random.Random,
) -> DefensivePlayCategory:
    """Pick a defensive category by weight. Categories with 0 weight are excluded."""
    categories = [c for c in DefensivePlayCategory if weights.get(c, 0) > 0]
    if not categories:
        return DefensivePlayCategory.ZONES
    vals = [max(0.0, weights[c]) for c in categories]
    if sum(vals) <= 0:
        return DefensivePlayCategory.ZONES
    return rng.choices(categories, weights=vals, k=1)[0]


def _situation_to_defensive_category(
    situation: GameSituation, rng: Optional[random.Random] = None
) -> DefensivePlayCategory:
    """
    Map game situation to a suggested defensive play category.
    When coach_defense has defensive_game_plan, use that grid; otherwise use
    situation logic and defense_rating / coach defensive_style.
    """
    rng = rng or random
    coach = getattr(situation, "coach_defense", None)
    # V2 coach gameplan (score situation + field area + D&D buckets)
    game_plan_v2 = getattr(coach, "game_plan_v2_defense", None) if coach else None
    if (
        game_plan_v2 is not None
        and get_defense_weights_from_plan_v2 is not None
        and validate_plan_v2 is not None
    ):
        ok, _errs = validate_plan_v2(game_plan_v2, categories=DEFENSE_CATEGORIES_V2)
        if ok:
            weights = get_defense_weights_from_plan_v2(
                game_plan_v2,
                down=situation.down,
                yards_to_go=situation.yards_to_go,
                ball_position=situation.ball_position,
                # Defense perspective: our score is the team without the ball
                score_for=situation.score_defense,
                score_against=situation.score_offense,
            )
            return _choose_defensive_category_by_weights(weights, rng)
    game_plan = getattr(coach, "defensive_game_plan", None) if coach else None
    if (
        game_plan is not None
        and get_weights_from_defensive_game_plan is not None
        and validate_defensive_game_plan is not None
    ):
        ok, _ = validate_defensive_game_plan(game_plan)
        if ok:
            weights = get_weights_from_defensive_game_plan(
                game_plan,
                situation.down,
                situation.yards_to_go,
                situation.ball_position,
            )
            return _choose_defensive_category_by_weights(weights, rng)

    score_margin = situation.score_offense - situation.score_defense
    two_minute = situation.quarter == 4 and situation.time_remaining <= 2 * 60

    if two_minute:
        return _weighted_defensive_category(
            [DefensivePlayCategory.ZONES],
            [
                DefensivePlayCategory.ZONE_PRESSURE,
                DefensivePlayCategory.MAN_PRESSURE,
            ],
            situation,
            rng,
        )
    if situation.yards_to_go >= 7 and situation.down >= 3:
        return _weighted_defensive_category(
            [DefensivePlayCategory.ZONES, DefensivePlayCategory.MANS],
            [DefensivePlayCategory.ZONE_PRESSURE],
            situation,
            rng,
        )
    if situation.yards_to_go <= 3:
        return rng.choice([
            DefensivePlayCategory.ZONES,
            DefensivePlayCategory.MANS,
        ])
    return _weighted_defensive_category(
        [DefensivePlayCategory.ZONES, DefensivePlayCategory.MANS],
        [DefensivePlayCategory.ZONE_PRESSURE, DefensivePlayCategory.MAN_PRESSURE],
        situation,
        rng,
    )


def call_plays_for_situation(
    offense_playbook: Playbook,
    defense_playbook: Playbook,
    situation: GameSituation,
    *,
    rng: Optional[random.Random] = None,
) -> Tuple[Optional[Play], Optional[Play]]:
    """
    Return (offensive_play, defensive_play) for the given situation.
    Convenience for the play engine when both sides call at once.
    """
    rng = rng or random
    off = pick_offensive_play(offense_playbook, situation, rng=rng)
    def_ = pick_defensive_play(defense_playbook, situation, rng=rng)
    return (off, def_)
