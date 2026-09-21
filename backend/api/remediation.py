"""
ORION Remediation API

Permission-gated intervention endpoints.
"""

from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from database.investigation_store import get_investigation
from tools.remediation.process_actions import (
    suspend_and_verify,
)


router = APIRouter(
    prefix="/investigations",
    tags=["remediation"],
)


class SuspendRequest(BaseModel):
    approved: bool = Field(
        ...,
        description="Explicit user approval for the intervention.",
    )

    pid: int = Field(
        ...,
        gt=0,
    )

    process_name: str = Field(
        ...,
        min_length=1,
        max_length=255,
    )

    suspend_seconds: float = Field(
        default=4,
        ge=2,
        le=8,
    )


def _validate_investigation_target(
    investigation: Dict[str, Any],
    pid: int,
    process_name: str,
) -> None:
    """
    Confirm that the requested process was actually part
    of the stored investigation.
    """

    investigation_data = investigation.get(
        "investigation",
        {},
    )

    strongest = investigation_data.get(
        "strongest_evidence"
    )

    if isinstance(strongest, dict):
        strongest_pid = strongest.get("pid")

        if strongest_pid is None:
            pids = strongest.get("pids") or []

            if pid in pids:
                strongest_pid = pid

        strongest_name = strongest.get("process")

        if strongest_name:
            if (
                strongest_pid == pid
                and strongest_name.lower()
                == process_name.lower()
            ):
                return

    # Search supporting evidence.
    evidence = investigation_data.get(
        "evidence",
        [],
    )

    if isinstance(evidence, list):
        for item in evidence:
            if not isinstance(item, dict):
                continue

            item_pid = item.get("pid")
            item_name = (
                item.get("process")
                or item.get("process_name")
            )

            item_pids = item.get("pids") or []

            pid_matches = (
                item_pid == pid
                or pid in item_pids
            )

            name_matches = (
                not item_name
                or item_name.lower()
                == process_name.lower()
            )

            if pid_matches and name_matches:
                return

    raise HTTPException(
        status_code=400,
        detail=(
            "The requested process was not verified "
            "as part of this investigation."
        ),
    )


@router.post(
    "/{investigation_id}/actions/suspend",
)
def suspend_investigated_process(
    investigation_id: str,
    request: SuspendRequest,
):
    """
    Temporarily suspend an investigated process,
    re-measure system CPU, then resume it.
    """

    if not request.approved:
        raise HTTPException(
            status_code=403,
            detail="Explicit user approval is required.",
        )

    investigation = get_investigation(
        investigation_id
    )

    if investigation is None:
        raise HTTPException(
            status_code=404,
            detail="Investigation not found.",
        )

    _validate_investigation_target(
        investigation=investigation,
        pid=request.pid,
        process_name=request.process_name,
    )

    try:
        result = suspend_and_verify(
            pid=request.pid,
            expected_process_name=request.process_name,
            suspend_seconds=request.suspend_seconds,
        )

        result["investigation_id"] = investigation_id

        return result

    except PermissionError as error:
        raise HTTPException(
            status_code=403,
            detail=str(error),
        )

    except ValueError as error:
        raise HTTPException(
            status_code=400,
            detail=str(error),
        )

    except RuntimeError as error:
        raise HTTPException(
            status_code=500,
            detail=str(error),
        )

    except Exception:
        raise HTTPException(
            status_code=500,
            detail=(
                "ORION could not complete the "
                "requested intervention."
            ),
        )