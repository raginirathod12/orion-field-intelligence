"""
ORION Safe Process Remediation

Provides a narrowly scoped process intervention:

    measure
        ↓
    suspend
        ↓
    measure
        ↓
    resume
        ↓
    verify

ORION does not terminate processes.
"""

from __future__ import annotations

import time
from typing import Any, Dict

import psutil

from tools.remediation.action_policy import (
    validate_suspend_target,
)


DEFAULT_SUSPEND_SECONDS = 4
DEFAULT_MEASUREMENT_SECONDS = 2


def _measure_system_cpu(
    seconds: float = DEFAULT_MEASUREMENT_SECONDS,
) -> float:
    """
    Measure system-wide CPU usage.
    """

    seconds = max(
        0.5,
        min(float(seconds), 5.0),
    )

    return round(
        float(
            psutil.cpu_percent(
                interval=seconds
            )
        ),
        2,
    )


def _measure_process_cpu(
    process: psutil.Process,
    seconds: float = 1.0,
) -> float | None:
    """
    Measure CPU usage for the target process.
    """

    try:
        process.cpu_percent(interval=None)

        time.sleep(
            max(
                0.2,
                min(float(seconds), 3.0),
            )
        )

        return round(
            float(
                process.cpu_percent(
                    interval=None
                )
            ),
            2,
        )

    except (
        psutil.NoSuchProcess,
        psutil.AccessDenied,
    ):
        return None


def suspend_and_verify(
    pid: int,
    expected_process_name: str,
    suspend_seconds: float = DEFAULT_SUSPEND_SECONDS,
) -> Dict[str, Any]:
    """
    Temporarily suspend a process, measure system behavior,
    resume the process, and return verification evidence.

    This function never terminates the process.
    """

    if not isinstance(pid, int) or pid <= 0:
        raise ValueError("Invalid process ID.")

    if not expected_process_name:
        raise ValueError(
            "Expected process name is required."
        )

    suspend_seconds = max(
        2.0,
        min(float(suspend_seconds), 8.0),
    )

    try:
        process = psutil.Process(pid)
    except psutil.NoSuchProcess:
        raise ValueError(
            f"Process PID {pid} no longer exists."
        )

    # --------------------------------------------------
    # Verify process identity BEFORE doing anything.
    # --------------------------------------------------

    try:
        actual_name = process.name()
    except (
        psutil.NoSuchProcess,
        psutil.AccessDenied,
    ):
        raise ValueError(
            f"Unable to identify process PID {pid}."
        )

    if actual_name.lower() != expected_process_name.lower():
        raise ValueError(
            "Process identity changed. "
            f"Expected '{expected_process_name}', "
            f"but PID {pid} is now '{actual_name}'."
        )

    # --------------------------------------------------
    # Apply ORION safety policy.
    # --------------------------------------------------

    allowed, reason = validate_suspend_target(
        pid=pid,
        process_name=actual_name,
    )

    if not allowed:
        raise PermissionError(reason)

    # --------------------------------------------------
    # BEFORE measurement.
    # --------------------------------------------------

    before_cpu = _measure_system_cpu()

    process_cpu_before = _measure_process_cpu(
        process,
        seconds=1.0,
    )

    # --------------------------------------------------
    # SUSPEND.
    # --------------------------------------------------

    suspended_at = time.time()

    try:
        process.suspend()

    except (
        psutil.NoSuchProcess,
        psutil.AccessDenied,
        psutil.Error,
    ) as error:

        raise RuntimeError(
            f"Unable to suspend PID {pid}: {error}"
        )

    # --------------------------------------------------
    # Intervention window.
    # --------------------------------------------------

    time.sleep(suspend_seconds)

    # --------------------------------------------------
    # AFTER measurement while target is suspended.
    # --------------------------------------------------

    after_cpu = _measure_system_cpu()

    # --------------------------------------------------
    # ALWAYS attempt to resume.
    # --------------------------------------------------

    resumed = False

    try:
        process.resume()
        resumed = True

    except (
        psutil.NoSuchProcess,
        psutil.AccessDenied,
        psutil.Error,
    ):
        resumed = False

    resumed_at = time.time()

    # --------------------------------------------------
    # Verification calculations.
    # --------------------------------------------------

    cpu_change = round(
        after_cpu - before_cpu,
        2,
    )

    cpu_improvement = round(
        before_cpu - after_cpu,
        2,
    )

    if cpu_improvement > 5:
        verification = (
            "SUPPORTED_BY_INTERVENTION"
        )

    elif cpu_improvement > 0:
        verification = (
            "WEAK_INTERVENTION_SIGNAL"
        )

    else:
        verification = (
            "NO_MEASURED_IMPROVEMENT"
        )

    if cpu_improvement > 0:
        evidence = (
            "System CPU decreased during the "
            "temporary suspension of the target process."
        )
    else:
        evidence = (
            "No measurable system CPU improvement "
            "was observed during the intervention window."
        )

    return {
        "success": True,
        "action": "SUSPEND_AND_VERIFY",
        "pid": pid,
        "process_name": actual_name,
        "policy": {
            "allowed": True,
            "reason": reason,
        },
        "measurement": {
            "cpu_before": before_cpu,
            "cpu_after": after_cpu,
            "cpu_change": cpu_change,
            "cpu_improvement": cpu_improvement,
            "process_cpu_before": process_cpu_before,
        },
        "intervention": {
            "suspend_seconds": suspend_seconds,
            "suspended_at": suspended_at,
            "resumed_at": resumed_at,
            "resumed": resumed,
        },
        "verification": {
            "status": verification,
            "evidence": evidence,
        },
    }