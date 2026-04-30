"""Rules for offensive/defensive preferred playbooks (formation labels): change at most once every N seasons."""

from __future__ import annotations

from typing import Any

PREFERRED_PLAYBOOK_CHANGE_INTERVAL_SEASONS = 5


def coach_may_change_preferred_playbooks(coach: Any, current_year: int) -> bool:
    """If False, offensive/defensive playbook labels must not change this season."""
    last = int(getattr(coach, "last_preferred_playbook_change_year", 0) or 0)
    if last <= 0:
        return True
    cy = int(current_year)
    return cy >= last + PREFERRED_PLAYBOOK_CHANGE_INTERVAL_SEASONS


def coach_record_preferred_playbook_change(coach: Any, current_year: int) -> None:
    setattr(coach, "last_preferred_playbook_change_year", int(current_year))


def next_eligible_season_for_preferred_playbooks(coach: Any) -> int:
    """Minimum season year when playbook labels may change again."""
    last = int(getattr(coach, "last_preferred_playbook_change_year", 0) or 0)
    if last <= 0:
        return 0  # caller: no lock
    return last + PREFERRED_PLAYBOOK_CHANGE_INTERVAL_SEASONS
