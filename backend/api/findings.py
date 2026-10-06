"""
ORION Findings API

Exposes the automatic findings produced by the background watcher.
"""

from __future__ import annotations

from fastapi import APIRouter

from database.findings_store import (
    clear_findings,
    list_findings,
)
from monitoring.watcher import (
    CHECK_INTERVAL_SECONDS,
    CPU_THRESHOLD,
    RAM_THRESHOLD,
    WATCHER_ENABLED,
    force_check_now,
)


router = APIRouter(
    prefix="/findings",
    tags=["findings"],
)


@router.get("")
def get_findings(limit: int = 10):
    return {
        "success": True,
        "watcher_enabled": WATCHER_ENABLED,
        "interval_seconds": CHECK_INTERVAL_SECONDS,
        "cpu_threshold": CPU_THRESHOLD,
        "ram_threshold": RAM_THRESHOLD,
        "findings": list_findings(limit),
    }


@router.post("/check-now")
async def check_now():
    """Manually trigger one watcher cycle (useful for testing)."""
    return await force_check_now()


@router.post("/clear")
def clear_all():
    count = clear_findings()
    return {"success": True, "cleared": count}