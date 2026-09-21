def _completed_tool_set(
    completed_tools=None,
    additional_evidence=None
):
    """
    Build a reliable set of tools that have already run.

    ORION checks both:
    - explicit completed_tools
    - recorded additional_evidence
    """

    completed = set(
        completed_tools or []
    )

    for item in additional_evidence or []:

        if not isinstance(item, dict):
            continue

        tool_name = item.get("tool")

        if tool_name:
            completed.add(tool_name)

    return completed


def _profiled_pids(
    additional_evidence=None
):
    """
    Return PIDs that already received temporal profiling.
    """

    pids = set()

    for item in additional_evidence or []:

        if not isinstance(item, dict):
            continue

        if item.get("tool") != "process_temporal_profile":
            continue

        for pid in item.get(
            "target_pids",
            []
        ):

            try:
                pids.add(int(pid))
            except (
                TypeError,
                ValueError
            ):
                continue

    return pids


def _deep_investigated_pids(
    additional_evidence=None
):
    """
    Return PIDs that already received deep investigation.
    """

    pids = set()

    for item in additional_evidence or []:

        if not isinstance(item, dict):
            continue

        if item.get("tool") != "process_deep_investigation":
            continue

        for pid in item.get(
            "target_pids",
            []
        ):

            try:
                pids.add(int(pid))
            except (
                TypeError,
                ValueError
            ):
                continue

    return pids


def _service_inspected_pids(
    additional_evidence=None
):
    """
    Return svchost PIDs that already had service inspection.
    """

    pids = set()

    for item in additional_evidence or []:

        if not isinstance(item, dict):
            continue

        if item.get("tool") != "windows_services":
            continue

        for pid in item.get(
            "target_pids",
            []
        ):

            try:
                pids.add(int(pid))
            except (
                TypeError,
                ValueError
            ):
                continue

    return pids


def _candidate_pids(
    process_info,
    root_causes
):
    """
    Select useful candidate process PIDs.

    ORION does NOT simply choose every process.

    Candidates are ranked using existing root-cause evidence
    and process resource activity.
    """

    candidates = []

    for candidate in root_causes or []:

        pid = candidate.get("pid")

        if pid is None:
            continue

        score = candidate.get(
            "evidence_score",
            0
        )

        candidates.append(
            (
                score,
                pid
            )
        )

    if candidates:

        candidates.sort(
            key=lambda item: item[0],
            reverse=True
        )

        return [
            pid
            for _, pid in candidates
        ]

    # Fallback if root-cause ranking has no candidates.
    fallback = []

    for process in process_info or []:

        pid = process.get("pid")

        if pid is None:
            continue

        cpu = process.get(
            "cpu_average",
            process.get(
                "cpu_percent",
                0
            )
        )

        memory = process.get(
            "memory_percent",
            0
        )

        if cpu >= 15 or memory >= 8:

            fallback.append(
                (
                    max(cpu, memory),
                    pid
                )
            )

    fallback.sort(
        key=lambda item: item[0],
        reverse=True
    )

    return [
        pid
        for _, pid in fallback
    ]


def create_investigation_plan(
    system_info,
    process_info,
    anomalies,
    root_causes,
    completed_tools=None,
    additional_evidence=None
):
    """
    Autonomous ORION investigation planner.

    Investigation strategy:

        1. Temporal process profiling
        2. Deep process investigation when justified
        3. Windows service inspection when justified
        4. Per-core CPU
        5. GPU
        6. Memory pressure
        7. Storage latency
        8. CPU frequency / temperature when justified
        9. Stop

    The planner is authoritative for tool selection.

    It does NOT ask the LLM to blindly choose every tool.
    """

    completed_set = _completed_tool_set(
        completed_tools,
        additional_evidence
    )

    profiled_pids = _profiled_pids(
        additional_evidence
    )

    deep_pids = _deep_investigated_pids(
        additional_evidence
    )

    service_pids = _service_inspected_pids(
        additional_evidence
    )

    candidate_pids = _candidate_pids(
        process_info,
        root_causes
    )

    # ==========================================================
    # ROUND 1+
    # TEMPORAL PROCESS PROFILING
    # ==========================================================

    if (
        "process_temporal_profile"
        not in completed_set
    ):

        targets = [
            pid
            for pid in candidate_pids
            if pid not in profiled_pids
        ][:2]

        if targets:

            return {
                "next_tool": (
                    "process_temporal_profile"
                ),
                "target_pids": targets,
                "reason": (
                    "ORION identified suspicious process "
                    "candidates. Temporal profiling will test "
                    "whether the activity persists across "
                    "multiple samples instead of treating a "
                    "single snapshot as proof."
                )
            }

    # ==========================================================
    # DEEP PROCESS INVESTIGATION
    # ==========================================================

    if (
        "process_deep_investigation"
        not in completed_set
    ):

        persistent_targets = []

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

                pid = profile.get("pid")

                persistence = profile.get(
                    "persistence"
                )

                if (
                    pid is not None
                    and persistence in {
                        "PERSISTENT",
                        "INTERMITTENT"
                    }
                    and pid not in deep_pids
                ):

                    persistent_targets.append(
                        pid
                    )

        if persistent_targets:

            return {
                "next_tool": (
                    "process_deep_investigation"
                ),
                "target_pids": (
                    persistent_targets[:2]
                ),
                "reason": (
                    "Temporal profiling found activity that "
                    "remained persistent or intermittent. "
                    "ORION will inspect the process in more "
                    "detail before treating it as a serious "
                    "candidate."
                )
            }

    # ==========================================================
    # WINDOWS SERVICES
    # ==========================================================

    if (
        "windows_services"
        not in completed_set
    ):

        service_targets = []

        for process in process_info or []:

            name = (
                process.get("name")
                or ""
            ).lower()

            pid = process.get(
                "pid"
            )

            if (
                "svchost.exe" in name
                and pid is not None
                and pid not in service_pids
            ):

                service_targets.append(
                    pid
                )

        if service_targets:

            return {
                "next_tool": (
                    "windows_services"
                ),
                "target_pids": (
                    service_targets[:2]
                ),
                "reason": (
                    "A Windows service-host process is a "
                    "candidate. ORION will map the specific "
                    "svchost PID to hosted Windows services "
                    "before assigning causality."
                )
            }

    # ==========================================================
    # PER-CORE CPU
    # ==========================================================

    if (
        "per_core_cpu"
        not in completed_set
    ):

        return {
            "next_tool": "per_core_cpu",
            "target_pids": [],
            "reason": (
                "Process-level evidence is insufficient to "
                "establish a sustained process cause. ORION "
                "will collect independent per-core CPU evidence "
                "to determine whether system-wide load is "
                "balanced or concentrated."
            )
        }

    # ==========================================================
    # GPU
    # ==========================================================

    if (
        "gpu_monitor"
        not in completed_set
    ):

        return {
            "next_tool": "gpu_monitor",
            "target_pids": [],
            "reason": (
                "CPU and process evidence did not establish "
                "a clear bottleneck. ORION will investigate "
                "GPU utilization and available GPU telemetry."
            )
        }

    # ==========================================================
    # MEMORY PRESSURE
    # ==========================================================

    if (
        "memory_pressure"
        not in completed_set
    ):

        return {
            "next_tool": (
                "memory_pressure"
            ),
            "target_pids": [],
            "reason": (
                "CPU, process and GPU evidence did not "
                "establish a clear bottleneck. ORION will "
                "measure actual memory pressure, committed "
                "memory and paging activity because RAM "
                "percentage alone does not establish memory "
                "health."
            )
        }

    # ==========================================================
    # STORAGE LATENCY
    # ==========================================================

    if (
        "storage_latency"
        not in completed_set
    ):

        return {
            "next_tool": (
                "storage_latency"
            ),
            "target_pids": [],
            "reason": (
                "Memory pressure did not sufficiently explain "
                "the performance complaint. ORION will now "
                "measure storage latency, disk queue depth and "
                "I/O behavior."
            )
        }

    # ==========================================================
    # CPU FREQUENCY
    # ==========================================================

    cpu_usage = (
        system_info.get(
            "cpu_usage_percent",
            0
        )
        or 0
    )

    if (
        "cpu_frequency"
        not in completed_set
        and cpu_usage >= 60
    ):

        return {
            "next_tool": "cpu_frequency",
            "target_pids": [],
            "reason": (
                "System CPU utilization is elevated. ORION "
                "will inspect CPU frequency behavior for "
                "additional performance evidence."
            )
        }

    # ==========================================================
    # TEMPERATURE
    # ==========================================================

    if (
        "temperature"
        not in completed_set
        and cpu_usage >= 60
    ):

        return {
            "next_tool": "temperature",
            "target_pids": [],
            "reason": (
                "System CPU utilization remains elevated. "
                "ORION will check whether operating-system-"
                "exposed temperature sensors provide "
                "additional evidence."
            )
        }

    # ==========================================================
    # NOTHING ELSE
    # ==========================================================

    return {
        "next_tool": None,
        "target_pids": [],
        "reason": (
            "ORION completed the currently implemented "
            "high-value investigation paths. Additional "
            "evidence is insufficient to justify another "
            "investigation tool."
        )
    }