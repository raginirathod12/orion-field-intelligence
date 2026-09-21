import psutil


def get_process_relationship(process):
    """
    Determine the parent process and whether the process
    appears to belong to ORION.
    """

    pid = process.get("pid")

    parent_pid = None
    parent_name = None
    parent_command_line = ""

    is_orion_process = False

    try:

        if pid is not None:

            proc = psutil.Process(pid)

            parent = proc.parent()

            if parent:

                parent_pid = parent.pid

                parent_name = parent.name()

                try:
                    parent_command_line = " ".join(
                        parent.cmdline()
                    )
                except (
                    psutil.NoSuchProcess,
                    psutil.AccessDenied
                ):
                    parent_command_line = ""

            # ----------------------------------------------
            # CHECK PROCESS ITSELF
            # ----------------------------------------------

            executable = (
                process.get("executable") or ""
            ).lower()

            command_line = (
                process.get("command_line") or ""
            ).lower()

            if "orion-field-intelligence" in executable:
                is_orion_process = True

            if "orion-field-intelligence" in command_line:
                is_orion_process = True

            # ----------------------------------------------
            # CHECK PARENT
            # ----------------------------------------------

            if (
                "orion-field-intelligence"
                in parent_command_line.lower()
            ):
                is_orion_process = True

    except (
        psutil.NoSuchProcess,
        psutil.AccessDenied,
        psutil.ZombieProcess
    ):
        pass

    return {
        "parent_pid": parent_pid,
        "parent_name": parent_name,
        "parent_command_line": parent_command_line,
        "is_orion_process": is_orion_process
    }


def calculate_root_causes(
    process_info,
    anomalies,
    trend_analysis
):
    """
    Rank possible root causes using multiple pieces
    of evidence.

    IMPORTANT:

    The returned confidence is an EVIDENCE SCORE.

    It is NOT a guaranteed probability that the process
    caused the problem.
    """

    candidates = []

    anomaly_list = (
        anomalies.get("anomalies", [])
        if anomalies
        else []
    )


    # ========================================================
    # PROCESS ANALYSIS
    # ========================================================

    for process in process_info or []:

        name = process.get(
            "name",
            "Unknown"
        )

        pid = process.get("pid")

        cpu = process.get(
            "cpu_percent",
            0
        )

        memory = process.get(
            "memory_percent",
            0
        )


        # ----------------------------------------------------
        # PROCESS RELATIONSHIP
        # ----------------------------------------------------

        relationship = get_process_relationship(
            process
        )

        parent_pid = relationship[
            "parent_pid"
        ]

        parent_name = relationship[
            "parent_name"
        ]

        parent_command_line = relationship[
            "parent_command_line"
        ]

        is_orion_process = relationship[
            "is_orion_process"
        ]


        # ----------------------------------------------------
        # IGNORE SYSTEM IDLE
        # ----------------------------------------------------

        normalized_name = name.lower()

        if normalized_name in {
            "system idle process",
            "idle"
        }:

            continue


        # ----------------------------------------------------
        # INITIAL SCORE
        # ----------------------------------------------------

        score = 0

        evidence = []


        # ====================================================
        # CPU EVIDENCE
        # ====================================================

        if cpu >= 50:

            score += 45

            evidence.append(
                f"Very high observed CPU activity: {cpu}%"
            )

        elif cpu >= 40:

            score += 35

            evidence.append(
                f"High observed CPU activity: {cpu}%"
            )

        elif cpu >= 25:

            score += 25

            evidence.append(
                f"Elevated observed CPU activity: {cpu}%"
            )

        elif cpu >= 15:

            score += 10

            evidence.append(
                f"Moderate observed CPU activity: {cpu}%"
            )


        # ====================================================
        # MEMORY EVIDENCE
        # ====================================================

        if memory >= 15:

            score += 25

            evidence.append(
                f"High memory usage: {memory}%"
            )

        elif memory >= 10:

            score += 18

            evidence.append(
                f"Elevated memory usage: {memory}%"
            )

        elif memory >= 5:

            score += 8

            evidence.append(
                f"Moderate memory usage: {memory}%"
            )


        # ====================================================
        # ANOMALY CORRELATION
        # ====================================================

        anomaly_match = False

        for anomaly in anomaly_list:

            if anomaly.get("pid") == pid:

                anomaly_match = True

                anomaly_score = anomaly.get(
                    "score",
                    0
                )

                if anomaly_score >= 85:

                    score += 15

                elif anomaly_score >= 60:

                    score += 8

                evidence.append(
                    "Independently flagged by "
                    "ORION anomaly detection."
                )

                break


        # ====================================================
        # SYSTEM TREND CORRELATION
        # ====================================================

        if trend_analysis:

            cpu_data = trend_analysis.get(
                "cpu",
                {}
            )

            cpu_average = cpu_data.get(
                "average",
                0
            )

            cpu_maximum = cpu_data.get(
                "maximum",
                0
            )


            if cpu_average >= 65:

                score += 10

                evidence.append(
                    "System CPU remained elevated "
                    "during monitoring."
                )

            elif cpu_maximum >= 75:

                score += 5

                evidence.append(
                    "System CPU reached a significant "
                    "peak during monitoring."
                )


        # ====================================================
        # ORION PROCESS DETECTION
        # ====================================================

        if is_orion_process:

            # Do NOT completely remove it.

            # Instead, reduce its root-cause score
            # because ORION should understand that its
            # own workload may be contributing to the
            # measurements.

            score = max(
                0,
                score - 25
            )

            evidence.append(
                "Process appears to belong to ORION's "
                "own execution tree; reduced root-cause "
                "priority."
            )


        # ====================================================
        # PARENT PROCESS INFORMATION
        # ====================================================

        if parent_pid is not None:

            evidence.append(
                f"Parent process: "
                f"{parent_name} "
                f"(PID {parent_pid})."
            )


        # ====================================================
        # PYTHON MULTIPROCESSING DETECTION
        # ====================================================

        command_line = (
            process.get("command_line")
            or ""
        ).lower()


        if (
            "multiprocessing.spawn"
            in command_line
        ):

            evidence.append(
                "This process is a Python "
                "multiprocessing child process."
            )


        # ====================================================
        # ONLY KEEP REAL CANDIDATES
        # ====================================================

        if score > 0:

            candidates.append({

                "pid": pid,

                "process": name,

                "evidence_score": min(
                    score,
                    100
                ),

                "cpu_percent": cpu,

                "memory_percent": memory,

                "parent_pid": parent_pid,

                "parent_process": parent_name,

                "is_orion_process":
                    is_orion_process,

                "evidence": evidence
            })


    # ========================================================
    # SORT
    # ========================================================

    candidates.sort(
        key=lambda item:
            item["evidence_score"],
        reverse=True
    )


    # ========================================================
    # RETURN
    # ========================================================

    return candidates