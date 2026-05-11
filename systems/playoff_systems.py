"""Registry of supported state playoff system structures.

Each league JSON declares a top-level ``playoff_system`` id (e.g. ``"wv"``).
That id resolves through this module to a :class:`PlayoffSystemConfig` that
drives bracket size, scope (one bracket per classification vs one state-wide
bracket), seeding rules, and minimum team counts.

Today only the West Virginia "8-team per classification" system is defined.
Add new state systems by appending entries to ``PLAYOFF_SYSTEMS`` below; no
other code changes are required for the basic plumbing — the league JSON
just references the new id.

Adding a new system later (cheat-sheet)
---------------------------------------
1. Add an entry to ``PLAYOFF_SYSTEMS`` with a unique ``id``.
2. Pick the bracket scope:
     * ``per_classification=True``  → one bracket per ``team.classification``
       (state-champion-per-class, like WV).
     * ``per_classification=False`` → one state-wide bracket across every
       team (state-champion-overall).
3. Pick ``bracket_size`` (4, 8, 16, 32, ...). Pairings follow the standard
   high-seed-vs-low-seed format already implemented in
   :mod:`systems.playoff_system`.
4. Set ``min_teams`` to the smallest pool that still fills the bracket.
5. Reference the new id from the league's ``data/teams.json``.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Optional


@dataclass(frozen=True)
class PlayoffSystemConfig:
    """Static description of one playoff structure.

    Attributes
    ----------
    id:
        Stable, lowercase identifier referenced from league JSON / save state
        (e.g. ``"wv"``).  Treat as an enum value: never rename without writing
        a migration.
    label:
        Short human-readable name shown in the UI / setup screens.
    description:
        One-paragraph summary suitable for a tooltip or "about this league"
        panel.  Should describe seeding, bracket scope, and round structure.
    bracket_size:
        Number of teams that fill one bracket (4, 8, 16, ...).
    per_classification:
        If True, the system runs one bracket per ``team.classification``
        (e.g. WV: 1A/2A/3A/4A each crown their own state champion).  If False,
        one state-wide bracket is built across every team.
    min_teams:
        Minimum eligible teams required to fill the bracket; pools smaller
        than this are skipped (no playoff bracket created for that scope).
    seeding_mode:
        ``"overall"`` (default) — single pool seeded 1..bracket_size by
        wins/PD; standard fixed bracket throughout.
        ``"regional"`` — pool is split into ``regions_per_class`` regions and
        the top ``teams_per_region`` from each region make the bracket.
        Rounds 1-2 stay inside each region (1v4, 2v3 → regional final);
        round 3 (state semifinal) re-seeds the regional champions by overall
        wins/PD and pairs highest-vs-lowest, middle-vs-middle; round 4 is
        the championship.
    regions_per_class:
        Only used when ``seeding_mode == "regional"``. Number of regions
        the bracket pool is split into (e.g. 4 for the regional_4x4 system).
    teams_per_region:
        Only used when ``seeding_mode == "regional"``. Top-N from each
        region that make the bracket (e.g. 4 for the regional_4x4 system).
        ``bracket_size`` must equal ``regions_per_class * teams_per_region``.
    """

    id: str
    label: str
    description: str
    bracket_size: int
    per_classification: bool
    min_teams: int
    seeding_mode: str = "overall"
    regions_per_class: int = 0
    teams_per_region: int = 0


# Default id used when a save / league JSON omits ``playoff_system``.
DEFAULT_PLAYOFF_SYSTEM_ID: str = "wv"


PLAYOFF_SYSTEMS: Dict[str, PlayoffSystemConfig] = {
    "wv": PlayoffSystemConfig(
        id="wv",
        label="West Virginia (8-team per classification)",
        description=(
            "One 8-team bracket per classification (1A/2A/3A/4A). "
            "Seeded 1-8 by wins then point differential; pairings 1v8, 2v7, "
            "3v6, 4v5. Three rounds: Quarterfinal -> Semifinal -> "
            "Championship. Each classification crowns its own state champion."
        ),
        bracket_size=8,
        per_classification=True,
        min_teams=8,
    ),
    "wv16": PlayoffSystemConfig(
        id="wv16",
        label="WV-style (16-team per classification)",
        description=(
            "One 16-team bracket per classification. Seeded 1-16 by wins then "
            "point differential; first-round pairings 1v16, 2v15, 3v14, 4v13, "
            "5v12, 6v11, 7v10, 8v9. Four rounds: Round of 16 -> Quarterfinal "
            "-> Semifinal -> Championship. Each classification crowns its own "
            "state champion. Same shape as the WV system, just twice the field."
        ),
        bracket_size=16,
        per_classification=True,
        min_teams=16,
    ),
    "regional_4x4": PlayoffSystemConfig(
        id="regional_4x4",
        label="Regional (4 regions x top 4, 16-team per classification)",
        description=(
            "One 16-team bracket per classification, split into 4 regions of "
            "4 qualifiers each. Round 1 (Regional Semifinal): inside each "
            "region the top 4 play 1v4 and 2v3. Round 2 (Regional Final): "
            "the two regional winners meet to crown a regional champion. "
            "Round 3 (Semifinal): the four regional champions are re-seeded "
            "by overall wins / point differential -- highest vs lowest, "
            "middle two vs each other. Round 4 (Championship): state title."
        ),
        bracket_size=16,
        per_classification=True,
        min_teams=16,
        seeding_mode="regional",
        regions_per_class=4,
        teams_per_region=4,
    ),
    "regional_8x4": PlayoffSystemConfig(
        id="regional_8x4",
        label="Regional (4 regions x top 8, 32-team per classification)",
        description=(
            "One 32-team bracket per classification, split into 4 regions of "
            "8 qualifiers each. Designed for much larger regions where every "
            "good team gets a postseason game. Round 1 (Regional "
            "Quarterfinal): inside each region the top 8 play 1v8, 2v7, "
            "3v6, 4v5. Round 2 (Regional Semifinal): the four regional QF "
            "winners play (1/8 winner vs 4/5 winner; 2/7 winner vs 3/6 "
            "winner). Round 3 (Regional Final): the two regional SF winners "
            "meet to crown a regional champion. Round 4 (Semifinal): the "
            "four regional champions are re-seeded by overall wins / point "
            "differential -- highest vs lowest, middle two vs each other. "
            "Round 5 (Championship): state title."
        ),
        bracket_size=32,
        per_classification=True,
        min_teams=32,
        seeding_mode="regional",
        regions_per_class=4,
        teams_per_region=8,
    ),
}


def get_playoff_system(system_id: Optional[str]) -> PlayoffSystemConfig:
    """Resolve a system id to its config, falling back to the default.

    Unknown / empty ids quietly fall back so a typo in league JSON or an
    older save (pre-``playoff_system``) still produces a working bracket.
    """
    sid = (system_id or "").strip().lower()
    if sid in PLAYOFF_SYSTEMS:
        return PLAYOFF_SYSTEMS[sid]
    return PLAYOFF_SYSTEMS[DEFAULT_PLAYOFF_SYSTEM_ID]


def list_playoff_systems() -> Dict[str, PlayoffSystemConfig]:
    """Return all registered systems (used by setup UI / docs / tests)."""
    return dict(PLAYOFF_SYSTEMS)


def ensure_playoff_system_in_state(state: Dict) -> str:
    """
    Mutates ``state`` so it has a ``playoff_system`` id and returns it.

    Pre-``playoff_system`` saves are silently upgraded to the default
    (currently WV).  Unknown ids on existing saves are normalized to the
    default so a corrupted / typo'd value can't break playoffs.
    """
    if not isinstance(state, dict):
        return DEFAULT_PLAYOFF_SYSTEM_ID
    raw = state.get("playoff_system")
    if isinstance(raw, str) and raw.strip().lower() in PLAYOFF_SYSTEMS:
        sid = raw.strip().lower()
    else:
        sid = DEFAULT_PLAYOFF_SYSTEM_ID
    state["playoff_system"] = sid
    return sid


def get_state_playoff_system(state: Dict) -> PlayoffSystemConfig:
    """Resolve the active playoff system config for a save state.

    Convenience wrapper: looks up ``state['playoff_system']`` and falls back
    to the default for legacy / malformed saves.
    """
    if not isinstance(state, dict):
        return get_playoff_system(None)
    return get_playoff_system(state.get("playoff_system"))
