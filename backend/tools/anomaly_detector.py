def detect_anomalies(
    system_info,
    process_info,
    trend_analysis,
    disk_analysis=None
):
    """
    Detect unusual system behavior from
    multiple evidence sources.
    """

    anomalies = []

    # ==================================================
    # CPU ANOMALY
    # ==================================================

    cpu = system_info.get(
        "cpu_usage_percent",
        0
    )

    if cpu >= 90:

        anomalies.append({
            "type": "CPU",
            "severity": "CRITICAL",
            "score": 95,
            "message": (
                "System CPU utilization is critically high."
            )
        })

    elif cpu >= 75:

        anomalies.append({
            "type": "CPU",
            "severity": "HIGH",
            "score": 80,
            "message": (
                "System CPU utilization is unusually high."
            )
        })

    # ==================================================
    # CPU TREND ANOMALY
    # ==================================================

    if trend_analysis:

        cpu_data = trend_analysis.get(
            "cpu",
            {}
        )

        cpu_range = (
            cpu_data.get("maximum", 0)
            -
            cpu_data.get("minimum", 0)
        )

        if cpu_range >= 40:

            anomalies.append({
                "type": "CPU_SPIKE",
                "severity": "HIGH",
                "score": 75,
                "message": (
                    f"CPU fluctuated by approximately "
                    f"{round(cpu_range, 2)} percentage points."
                )
            })

    # ==================================================
    # RAM ANOMALY
    # ==================================================

    ram = system_info.get(
        "ram_usage_percent",
        0
    )

    if ram >= 90:

        anomalies.append({
            "type": "RAM",
            "severity": "CRITICAL",
            "score": 95,
            "message": (
                "RAM utilization is critically high."
            )
        })

    elif ram >= 80:

        anomalies.append({
            "type": "RAM",
            "severity": "HIGH",
            "score": 80,
            "message": (
                "RAM utilization is unusually high."
            )
        })

    # ==================================================
    # PROCESS ANOMALIES
    # ==================================================

    for process in process_info or []:

        name = process.get(
            "name",
            "Unknown"
        )

        cpu_usage = process.get(
            "cpu_percent",
            0
        )

        memory_usage = process.get(
            "memory_percent",
            0
        )

        if cpu_usage >= 40:

            anomalies.append({
                "type": "PROCESS_CPU",
                "severity": "HIGH",
                "score": 85,
                "pid": process.get("pid"),
                "process": name,
                "message": (
                    f"{name} is showing unusually high "
                    f"CPU activity at {cpu_usage}%."
                )
            })

        elif cpu_usage >= 25:

            anomalies.append({
                "type": "PROCESS_CPU",
                "severity": "MEDIUM",
                "score": 60,
                "pid": process.get("pid"),
                "process": name,
                "message": (
                    f"{name} is showing elevated "
                    f"CPU activity at {cpu_usage}%."
                )
            })

        if memory_usage >= 10:

            anomalies.append({
                "type": "PROCESS_MEMORY",
                "severity": "HIGH",
                "score": 80,
                "pid": process.get("pid"),
                "process": name,
                "message": (
                    f"{name} is consuming significant "
                    f"memory at {memory_usage}%."
                )
            })

    # ==================================================
    # DISK I/O ANOMALY
    # ==================================================

    if disk_analysis:

        read_avg = disk_analysis.get(
            "read",
            {}
        ).get(
            "average",
            0
        )

        write_avg = disk_analysis.get(
            "write",
            {}
        ).get(
            "average",
            0
        )

        if read_avg >= 100:

            anomalies.append({
                "type": "DISK_READ",
                "severity": "HIGH",
                "score": 75,
                "message": (
                    f"Disk read activity averaged "
                    f"{read_avg} MB/s."
                )
            })

        if write_avg >= 100:

            anomalies.append({
                "type": "DISK_WRITE",
                "severity": "HIGH",
                "score": 75,
                "message": (
                    f"Disk write activity averaged "
                    f"{write_avg} MB/s."
                )
            })

    # ==================================================
    # SORT
    # ==================================================

    anomalies.sort(
        key=lambda item: item.get(
            "score",
            0
        ),
        reverse=True
    )

    return {
        "status": (
            "ANOMALIES_DETECTED"
            if anomalies
            else "NORMAL"
        ),
        "count": len(anomalies),
        "anomalies": anomalies
    }