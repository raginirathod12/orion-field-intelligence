"""
ORION Background Watcher

Runs continuously while the backend is up.
Every N seconds it checks system health.
If CPU or RAM exceeds a threshold, it triggers an ORION investigation
and saves the result as a finding.

The watcher never takes action on its own.
It only investigates and records.
"""

from __future__ import annotations

import asyncio
import os
import time
from typing import Optional

import psutil

from agents.orion_agent import orion
from database.findings_store import (
    get_latest_finding_for_kind,
    save_finding,
)
from database.investigation_store import save_investigation


# -------------------------------------------------------------------
# Configuration (env vars with sane defaults)
# -------------------------------------------------------------------

WATCHER_ENABLED = (
    os.getenv("ORION_WATCHER_ENABLED", "true").strip().lower()
    in ("1", "true", "yes", "on")
)

CHECK_INTERVAL_SECONDS = float(
    os.getenv("ORION_WATCHER_INTERVAL", "30")
)

CPU_THRESHOLD = float(
    os.getenv("ORION_CPU_THRESHOLD", "70")
)

RAM_THRESHOLD = float(
    os.getenv("ORION_RAM_THRESHOLD", "80")
)

# If an investigation takes too long, skip the next cycles.
# This also protects against runaway loops.
MIN_SECONDS_BETWEEN_SAME_KIND = float(
    os.getenv("ORION_WATCHER_COOLDOWN", "300")
)


# -------------------------------------------------------------------
# Internal state
# -------------------------------------------------------------------

_task: Optional[asyncio.Task] = None
_running = False
_investigation_lock = asyncio.Lock()


# -------------------------------------------------------------------
# Helpers
# -------------------------------------------------------------------

def _recent(kind: str) -> bool:
    """Return True if a finding for this kind was saved recently."""
    latest = get_latest_finding_for_kind(kind)
    if latest is None:
        return False

    from datetime import datetime, timezone

    try:
        created = datetime.fromisoformat(
            latest["created_at"].replace("Z", "+00:00")
        )
    except Exception:
        return False

    age = (
        datetime.now(timezone.utc) - created
    ).total_seconds()

    return age < MIN_SECONDS_BETWEEN_SAME_KIND


async def _measure_async() -> dict:
    """Collect CPU and RAM without blocking the event loop."""
    cpu = await asyncio.to_thread(psutil.cpu_percent, 1)
    ram = psutil.virtual_memory().percent
    return {"cpu": float(cpu), "ram": float(ram)}


async def _run_investigation(message: str) -> Optional[dict]:
    """Run ORION in a thread so the event loop stays responsive."""
    async with _investigation_lock:
        try:
            return await asyncio.to_thread(
                orion.process_structured, message
            )
        except Exception as error:
            print(f"[WATCHER] Investigation failed: {error}")
            return None


# -------------------------------------------------------------------
# Alert generation
# -------------------------------------------------------------------

async def _check_once() -> None:
    """One pass of the watcher loop."""
    telemetry = await _measure_async()
    cpu = telemetry["cpu"]
    ram = telemetry["ram"]

    # CPU check
    if cpu >= CPU_THRESHOLD and not _recent("high_cpu"):
        await _emit_finding(
            kind="high_cpu",
            severity="WARNING" if cpu < 85 else "CRITICAL",
            title=f"High CPU detected ({cpu:.0f}%)",
            summary=f"System CPU reached {cpu:.1f}%. Triggering investigation.",
            message="My CPU is high. Investigate.",
        )

    # RAM check
    elif ram >= RAM_THRESHOLD and not _recent("high_ram"):
        await _emit_finding(
            kind="high_ram",
            severity="WARNING" if ram < 90 else "CRITICAL",
            title=f"High memory usage detected ({ram:.0f}%)",
            summary=f"RAM usage reached {ram:.1f}%. Triggering investigation.",
            message="My memory is high. Investigate.",
        )


async def _emit_finding(
    kind: str,
    severity: str,
    title: str,
    summary: str,
    message: str,
) -> None:
    """Run an investigation and save the finding."""
    print(f"[WATCHER] {title}")

    result = await _run_investigation(message)

    investigation_id = None
    if result and isinstance(result, dict):
        # Persist the full investigation
        investigation_id = save_investigation(
            question=message,
            result=result,
        )
        result["investigation_id"] = investigation_id

        # Try to enrich the summary with a real candidate if we have one
        try:
            inv = result.get("investigation") or {}
            strongest = inv.get("strongest_evidence") or {}
            if strongest.get("process"):
                name = str(strongest["process"]).replace(".exe", "")
                cpu_val = strongest.get("cpu_percent")
                if cpu_val is not None:
                    summary += (
                        f" Top candidate: {name} at {cpu_val:.0f}% CPU."
                    )
                else:
                    summary += f" Top candidate: {name}."
        except Exception:
            pass

    save_finding(
        severity=severity,
        kind=kind,
        title=title,
        summary=summary,
        investigation_id=investigation_id,
        result=result,
    )


# -------------------------------------------------------------------
# Watcher loop
# -------------------------------------------------------------------

async def _watch_loop() -> None:
    global _running

    _running = True
    print(
        f"[WATCHER] Started. Interval={CHECK_INTERVAL_SECONDS}s, "
        f"CPU>={CPU_THRESHOLD}%, RAM>={RAM_THRESHOLD}%"
    )

    # Small initial delay so backend fully boots
    await asyncio.sleep(5)

    while _running:
        try:
            await _check_once()
        except asyncio.CancelledError:
            break
        except Exception as error:
            print(f"[WATCHER] Loop error: {error}")

        try:
            await asyncio.sleep(CHECK_INTERVAL_SECONDS)
        except asyncio.CancelledError:
            break

    print("[WATCHER] Stopped.")


# -------------------------------------------------------------------
# Public API
# -------------------------------------------------------------------

def start_watcher() -> Optional[asyncio.Task]:
    """Called on backend startup."""
    global _task

    if not WATCHER_ENABLED:
        print("[WATCHER] Disabled via ORION_WATCHER_ENABLED.")
        return None

    if _task is not None and not _task.done():
        return _task

    _task = asyncio.create_task(_watch_loop())
    return _task


async def stop_watcher() -> None:
    """Called on backend shutdown."""
    global _task, _running

    _running = False

    if _task is None:
        return

    _task.cancel()
    try:
        await _task
    except (asyncio.CancelledError, Exception):
        pass

    _task = None


async def force_check_now() -> dict:
    """Manually trigger a single check (useful for testing)."""
    await _check_once()
    return {"success": True, "checked": True}