def _collect_tool_data(
    additional_evidence
):
    """
    Extract the latest result from each investigation tool.
    """

    results = {}

    for item in additional_evidence or []:

        if not isinstance(item, dict):
            continue

        tool = item.get("tool")

        if not tool:
            continue

        results[tool] = item.get(
            "data",
            {}
        )

    return results


def _temporal_process_map(
    additional_evidence
):
    """
    Build PID -> temporal profile mapping.
    """

    result = {}

    for item in additional_evidence or []:

        if not isinstance(item, dict):
            continue

        if item.get("tool") != (
            "process_temporal_profile"
        ):
            continue

        for profile in item.get(
            "data",
            []
        ):

            if not isinstance(profile, dict):
                continue

            pid = profile.get(
                "pid"
            )

            if pid is not None:

                result[pid] = profile

    return result


def _deep_process_map(
    additional_evidence
):
    """
    Build PID -> deep investigation mapping.
    """

    result = {}

    for item in additional_evidence or []:

        if not isinstance(item, dict):
            continue

        if item.get("tool") != (
            "process_deep_investigation"
        ):
            continue

        for investigation in item.get(
            "data",
            []
        ):

            if not isinstance(
                investigation,
                dict
            ):
                continue

            pid = investigation.get(
                "pid"
            )

            if pid is not None:

                result[pid] = investigation

    return result


def _get_system_pressure(
    system_info,
    trend_analysis
):
    """
    Estimate broad system pressure.

    This is context, not a root-cause probability.
    """

    cpu = (
        system_info.get(
            "cpu_usage_percent",
            0
        )
        or 0
    )

    ram = (
        system_info.get(
            "ram_usage_percent",
            0
        )
        or 0
    )

    cpu_average = cpu

    ram_average = ram

    if trend_analysis:

        cpu_average = (
            trend_analysis
            .get("cpu", {})
            .get(
                "average",
                cpu
            )
            or cpu
        )

        ram_average = (
            trend_analysis
            .get("ram", {})
            .get(
                "average",
                ram
            )
            or ram
        )

    score = (
        cpu_average
        * 0.55
        +
        ram_average
        * 0.45
    )

    if score >= 80:

        pressure = "HIGH"

    elif score >= 60:

        pressure = "MODERATE"

    else:

        pressure = "LOW"

    return {
        "status": pressure,
        "score": round(
            score,
            2
        ),
        "cpu_average": round(
            cpu_average,
            2
        ),
        "ram_average": round(
            ram_average,
            2
        )
    }


def _build_process_candidates(
    process_info,
    anomalies,
    trend_analysis,
    additional_evidence
):
    """
    Fuse initial process observations with later
    temporal/deep evidence.

    The final score is an evidence-support score,
    NOT the probability of causation.
    """

    temporal_map = _temporal_process_map(
        additional_evidence
    )

    deep_map = _deep_process_map(
        additional_evidence
    )

    anomaly_map = {}

    for anomaly in (
        anomalies.get(
            "anomalies",
            []
        )
        if anomalies
        else []
    ):

        pid = anomaly.get(
            "pid"
        )

        if pid is not None:

            anomaly_map[pid] = anomaly

    candidates = []

    for process in process_info or []:

        pid = process.get(
            "pid"
        )

        name = (
            process.get("name")
            or "Unknown"
        )

        if pid is None:
            continue

        if name.lower() in {
            "system idle process",
            "idle"
        }:
            continue

        score = 0

        evidence = []

        cpu = (
            process.get(
                "cpu_average",
                process.get(
                    "cpu_percent",
                    0
                )
            )
            or 0
        )

        memory = (
            process.get(
                "memory_percent",
                0
            )
            or 0
        )

        # ------------------------------------------------------
        # INITIAL CPU
        # ------------------------------------------------------

        if cpu >= 50:

            score += 35

            evidence.append(
                f"Initial observed CPU activity was "
                f"{cpu}%."
            )

        elif cpu >= 25:

            score += 22

            evidence.append(
                f"Initial observed CPU activity was "
                f"{cpu}%."
            )

        elif cpu >= 15:

            score += 10

            evidence.append(
                f"Initial observed CPU activity was "
                f"{cpu}%."
            )

        # ------------------------------------------------------
        # INITIAL MEMORY
        # ------------------------------------------------------

        if memory >= 15:

            score += 20

            evidence.append(
                f"Initial memory usage was "
                f"{memory}%."
            )

        elif memory >= 8:

            score += 10

            evidence.append(
                f"Initial memory usage was "
                f"{memory}%."
            )

        # ------------------------------------------------------
        # ANOMALY
        # ------------------------------------------------------

        anomaly = anomaly_map.get(
            pid
        )

        if anomaly:

            anomaly_score = (
                anomaly.get(
                    "score",
                    0
                )
                or 0
            )

            if anomaly_score >= 85:

                score += 15

            elif anomaly_score >= 60:

                score += 8

            evidence.append(
                "ORION anomaly detection independently "
                "flagged this process."
            )

        # ------------------------------------------------------
        # TEMPORAL EVIDENCE
        # ------------------------------------------------------

        temporal = temporal_map.get(
            pid
        )

        temporal_status = "NO_TEMPORAL_DATA"

        if temporal:

            persistence = temporal.get(
                "persistence"
            )

            temporal_status = (
                persistence
                or "UNKNOWN"
            )

            if persistence == "PERSISTENT":

                score += 35

                evidence.append(
                    "Temporal profiling found persistent "
                    "resource activity."
                )

            elif persistence == "INTERMITTENT":

                score += 20

                evidence.append(
                    "Temporal profiling found intermittent "
                    "resource activity."
                )

            elif persistence == "SHORT_SPIKE":

                score -= 20

                evidence.append(
                    "Temporal profiling indicates a short-lived "
                    "spike rather than sustained activity."
                )

            elif persistence == "LOW_ACTIVITY":

                score -= 35

                evidence.append(
                    "Temporal profiling found low activity, "
                    "strongly weakening the process hypothesis."
                )

        # ------------------------------------------------------
        # DEEP PROCESS EVIDENCE
        # ------------------------------------------------------

        deep = deep_map.get(
            pid
        )

        deep_status = "NO_DEEP_DATA"

        if deep:

            deep_status = deep.get(
                "status",
                "UNKNOWN"
            )

            deep_cpu = (
                deep.get(
                    "cpu_percent"
                )
            )

            deep_memory = (
                deep.get(
                    "memory_percent"
                )
            )

            if (
                deep_cpu is not None
                and deep_cpu >= 50
            ):

                score += 25

                evidence.append(
                    "Deep process investigation observed "
                    f"CPU activity of {deep_cpu}%."
                )

            elif (
                deep_cpu is not None
                and deep_cpu >= 25
            ):

                score += 15

                evidence.append(
                    "Deep process investigation observed "
                    f"elevated CPU activity of {deep_cpu}%."
                )

            elif (
                deep_cpu is not None
                and deep_cpu < 5
            ):

                score -= 10

                evidence.append(
                    "Deep process investigation found low "
                    "current CPU activity."
                )

            if (
                deep_memory is not None
                and deep_memory >= 15
            ):

                score += 15

                evidence.append(
                    "Deep process investigation found high "
                    "memory usage."
                )

            if (
                "HIGH_THREAD_COUNT"
                in deep.get(
                    "flags",
                    []
                )
            ):

                score += 5

                evidence.append(
                    "The process has a high thread count."
                )

        # ------------------------------------------------------
        # FINAL CLASSIFICATION
        # ------------------------------------------------------

        score = max(
            0,
            min(
                score,
                100
            )
        )

        if temporal_status == "LOW_ACTIVITY":

            classification = "WEAKENED"
            confidence = "LOW"

        elif score >= 70:

            classification = (
                "STRONG_CANDIDATE"
            )

            confidence = "HIGH"

        elif score >= 45:

            classification = (
                "SUPPORTED_CANDIDATE"
            )

            confidence = "MODERATE"

        elif score > 0:

            classification = (
                "POSSIBLE_CANDIDATE"
            )

            confidence = "LOW"

        else:

            classification = (
                "NOT_CONFIRMED"
            )

            confidence = "LOW"

        candidates.append({
            "pid": pid,
            "process": name,
            "evidence_score": score,
            "classification": classification,
            "confidence": confidence,
            "cpu_percent": cpu,
            "memory_percent": memory,
            "temporal_status": temporal_status,
            "deep_status": deep_status,
            "evidence": evidence
        })

    candidates.sort(
        key=lambda item: item[
            "evidence_score"
        ],
        reverse=True
    )

    return candidates


def fuse_investigation_evidence(
    system_info,
    process_info,
    anomalies,
    root_causes,
    trend_analysis,
    additional_evidence=None
):
    """
    Fuse all investigation evidence into one structured
    evidence state for ORION's reasoning layer.

    Evidence categories:

    - system pressure
    - process causality evidence
    - memory pressure
    - storage latency
    """

    additional_evidence = (
        additional_evidence
        or []
    )

    tool_data = _collect_tool_data(
        additional_evidence
    )

    system_pressure = _get_system_pressure(
        system_info,
        trend_analysis
    )

    candidates = _build_process_candidates(
        process_info,
        anomalies,
        trend_analysis,
        additional_evidence
    )

    # ==========================================================
    # MEMORY EVIDENCE
    # ==========================================================

    memory_data = tool_data.get(
        "memory_pressure"
    )

    if not memory_data:

        memory_status = "NOT_TESTED"

    else:

        memory_pressure_status = (
            memory_data.get(
                "pressure_status"
            )
        )

        if memory_pressure_status == "HIGH":

            memory_status = (
                "SUPPORTED_MEMORY_PRESSURE"
            )

        elif memory_pressure_status == "MODERATE":

            memory_status = (
                "POSSIBLE_MEMORY_PRESSURE"
            )

        elif memory_pressure_status == "LOW":

            memory_status = (
                "MEMORY_PRESSURE_NOT_SUPPORTED"
            )

        else:

            memory_status = (
                "NOT_TESTED"
            )

    # ==========================================================
    # STORAGE EVIDENCE
    # ==========================================================

    storage_data = tool_data.get(
        "storage_latency"
    )

    if not storage_data:

        storage_status = "NOT_TESTED"

    else:

        storage_pressure_status = (
            storage_data.get(
                "storage_pressure_status"
            )
        )

        if storage_pressure_status == "HIGH":

            storage_status = (
                "SUPPORTED_STORAGE_LATENCY"
            )

        elif storage_pressure_status == "MODERATE":

            storage_status = (
                "POSSIBLE_STORAGE_LATENCY"
            )

        elif storage_pressure_status == "LOW":

            storage_status = (
                "STORAGE_LATENCY_NOT_SUPPORTED"
            )

        else:

            storage_status = (
                "NOT_TESTED"
            )
    # ==========================================================
    # GPU EVIDENCE
    # ==========================================================

    gpu_data = tool_data.get(
        "gpu_monitor"
    )

    gpu_status = "NOT_TESTED"

    if gpu_data:

        maximum_utilization = (
            gpu_data.get(
                "maximum_engine_utilization_percent"
            )
        )

        average_active_engines = (
            gpu_data.get(
                "average_active_engine_count"
            )
        )

        if (
            maximum_utilization is not None
            and maximum_utilization <= 5
        ):

            gpu_status = (
                "NO_SIGNIFICANT_ACTIVITY_OBSERVED"
            )

        elif (
            maximum_utilization is not None
            and maximum_utilization > 5
        ):

            gpu_status = (
                "GPU_ACTIVITY_OBSERVED"
            )

        elif average_active_engines is not None:

            if average_active_engines <= 0:

                gpu_status = (
                    "NO_SIGNIFICANT_ACTIVITY_OBSERVED"
                )

            else:

                gpu_status = (
                    "GPU_ACTIVITY_OBSERVED"
                )
    

    # ==========================================================
    # SYSTEM CONCLUSION
    # ==========================================================

    strong_candidates = [
        item
        for item in candidates
        if item.get(
            "classification"
        ) == "STRONG_CANDIDATE"
    ]

    supported_candidates = [
        item
        for item in candidates
        if item.get(
            "classification"
        ) == "SUPPORTED_CANDIDATE"
    ]

    if strong_candidates:

        system_conclusion = (
            "STRONG_PROCESS_CANDIDATE"
        )

    elif supported_candidates:

        system_conclusion = (
            "SUPPORTED_PROCESS_CANDIDATE"
        )

    else:

        system_conclusion = (
            "NO_PROCESS_CAUSE_CONFIRMED"
        )

    strongest = (
        candidates[0]
        if candidates
        else None
    )

    return {
        "system_pressure": (
            system_pressure["status"]
        ),
        "system_pressure_score": (
            system_pressure["score"]
        ),
        "system_evidence": {
            "cpu_average": (
                system_pressure[
                    "cpu_average"
                ]
            ),
            "ram_average": (
                system_pressure[
                    "ram_average"
                ]
            )
        },
        "system_conclusion": system_conclusion,
        "candidate_count": len(
            candidates
        ),
        "candidates": candidates,
        "strongest_candidate": strongest,
        "investigated_processes": list(
            _temporal_process_map(
                additional_evidence
            ).keys()
        ),
        "memory_evidence": {
            "status": memory_status,
            "data": memory_data
        },
        "storage_evidence": {
            "status": storage_status,
            "data": storage_data
        },
        "gpu_evidence": {
            "status": gpu_status,
            "data": gpu_data
        }
    }