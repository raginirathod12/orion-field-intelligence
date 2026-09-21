def diagnose_system(
    system_info,
    process_info,
    trend_analysis=None
):
    """
    ORION deterministic diagnostic engine.

    Analyzes:
    - System CPU
    - RAM
    - Disk
    - Individual processes
    - Performance trends

    Produces evidence that the AI reasoning layer
    can interpret.
    """

    findings = []
    severity = "NORMAL"

    cpu_usage = system_info.get(
        "cpu_usage_percent",
        0
    )

    ram_usage = system_info.get(
        "ram_usage_percent",
        0
    )

    disk_free = system_info.get(
        "disk_free_gb",
        0
    )

    # ==================================================
    # CPU
    # ==================================================

    if cpu_usage >= 90:

        findings.append({
            "type": "CPU",
            "severity": "CRITICAL",
            "message": (
                f"Overall CPU usage is critically high "
                f"at {cpu_usage}%."
            )
        })

        severity = "CRITICAL"

    elif cpu_usage >= 75:

        findings.append({
            "type": "CPU",
            "severity": "WARNING",
            "message": (
                f"Overall CPU usage is elevated "
                f"at {cpu_usage}%."
            )
        })

        if severity == "NORMAL":
            severity = "WARNING"

    elif cpu_usage >= 60:

        findings.append({
            "type": "CPU",
            "severity": "ELEVATED",
            "message": (
                f"Overall CPU usage is moderately elevated "
                f"at {cpu_usage}%."
            )
        })

        if severity == "NORMAL":
            severity = "WARNING"

    else:

        findings.append({
            "type": "CPU",
            "severity": "NORMAL",
            "message": (
                f"Overall CPU usage is {cpu_usage}%, "
                "with no significant system-wide pressure."
            )
        })

    # ==================================================
    # RAM
    # ==================================================

    if ram_usage >= 90:

        findings.append({
            "type": "RAM",
            "severity": "CRITICAL",
            "message": (
                f"RAM usage is critically high "
                f"at {ram_usage}%."
            )
        })

        severity = "CRITICAL"

    elif ram_usage >= 80:

        findings.append({
            "type": "RAM",
            "severity": "WARNING",
            "message": (
                f"RAM usage is elevated "
                f"at {ram_usage}%."
            )
        })

        if severity == "NORMAL":
            severity = "WARNING"

    elif ram_usage >= 70:

        findings.append({
            "type": "RAM",
            "severity": "ELEVATED",
            "message": (
                f"RAM usage is moderately elevated "
                f"at {ram_usage}%."
            )
        })

        if severity == "NORMAL":
            severity = "WARNING"

    else:

        findings.append({
            "type": "RAM",
            "severity": "NORMAL",
            "message": (
                f"RAM usage is {ram_usage}%, "
                "with no significant memory pressure."
            )
        })

    # ==================================================
    # DISK
    # ==================================================

    if disk_free < 10:

        findings.append({
            "type": "DISK",
            "severity": "CRITICAL",
            "message": (
                f"Only {disk_free} GB of disk space remains."
            )
        })

        severity = "CRITICAL"

    elif disk_free < 25:

        findings.append({
            "type": "DISK",
            "severity": "WARNING",
            "message": (
                f"Disk space is getting low: "
                f"{disk_free} GB remaining."
            )
        })

        if severity == "NORMAL":
            severity = "WARNING"

    else:

        findings.append({
            "type": "DISK",
            "severity": "NORMAL",
            "message": (
                f"Disk space is healthy with "
                f"{disk_free} GB available."
            )
        })

    # ==================================================
    # PROCESS ANALYSIS
    # ==================================================

    heavy_processes = []

    ignored_processes = {
        "system idle process",
        "idle"
    }

    for process in process_info or []:

        name = process.get(
            "name",
            "Unknown"
        )

        cpu = process.get(
            "cpu_percent",
            0
        )

        memory = process.get(
            "memory_percent",
            0
        )

        normalized_name = name.lower()

        # Never treat idle accounting as a culprit
        if normalized_name in ignored_processes:
            continue

        # ----------------------------------------------
        # RESOURCE THRESHOLDS
        # ----------------------------------------------

        if cpu >= 15 or memory >= 8:

            heavy_processes.append({
                "pid": process.get("pid"),
                "name": name,
                "cpu_percent": cpu,
                "memory_percent": memory,
                "executable": process.get(
                    "executable"
                ),
                "command_line": process.get(
                    "command_line"
                )
            })

    # --------------------------------------------------
    # SORT HEAVY PROCESSES
    # --------------------------------------------------

    heavy_processes.sort(
        key=lambda process: (
            process["cpu_percent"],
            process["memory_percent"]
        ),
        reverse=True
    )

    # --------------------------------------------------
    # PROCESS FINDING
    # --------------------------------------------------

    if heavy_processes:

        top_process = heavy_processes[0]

        findings.append({
            "type": "PROCESS",
            "severity": "WARNING",
            "message": (
                f"High resource consumption detected "
                f"from {top_process['name']} "
                f"(PID {top_process['pid']}) "
                f"using {top_process['cpu_percent']}% CPU."
            ),
            "processes": heavy_processes
        })

        if severity == "NORMAL":
            severity = "WARNING"

    else:

        findings.append({
            "type": "PROCESS",
            "severity": "NORMAL",
            "message": (
                "No sampled process is currently "
                "showing excessive resource usage."
            )
        })

    # ==================================================
    # PERFORMANCE TRENDS
    # ==================================================

    if trend_analysis:

        # --------------------------------------------------
        # CPU TREND
        # --------------------------------------------------

        cpu_data = trend_analysis.get(
            "cpu",
            {}
        )

        cpu_min = cpu_data.get(
            "minimum",
            0
        )

        cpu_max = cpu_data.get(
            "maximum",
            0
        )

        cpu_average = cpu_data.get(
            "average",
            0
        )

        cpu_range = cpu_max - cpu_min

        if cpu_average >= 80:

            findings.append({
                "type": "CPU_TREND",
                "severity": "CRITICAL",
                "message": (
                    f"CPU remained heavily loaded. "
                    f"Average usage was {cpu_average}%."
                )
            })

            severity = "CRITICAL"

        elif cpu_average >= 65:

            findings.append({
                "type": "CPU_TREND",
                "severity": "WARNING",
                "message": (
                    f"CPU showed sustained elevated "
                    f"activity. Average usage was "
                    f"{cpu_average}%."
                )
            })

            if severity == "NORMAL":
                severity = "WARNING"

        elif cpu_range >= 30:

            findings.append({
                "type": "CPU_SPIKE",
                "severity": "WARNING",
                "message": (
                    f"CPU usage fluctuated significantly "
                    f"from {cpu_min}% to {cpu_max}%."
                )
            })

            if severity == "NORMAL":
                severity = "WARNING"

        else:

            findings.append({
                "type": "CPU_TREND",
                "severity": "NORMAL",
                "message": (
                    f"CPU remained relatively stable. "
                    f"Average: {cpu_average}%, "
                    f"range: {cpu_min}%–{cpu_max}%."
                )
            })

        # --------------------------------------------------
        # RAM TREND
        # --------------------------------------------------

        ram_data = trend_analysis.get(
            "ram",
            {}
        )

        ram_min = ram_data.get(
            "minimum",
            0
        )

        ram_max = ram_data.get(
            "maximum",
            0
        )

        ram_average = ram_data.get(
            "average",
            0
        )

        ram_range = ram_max - ram_min

        if ram_average >= 90:

            findings.append({
                "type": "RAM_TREND",
                "severity": "CRITICAL",
                "message": (
                    f"RAM remained critically high. "
                    f"Average usage was {ram_average}%."
                )
            })

            severity = "CRITICAL"

        elif ram_average >= 80:

            findings.append({
                "type": "RAM_TREND",
                "severity": "WARNING",
                "message": (
                    f"RAM remained elevated. "
                    f"Average usage was {ram_average}%."
                )
            })

            if severity == "NORMAL":
                severity = "WARNING"

        elif ram_range >= 10:

            findings.append({
                "type": "RAM_SPIKE",
                "severity": "WARNING",
                "message": (
                    f"RAM usage changed significantly "
                    f"from {ram_min}% to {ram_max}%."
                )
            })

            if severity == "NORMAL":
                severity = "WARNING"

        else:

            findings.append({
                "type": "RAM_TREND",
                "severity": "NORMAL",
                "message": (
                    f"RAM remained stable. "
                    f"Average: {ram_average}%."
                )
            })

    # ==================================================
    # FINAL RESULT
    # ==================================================

    return {
        "overall_status": severity,
        "findings": findings,
        "heavy_processes": heavy_processes
    }