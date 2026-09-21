"""
ORION Remediation Action Policy

Controls which processes ORION is allowed to temporarily suspend.

The policy is intentionally conservative.
"""

from __future__ import annotations

from typing import Optional


# Processes that should never be suspended by ORION.
PROTECTED_PROCESS_NAMES = {
    "system",
    "system idle process",
    "registry",
    "smss.exe",
    "csrss.exe",
    "wininit.exe",
    "services.exe",
    "lsass.exe",
    "winlogon.exe",
    "svchost.exe",
    "fontdrvhost.exe",
    "dwm.exe",
    "explorer.exe",
    "conhost.exe",
}


ALLOWED_ACTIONS = {
    "SUSPEND_PROCESS",
}


def normalize_process_name(name: Optional[str]) -> str:
    if not name:
        return ""

    return name.strip().lower()


def is_protected_process(name: Optional[str]) -> bool:
    normalized = normalize_process_name(name)

    return normalized in PROTECTED_PROCESS_NAMES


def validate_suspend_target(
    pid: int,
    process_name: Optional[str],
) -> tuple[bool, str]:
    """
    Validate a process before allowing a temporary suspension.
    """

    if not isinstance(pid, int):
        return False, "Invalid process ID."

    if pid <= 0:
        return False, "Invalid process ID."

    normalized_name = normalize_process_name(process_name)

    if not normalized_name:
        return False, "Process name is required."

    if is_protected_process(normalized_name):
        return (
            False,
            f"Process '{process_name}' is protected and cannot be suspended.",
        )

    return True, "Process is eligible for temporary suspension."


def is_action_allowed(action: str) -> bool:
    if not action:
        return False

    return action.upper() in ALLOWED_ACTIONS