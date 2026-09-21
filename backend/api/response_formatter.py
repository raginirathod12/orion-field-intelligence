"""
ORION Structured Response Formatter

Converts ORION's final text response into structured data for the
dashboard/API.

This module:

- does NOT perform investigation
- does NOT modify the investigation engine
- does NOT invent missing telemetry
- merges evidence belonging to the same process
- preserves evidence states such as WEAKENED / SUPPORTED_CANDIDATE
- repairs common UTF-8/mojibake corruption
"""

import re
from typing import Any, Dict, List, Optional


# ============================================================================
# STRUCTURED EVIDENCE MAPPINGS
#
# These map the small, FIXED set of enum strings that
# tools/evidence_fusion.py itself produces (verified against that
# file directly) onto display-friendly statuses. This is not prose
# parsing: evidence_fusion.py only ever emits one of the values on
# the left, deterministically, so this is a closed, exhaustive
# mapping rather than a best-effort regex guess.
# ============================================================================

_GPU_STATUS_MAP = {
    "GPU_ACTIVITY_OBSERVED": "ACTIVE",
    "NO_SIGNIFICANT_ACTIVITY_OBSERVED": "IDLE",
    "NOT_TESTED": "UNKNOWN",
}

_STORAGE_STATUS_MAP = {
    "SUPPORTED_STORAGE_LATENCY": "WARNING",
    "POSSIBLE_STORAGE_LATENCY": "WARNING",
    "STORAGE_LATENCY_NOT_SUPPORTED": "HEALTHY",
    "NOT_TESTED": "UNKNOWN",
}

_MEMORY_STATUS_MAP = {
    "SUPPORTED_MEMORY_PRESSURE": "WARNING",
    "POSSIBLE_MEMORY_PRESSURE": "WARNING",
    "MEMORY_PRESSURE_NOT_SUPPORTED": "HEALTHY",
    "NOT_TESTED": "UNKNOWN",
}


def _group_candidates_by_process(
    candidates: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """
    tools/evidence_fusion.py produces one candidate per PID (each
    OS process is measured independently, correctly). For display,
    group candidates that share the same process name into one
    row, since e.g. two python3.13.exe processes are the same
    program to a user reading a dashboard. The representative
    cpu/temporal/classification/score shown is taken from
    whichever instance has the highest evidence_score (the most
    decision-relevant one); every individual instance is preserved
    under "instances" so no data is lost, and "pids" lists every
    real PID -- never a fabricated merged average.
    """

    groups: Dict[str, List[Dict[str, Any]]] = {}
    order: List[str] = []

    for candidate in candidates:

        name = candidate.get("process") or "unknown"

        if name not in groups:
            groups[name] = []
            order.append(name)

        groups[name].append(candidate)

    grouped = []

    for name in order:

        instances = sorted(
            groups[name],
            key=lambda item: item.get("evidence_score", 0) or 0,
            reverse=True,
        )

        strongest = instances[0]

        pids = [
            item.get("pid")
            for item in instances
            if item.get("pid") is not None
        ]

        row = {
            "process": name,
            "pid": pids[0] if len(pids) == 1 else None,
            "pids": pids if len(pids) > 1 else [],
            "cpu_percent": strongest.get("cpu_percent"),
            "memory_percent": strongest.get("memory_percent"),
            "temporal_behavior": strongest.get(
                "temporal_status", "UNKNOWN"
            ),
            "score": strongest.get("evidence_score"),
            "fusion_score": strongest.get("evidence_score"),
            "classification": strongest.get("classification"),
            "confidence": strongest.get("confidence"),
            "deep_status": strongest.get("deep_status"),
            "evidence": strongest.get("evidence", []),
            "instances": instances,
        }

        grouped.append(row)

    return grouped


# ============================================================================
# TEXT CLEANING
# ============================================================================

def _clean(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _fix_encoding(text: str) -> str:
    """
    Repair common UTF-8 mojibake.

    Examples:
        â€“  -> –
        â€”  -> —
        â€™  -> ’
        â†’  -> →
        â€¢  -> •
    """

    text = _clean(text)

    if not text:
        return ""

    try:
        if any(
            marker in text
            for marker in ("â", "Â", "ð", "Ã")
        ):
            repaired = (
                text
                .encode("latin1", errors="ignore")
                .decode("utf-8", errors="ignore")
            )

            if repaired:
                text = repaired

    except Exception:
        pass

    replacements = {
        "â¯": " ",
        "Â ": " ",
        "Â": "",
        "â€“": "–",
        "â€”": "—",
        "â€˜": "‘",
        "â€™": "’",
        "â€œ": "“",
        "â€": "”",
        "â€¦": "…",
        "â†’": "→",
        "â†": "←",
        "â†‘": "↑",
        "â†“": "↓",
        "â‰ˆ": "≈",
        "â‰¤": "≤",
        "â‰¥": "≥",
        "â€¢": "•",
    }

    for bad, good in replacements.items():
        text = text.replace(bad, good)

    # Normalize spaces/tabs without destroying newlines.
    text = re.sub(r"[ \t]+", " ", text)

    return text.strip()


def _strip_markdown(text: str) -> str:
    text = _fix_encoding(text)

    text = text.replace("**", "")
    text = text.replace("__", "")

    text = re.sub(
        r"^\s*#+\s*",
        "",
        text,
    )

    text = re.sub(
        r"^\s*[-*•]\s*",
        "",
        text,
    )

    return text.strip()


# ============================================================================
# HEADINGS / SECTIONS
# ============================================================================

def _normalize_heading(line: str) -> str:
    value = _fix_encoding(line)

    value = re.sub(
        r"^\s*#+\s*",
        "",
        value,
    )

    value = value.replace("**", "")
    value = value.replace("__", "")

    value = value.rstrip(":").strip()

    return value.upper()


def _extract_sections(text: str) -> Dict[str, str]:
    text = _fix_encoding(text)

    sections = {
        "observation": "",
        "evidence": "",
        "likely_causes": "",
        "confidence": "",
        "next_step": "",
    }

    section_map = {
        "OBSERVATION": "observation",
        "EVIDENCE": "evidence",
        "LIKELY CAUSES": "likely_causes",
        "CONFIDENCE": "confidence",
        "NEXT STEP": "next_step",
    }

    current_section = None

    for raw_line in text.splitlines():

        line = _fix_encoding(raw_line)

        normalized = _normalize_heading(line)

        if normalized in section_map:
            current_section = section_map[normalized]
            continue

        if current_section is None:
            continue

        if not line.strip():
            continue

        if sections[current_section]:
            sections[current_section] += "\n"

        sections[current_section] += line.strip()

    return sections


# ============================================================================
# NUMERIC EXTRACTION
# ============================================================================

def _number(
    pattern: str,
    text: str,
) -> Optional[float]:

    match = re.search(
        pattern,
        text,
        flags=re.IGNORECASE,
    )

    if not match:
        return None

    try:
        return float(match.group(1))
    except (TypeError, ValueError):
        return None


def _integer(
    pattern: str,
    text: str,
) -> Optional[int]:

    match = re.search(
        pattern,
        text,
        flags=re.IGNORECASE,
    )

    if not match:
        return None

    try:
        return int(match.group(1))
    except (TypeError, ValueError):
        return None


def _normalize_number(
    value: Optional[float],
):
    if value is None:
        return None

    if float(value).is_integer():
        return int(value)

    return round(float(value), 2)


# ============================================================================
# PROCESS
# ============================================================================

def _extract_process(
    text: str,
) -> Optional[str]:

    text = _fix_encoding(text)

    patterns = [
        r"\b([A-Za-z0-9_.-]+\.exe)\b",
        r"\b(chrome)\b",
        r"\b(edge)\b",
        r"\b(firefox)\b",
        r"\b(python3(?:\.\d+)?)\b",
        r"\b(python)\b",
    ]

    for pattern in patterns:

        match = re.search(
            pattern,
            text,
            flags=re.IGNORECASE,
        )

        if not match:
            continue

        process = match.group(1).strip()
        lower = process.lower()

        if lower == "chrome":
            return "chrome.exe"

        if lower == "edge":
            return "edge.exe"

        if lower == "firefox":
            return "firefox.exe"

        if lower == "python":
            return "python.exe"

        if lower.startswith("python3"):
            if not lower.endswith(".exe"):
                return process + ".exe"

        return process

    return None


def _extract_pid(
    text: str,
) -> Optional[int]:

    text = _fix_encoding(text)

    patterns = [
        r"\bPID\s*[:#-]?\s*(\d+)\b",
        r"\bprocess\s+ID\s*[:#-]?\s*(\d+)\b",
    ]

    for pattern in patterns:

        value = _integer(
            pattern,
            text,
        )

        if value is not None:
            return value

    return None


def _extract_cpu(
    text: str,
) -> Optional[float]:

    text = _fix_encoding(text)

    patterns = [
        r"(\d+(?:\.\d+)?)\s*%\s*CPU\b",

        r"\bCPU\s*"
        r"(?:usage|load)?"
        r"\s*[:=]?\s*"
        r"(\d+(?:\.\d+)?)\s*%",

        r"\bCPU\s*[:=]\s*"
        r"(\d+(?:\.\d+)?)\b",
    ]

    for pattern in patterns:

        value = _number(
            pattern,
            text,
        )

        if value is not None:
            return _normalize_number(value)

    return None


def _extract_cpu_range(text: str):
    text = _fix_encoding(text)

    patterns = [
        r"(\d+(?:\.\d+)?)\s*[-–]\s*(\d+(?:\.\d+)?)\s*%",
        r"(\d+(?:\.\d+)?)\s+to\s+(\d+(?:\.\d+)?)\s*%",
    ]

    for pattern in patterns:

        match = re.search(
            pattern,
            text,
            flags=re.IGNORECASE,
        )

        if not match:
            continue

        low = float(match.group(1))
        high = float(match.group(2))

        return {
            "min": _normalize_number(low),
            "max": _normalize_number(high),
        }

    return None


# ============================================================================
# SCORES
# ============================================================================

def _extract_anomaly_score(
    text: str,
) -> Optional[int]:

    text = _fix_encoding(text)

    patterns = [
        r"\banomaly\s+score\s*[:=]?\s*(\d+)",
        r"\bscore\s*[:=]?\s*(\d+)",
    ]

    for pattern in patterns:

        value = _integer(
            pattern,
            text,
        )

        if value is not None:
            return value

    return None


def _extract_fusion_score(
    text: str,
) -> Optional[int]:

    text = _fix_encoding(text)

    patterns = [
        r"\bfusion\s+(?:result|score)\D*(\d+)",

        r"\bclassified\s+as.*?"
        r"\(?\s*score\s*[:=]?\s*(\d+)\s*\)?",
    ]

    for pattern in patterns:

        value = _integer(
            pattern,
            text,
        )

        if value is not None:
            return value

    return None


# ============================================================================
# CLASSIFICATION
# ============================================================================

def _extract_classification(
    text: str,
) -> Optional[str]:

    text = _fix_encoding(text).upper()

    # Normalize common formatting variants.
    normalized = (
        text
        .replace("-", "_")
        .replace(" ", "_")
    )

    # Negative/specific states must be checked first.
    #
    # Otherwise:
    #
    # "no confirmed root cause"
    #
    # could incorrectly become:
    #
    # "CONFIRMED"

    ordered = [
        "NO_PROCESS_CAUSE_CONFIRMED",
        "REJECTED_CANDIDATE",
        "STRONG_CANDIDATE",
        "SUPPORTED_CANDIDATE",
        "WEAKENED",
        "WEAK_CANDIDATE",
        "CONFIRMED",
        "UNCERTAIN",
    ]

    for classification in ordered:

        if classification in normalized:
            return classification

    return None


# ============================================================================
# TEMPORAL BEHAVIOR
# ============================================================================

def _extract_temporal_behavior(
    text: str,
) -> str:

    text = _fix_encoding(text).upper()

    normalized = (
        text
        .replace("-", "_")
        .replace(" ", "_")
    )

    states = [
        "PERSISTENT",
        "INTERMITTENT",
        "SHORT_SPIKE",
        "LOW_ACTIVITY",
        "SPIKE",
    ]

    for state in states:

        if state in normalized:
            return state

    return "UNKNOWN"


# ============================================================================
# EVIDENCE
# ============================================================================

def _parse_evidence_line(
    line: str,
) -> Optional[Dict[str, Any]]:

    line = _fix_encoding(line)

    if not line:
        return None

    process = _extract_process(line)
    pid = _extract_pid(line)
    cpu = _extract_cpu(line)
    cpu_range = _extract_cpu_range(line)

    score = _extract_anomaly_score(line)
    classification = _extract_classification(line)
    temporal = _extract_temporal_behavior(line)
    fusion_score = _extract_fusion_score(line)

    if (
        process is None
        and pid is None
        and cpu is None
        and cpu_range is None
        and score is None
        and classification is None
        and temporal == "UNKNOWN"
        and fusion_score is None
    ):
        return None

    return {
        "process": process,
        "pid": pid,
        "cpu_percent": cpu,
        "cpu_range": cpu_range,
        "temporal_behavior": temporal,
        "score": score,
        "classification": classification,
        "fusion_score": fusion_score,
        "raw": line,
    }


def _extract_evidence_items(
    evidence_text: str,
) -> List[Dict[str, Any]]:

    evidence_text = _fix_encoding(
        evidence_text
    )

    items = []

    for line in evidence_text.splitlines():

        line = line.strip()

        if not line:
            continue

        line = re.sub(
            r"^\s*[-*•]\s*",
            "",
            line,
        )

        line = re.sub(
            r"^\s*\d+[.)]\s*",
            "",
            line,
        )

        parsed = _parse_evidence_line(
            line
        )

        if parsed:
            items.append(parsed)

    return items


# ============================================================================
# EVIDENCE MERGING
# ============================================================================

def _same_candidate(
    first: Dict[str, Any],
    second: Dict[str, Any],
) -> bool:

    pid_a = first.get("pid")
    pid_b = second.get("pid")

    process_a = (
        first.get("process") or ""
    ).lower()

    process_b = (
        second.get("process") or ""
    ).lower()

    # Same PID = definitely same process.
    if (
        pid_a is not None
        and pid_b is not None
    ):
        return pid_a == pid_b

    # Same process name when PID is unavailable.
    if process_a and process_b:
        return process_a == process_b

    return False


def _merge_evidence(
    items: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:

    merged = []

    temporal_priority = {
        "UNKNOWN": 0,
        "SPIKE": 1,
        "SHORT_SPIKE": 2,
        "LOW_ACTIVITY": 3,
        "INTERMITTENT": 4,
        "PERSISTENT": 5,
    }

    classification_priority = {
        "NO_PROCESS_CAUSE_CONFIRMED": 100,
        "REJECTED_CANDIDATE": 90,
        "WEAKENED": 80,
        "WEAK_CANDIDATE": 70,
        "SUPPORTED_CANDIDATE": 60,
        "STRONG_CANDIDATE": 50,
        "CONFIRMED": 40,
        "UNCERTAIN": 10,
    }

    for item in items:

        existing = None

        for candidate in merged:

            if _same_candidate(
                candidate,
                item,
            ):
                existing = candidate
                break

        if existing is None:

            merged.append(
                {
                    "process": item.get("process"),
                    "pid": item.get("pid"),
                    "cpu_percent": item.get("cpu_percent"),
                    "cpu_range": item.get("cpu_range"),
                    "temporal_behavior": item.get(
                        "temporal_behavior",
                        "UNKNOWN",
                    ),
                    "score": item.get("score"),
                    "classification": item.get(
                        "classification"
                    ),
                    "fusion_score": item.get(
                        "fusion_score"
                    ),
                    "raw": item.get("raw", ""),
                }
            )

            continue

        # Process
        if existing.get("process") is None:
            existing["process"] = item.get("process")

        # PID
        if existing.get("pid") is None:
            existing["pid"] = item.get("pid")

        # CPU
        if existing.get("cpu_percent") is None:
            existing["cpu_percent"] = item.get(
                "cpu_percent"
            )

        # CPU range
        if existing.get("cpu_range") is None:
            existing["cpu_range"] = item.get(
                "cpu_range"
            )

        # Anomaly score
        if existing.get("score") is None:
            existing["score"] = item.get("score")

        # Fusion score
        if existing.get("fusion_score") is None:
            existing["fusion_score"] = item.get(
                "fusion_score"
            )

        # Classification
        old_classification = existing.get(
            "classification"
        )

        new_classification = item.get(
            "classification"
        )

        if new_classification:

            if (
                old_classification is None
                or classification_priority.get(
                    new_classification,
                    0,
                )
                > classification_priority.get(
                    old_classification,
                    0,
                )
            ):
                existing["classification"] = (
                    new_classification
                )

        # Temporal state
        old_temporal = existing.get(
            "temporal_behavior",
            "UNKNOWN",
        )

        new_temporal = item.get(
            "temporal_behavior",
            "UNKNOWN",
        )

        if (
            temporal_priority.get(
                new_temporal,
                0,
            )
            >
            temporal_priority.get(
                old_temporal,
                0,
            )
        ):
            existing["temporal_behavior"] = (
                new_temporal
            )

        # Raw evidence
        old_raw = existing.get(
            "raw",
            "",
        )

        new_raw = item.get(
            "raw",
            "",
        )

        if (
            new_raw
            and new_raw not in old_raw
        ):

            if old_raw:
                existing["raw"] = (
                    old_raw
                    + " | "
                    + new_raw
                )
            else:
                existing["raw"] = new_raw

    return merged


# ============================================================================
# OBSERVATION EVIDENCE
# ============================================================================

def _extract_observation_evidence(
    observation: str,
) -> List[Dict[str, Any]]:

    observation = _fix_encoding(
        observation
    )

    items = []

    for sentence in re.split(
        r"(?<=[.!?])\s+",
        observation,
    ):

        sentence = sentence.strip()

        if not sentence:
            continue

        parsed = _parse_evidence_line(
            sentence
        )

        if parsed:
            items.append(parsed)

    return items


# ============================================================================
# SYSTEM TELEMETRY
# ============================================================================

def _extract_system_cpu(
    text: str,
) -> Optional[float]:

    text = _fix_encoding(text)

    patterns = [
        r"\bSystem\s+CPU\s+(?:is\s+)?(\d+(?:\.\d+)?)\s*%",
        r"\boverall\s+CPU\s+(?:is\s+)?(\d+(?:\.\d+)?)\s*%",
        r"\bCPU\s+(?:is\s+)?(\d+(?:\.\d+)?)\s*%",
    ]

    for pattern in patterns:

        value = _number(
            pattern,
            text,
        )

        if value is not None:
            return _normalize_number(
                value
            )

    return None


def _extract_system_ram(
    text: str,
) -> Optional[float]:

    text = _fix_encoding(text)

    patterns = [
        r"\bRAM\s+(?:is\s+)?(\d+(?:\.\d+)?)\s*%",
        r"\bmemory\s+(?:is\s+)?(\d+(?:\.\d+)?)\s*%\s*(?:used)?",
    ]

    for pattern in patterns:

        value = _number(
            pattern,
            text,
        )

        if value is not None:
            return _normalize_number(
                value
            )

    return None


def _extract_disk_status(
    text: str,
) -> str:

    text = _fix_encoding(text).upper()

    healthy_phrases = [
        "DISK SPACE HEALTHY",
        "STORAGE HEALTHY",
        "DISK HEALTHY",
        "STORAGE CONDITION HEALTHY",
        "AMPLE DISK SPACE",
        "DISK SPACE AMPLE",
        "STORAGE LATENCY NEGLIGIBLE",
        "DISK SPACE AND LATENCY ARE HEALTHY",
        "DISK SPACE AND LATENCY HEALTHY",
    ]

    if any(
        phrase in text
        for phrase in healthy_phrases
    ):
        return "HEALTHY"

    warning_phrases = [
        "DISK SPACE LOW",
        "LOW DISK",
        "STORAGE LOW",
        "DISK WARNING",
        "STORAGE WARNING",
    ]

    if any(
        phrase in text
        for phrase in warning_phrases
    ):
        return "WARNING"

    critical_phrases = [
        "DISK CRITICAL",
        "STORAGE CRITICAL",
        "DISK FAILURE",
        "STORAGE FAILURE",
    ]

    if any(
        phrase in text
        for phrase in critical_phrases
    ):
        return "CRITICAL"

    return "UNKNOWN"


def _extract_gpu_status(
    text: str,
) -> str:

    text = _fix_encoding(text).upper()

    if re.search(
        r"\bGPU\s+(?:IS\s+)?IDLE\b",
        text,
    ):
        return "IDLE"

    if "GPU NEGLIGIBLE" in text:
        return "IDLE"

    if re.search(
        r"\bGPU\s+HIGH\b",
        text,
    ):
        return "HIGH"

    if re.search(
        r"\bGPU\s+LOW\b",
        text,
    ):
        return "LOW"

    if "GPU NORMAL" in text:
        return "NORMAL"

    return "UNKNOWN"


# ============================================================================
# STRONGEST EVIDENCE
# ============================================================================

def _evidence_strength(
    item: Dict[str, Any],
) -> float:

    strength = 0.0

    # Process identity.
    if item.get("pid") is not None:
        strength += 35

    if item.get("process"):
        strength += 20

    # Current CPU observation.
    if item.get("cpu_percent") is not None:
        strength += 30

    # Temporal behavior.
    temporal = item.get(
        "temporal_behavior"
    )

    if temporal not in {
        None,
        "",
        "UNKNOWN",
    }:
        strength += 15

    # Anomaly score.
    anomaly_score = item.get(
        "score"
    )

    if anomaly_score is not None:

        strength += min(
            float(anomaly_score) * 0.15,
            15,
        )

    # Evidence classification.
    classification = item.get(
        "classification"
    )

    classification_bonus = {
        "CONFIRMED": 20,
        "STRONG_CANDIDATE": 18,
        "SUPPORTED_CANDIDATE": 12,
        "WEAK_CANDIDATE": 6,
        "UNCERTAIN": 0,

        # IMPORTANT:
        # Weakened/rejected evidence should NOT
        # become the strongest evidence merely
        # because CPU is high.
        "WEAKENED": -30,
        "REJECTED_CANDIDATE": -50,
        "NO_PROCESS_CAUSE_CONFIRMED": -60,
    }

    if classification:
        strength += classification_bonus.get(
            classification,
            5,
        )

    # Persistent/intermittent behavior is more
    # useful than a short spike.
    temporal_bonus = {
        "PERSISTENT": 20,
        "INTERMITTENT": 12,
        "LOW_ACTIVITY": -8,
        "SHORT_SPIKE": -5,
        "SPIKE": 0,
    }

    strength += temporal_bonus.get(
        temporal,
        0,
    )

    return strength


def _find_strongest_evidence(
    items: List[Dict[str, Any]],
) -> Dict[str, Any]:

    empty_result = {
        "process": None,
        "pid": None,
        "cpu_percent": None,
        "cpu_range": None,
        "temporal_behavior": "UNKNOWN",
        "score": None,
        "classification": None,
        "fusion_score": None,
        "raw": "",
    }

    if not items:
        return empty_result

    # Only use evidence that has not been explicitly
    # rejected/weakened when a better candidate exists.
    usable = [
        item
        for item in items
        if item.get("classification")
        not in {
            "REJECTED_CANDIDATE",
            "NO_PROCESS_CAUSE_CONFIRMED",
        }
    ]

    if not usable:
        usable = items

    return max(
        usable,
        key=_evidence_strength,
    )


# ============================================================================
# ROOT CAUSES
# ============================================================================

def _extract_root_causes(
    likely_causes: str,
) -> List[Dict[str, Any]]:

    likely_causes = _fix_encoding(
        likely_causes
    )

    causes = []

    pattern = re.compile(
        r"(?:^|\n)\s*\d+[.)]\s*(.+?)(?=\n\s*\d+[.)]\s*|\Z)",
        flags=re.DOTALL,
    )

    matches = list(
        pattern.finditer(
            likely_causes
        )
    )

    if matches:

        for match in matches:

            name = match.group(1).strip()

            name = _strip_markdown(
                name
            )

            name = re.sub(
                r"[*_]+$",
                "",
                name,
            ).strip()

            if name:
                causes.append(
                    {
                        "name": name,
                        "confidence": "UNKNOWN",
                        "score": None,
                    }
                )

    else:

        for line in likely_causes.splitlines():

            line = line.strip()

            if not line:
                continue

            line = re.sub(
                r"^\s*[-*•]\s*",
                "",
                line,
            )

            line = _strip_markdown(
                line
            )

            if line:
                causes.append(
                    {
                        "name": line,
                        "confidence": "UNKNOWN",
                        "score": None,
                    }
                )

    return causes[:3]


def _extract_cause_confidences(
    confidence_text: str,
    causes: List[Dict[str, Any]],
) -> None:

    text = _fix_encoding(
        confidence_text
    )

    confidence_values = re.findall(
        r"\b(HIGH|MODERATE|MEDIUM|LOW)\b",
        text,
        flags=re.IGNORECASE,
    )

    normalized = []

    for value in confidence_values:

        value = value.upper()

        if value == "MEDIUM":
            value = "MODERATE"

        normalized.append(value)

    for index, cause in enumerate(
        causes
    ):

        if index < len(normalized):
            cause["confidence"] = normalized[index]


def _determine_root_cause_status(
    evidence: List[Dict[str, Any]],
) -> str:

    classifications = [
        item.get("classification")
        for item in evidence
        if item.get("classification")
    ]

    # Explicit negative state wins.
    if (
        "NO_PROCESS_CAUSE_CONFIRMED"
        in classifications
    ):
        return "NO_CONFIRMED_CAUSE"

    if "REJECTED_CANDIDATE" in classifications:
        return "REJECTED_CANDIDATE"

    if "WEAKENED" in classifications:
        return "WEAKENED"

    if "STRONG_CANDIDATE" in classifications:
        return "STRONG_CANDIDATE"

    if "SUPPORTED_CANDIDATE" in classifications:
        return "SUPPORTED_CANDIDATE"

    if "CONFIRMED" in classifications:
        return "CONFIRMED"

    if "WEAK_CANDIDATE" in classifications:
        return "WEAK_CANDIDATE"

    if "UNCERTAIN" in classifications:
        return "UNCERTAIN"

    # Text fallback.
    all_raw = " ".join(
        item.get("raw", "")
        for item in evidence
    )

    all_raw_upper = _fix_encoding(
        all_raw
    ).upper()

    if "NO CONFIRMED ROOT CAUSE" in all_raw_upper:
        return "NO_CONFIRMED_CAUSE"

    if "CLASSIFIED AS WEAKENED" in all_raw_upper:
        return "WEAKENED"

    return "NO_CONFIRMED_CAUSE"


# ============================================================================
# OVERALL CONFIDENCE
# ============================================================================

def _extract_overall_confidence(
    confidence_text: str,
) -> str:

    text = _fix_encoding(
        confidence_text
    )

    match = re.search(
        r"\b(HIGH|MODERATE|MEDIUM|LOW)\b",
        text,
        flags=re.IGNORECASE,
    )

    if not match:
        return "UNKNOWN"

    value = match.group(1).upper()

    if value == "MEDIUM":
        return "MODERATE"

    return value


# ============================================================================
# MAIN FORMATTER
# ============================================================================

def format_orion_response(
    user_question: str,
    intent: str,
    response_text: str,
    structured_evidence: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:

    # ----------------------------------------------------------------------
    # Clean original response.
    # ----------------------------------------------------------------------

    response_text = _fix_encoding(
        response_text
    )

    # ----------------------------------------------------------------------
    # Extract ORION sections.
    #
    # This part always runs, structured evidence or not: the
    # OBSERVATION/EVIDENCE/LIKELY CAUSES/CONFIDENCE/NEXT STEP
    # headings are reliable to split on (the LLM is instructed to
    # use exactly these), and this text is for human reading, not
    # for driving numeric/structured fields below.
    # ----------------------------------------------------------------------

    sections = _extract_sections(
        response_text
    )

    # ----------------------------------------------------------------------
    # Decide whether real structured evidence is available. If the
    # investigation engine already computed it (fused_evidence with
    # real candidates), that is used directly below instead of
    # regex-parsing the prose. If not (e.g. a GENERAL question, or
    # investigation/fusion failed), fall back to the original
    # prose-parsing behavior so nothing regresses.
    # ----------------------------------------------------------------------

    fused_evidence = (
        (structured_evidence or {}).get("fused_evidence") or {}
    )

    system_info = (
        (structured_evidence or {}).get("system_info") or {}
    )

    has_structured_evidence = bool(
        fused_evidence.get("candidates")
    )

    if has_structured_evidence:

        # ------------------------------------------------------
        # STRUCTURED PATH -- no regex, real data only.
        # ------------------------------------------------------

        confidence = _extract_overall_confidence(
            sections["confidence"]
        )

        evidence = _group_candidates_by_process(
            fused_evidence.get("candidates", [])
        )

        cpu_percent = _normalize_number(
            system_info.get("cpu_usage_percent")
        )

        ram_percent = _normalize_number(
            system_info.get("ram_usage_percent")
        )

        disk_status = _STORAGE_STATUS_MAP.get(
            fused_evidence.get(
                "storage_evidence", {}
            ).get("status"),
            "UNKNOWN",
        )

        gpu_status = _GPU_STATUS_MAP.get(
            fused_evidence.get(
                "gpu_evidence", {}
            ).get("status"),
            "UNKNOWN",
        )

        memory_status = _MEMORY_STATUS_MAP.get(
            fused_evidence.get(
                "memory_evidence", {}
            ).get("status"),
            "UNKNOWN",
        )

        # evidence_fusion.py already sorts candidates by
        # evidence_score descending and hands us the top one
        # directly -- no need to recompute "strength" from prose.
        strongest_raw = fused_evidence.get("strongest_candidate")

        if strongest_raw:
            strongest = {
                "process": strongest_raw.get("process"),
                "pid": strongest_raw.get("pid"),
                "cpu_percent": strongest_raw.get("cpu_percent"),
                "temporal_behavior": strongest_raw.get(
                    "temporal_status", "UNKNOWN"
                ),
                "score": strongest_raw.get("evidence_score"),
                "fusion_score": strongest_raw.get(
                    "evidence_score"
                ),
                "classification": strongest_raw.get(
                    "classification"
                ),
                "confidence": strongest_raw.get("confidence"),
            }
        else:
            strongest = {
                "process": None,
                "pid": None,
                "cpu_percent": None,
                "temporal_behavior": "UNKNOWN",
                "score": None,
                "fusion_score": None,
                "classification": None,
                "confidence": None,
            }

        # Root causes come directly from the top real candidates
        # -- their classification is never upgraded to CONFIRMED
        # here; it is passed through exactly as evidence_fusion.py
        # computed it.
        root_causes = [
            {
                "name": candidate.get("process"),
                "confidence": candidate.get("confidence", "UNKNOWN"),
                "score": candidate.get("evidence_score"),
                "classification": candidate.get("classification"),
            }
            for candidate in fused_evidence.get(
                "candidates", []
            )[:3]
        ]

        root_cause_status = fused_evidence.get(
            "system_conclusion", "NO_PROCESS_CAUSE_CONFIRMED"
        )

    else:

        # ------------------------------------------------------
        # FALLBACK PATH -- original prose-parsing behavior,
        # unchanged, used only when no structured evidence was
        # supplied (e.g. GENERAL questions have nothing to
        # structure) or investigation/fusion failed upstream.
        # ------------------------------------------------------

        confidence = _extract_overall_confidence(
            sections["confidence"]
        )

        evidence = _extract_evidence_items(
            sections["evidence"]
        )

        observation_evidence = (
            _extract_observation_evidence(
                sections["observation"]
            )
        )

        for item in observation_evidence:

            if (
                item.get("pid") is not None
                or item.get("cpu_percent") is not None
                or item.get("score") is not None
            ):
                evidence.append(item)

        evidence = _merge_evidence(
            evidence
        )

        full_text = (
            response_text
            + "\n"
            + sections["observation"]
            + "\n"
            + sections["evidence"]
        )

        cpu_percent = _extract_system_cpu(
            full_text
        )

        ram_percent = _extract_system_ram(
            full_text
        )

        disk_status = _extract_disk_status(
            full_text
        )

        gpu_status = _extract_gpu_status(
            full_text
        )

        memory_status = "UNKNOWN"

        strongest = _find_strongest_evidence(
            evidence
        )

        root_causes = _extract_root_causes(
            sections["likely_causes"]
        )

        _extract_cause_confidences(
            sections["confidence"],
            root_causes,
        )

        root_cause_status = (
            _determine_root_cause_status(
                evidence
            )
        )

    # ----------------------------------------------------------------------
    # Investigation stages.
    #
    # NOTE:
    # These represent the completed investigation returned by
    # ORION. They are not fake live progress indicators.
    # ----------------------------------------------------------------------

    stages = {
        "understanding": "completed",
        "telemetry": "completed",
        "anomaly_detection": "completed",
        "root_cause_analysis": "completed",
        "investigation": "completed",
        "evidence_fusion": "completed",
        "diagnosis": "completed",
    }

    # ----------------------------------------------------------------------
    # Final structured response.
    # ----------------------------------------------------------------------

    return {
        "success": True,

        "intent": _clean(
            intent
        ),

        "status": "completed",

        "response": response_text,

        "investigation": {

            "request": _fix_encoding(
                user_question
            ),

            "stages": stages,

            "system": {
                "cpu_percent": cpu_percent,
                "ram_percent": ram_percent,
                "disk_status": disk_status,
                "disk_free_gb": system_info.get("disk_free_gb"),
                "disk_total_gb": system_info.get("disk_total_gb"),
                "gpu_status": gpu_status,
                "memory_pressure_status": memory_status,
            },

            "evidence": evidence,

            "strongest_evidence": strongest,

            "root_cause_status": root_cause_status,

            "root_causes": root_causes,
        },

        "diagnosis": {

            "observation": sections[
                "observation"
            ],

            "evidence": sections[
                "evidence"
            ],

            "likely_causes": sections[
                "likely_causes"
            ],

            "confidence": confidence,

            "next_step": sections[
                "next_step"
            ],
        },
    }