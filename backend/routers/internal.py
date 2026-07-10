"""Internal cron / maintenance endpoints."""

from __future__ import annotations

import os

from fastapi import APIRouter, Header, HTTPException

from backend.services.league_notifications import run_notification_tick

router = APIRouter()


@router.post("/league-notifications/tick")
def league_notifications_tick_route(x_cron_secret: str | None = Header(None, alias="X-Cron-Secret")):
    expected = os.environ.get("FND_CRON_SECRET", "").strip()
    if not expected or x_cron_secret != expected:
        raise HTTPException(status_code=403, detail="Forbidden")
    return run_notification_tick()
