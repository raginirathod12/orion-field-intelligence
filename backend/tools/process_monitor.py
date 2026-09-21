import time
import psutil


def get_top_processes(
    limit=10,
    duration=10,
    interval=2
):
    """
    Monitor processes over time.

    ORION records multiple CPU/RAM samples for each process
    so it can distinguish persistent load from temporary spikes.

    Returns:
        - top processes
        - CPU/RAM averages
        - CPU maximum
        - number of samples
        - persistence information
        - executable
        - command line
    """

    process_records = {}

    # ========================================================
    # DISCOVER PROCESSES
    # ========================================================

    processes = []

    for process in psutil.process_iter(
        [
            "pid",
            "name",
            "memory_percent",
            "exe",
            "cmdline"
        ]
    ):

        try:

            process.cpu_percent(None)

            processes.append(process)

        except (
            psutil.NoSuchProcess,
            psutil.AccessDenied,
            psutil.ZombieProcess
        ):

            continue


    # ========================================================
    # MONITORING LOOP
    # ========================================================

    start_time = time.time()

    while time.time() - start_time < duration:

        time.sleep(interval)

        for process in processes:

            try:

                info = process.info

                pid = info.get("pid")

                name = info.get("name") or "Unknown"

                # ------------------------------------------------
                # IGNORE SYSTEM IDLE PROCESS
                # ------------------------------------------------

                if name.lower() == "system idle process":
                    continue


                # ------------------------------------------------
                # CPU
                # ------------------------------------------------

                cpu_usage = process.cpu_percent(None)


                # ------------------------------------------------
                # MEMORY
                # ------------------------------------------------

                memory_usage = round(
                    info.get("memory_percent") or 0,
                    2
                )


                # ------------------------------------------------
                # EXECUTABLE
                # ------------------------------------------------

                executable = info.get("exe")


                # ------------------------------------------------
                # COMMAND LINE
                # ------------------------------------------------

                command_line = info.get(
                    "cmdline"
                )

                if isinstance(
                    command_line,
                    list
                ):

                    command_line = " ".join(
                        str(item)
                        for item in command_line
                    )

                elif not command_line:

                    command_line = ""


                # =================================================
                # CREATE PROCESS RECORD
                # =================================================

                if pid not in process_records:

                    process_records[pid] = {

                        "pid": pid,

                        "name": name,

                        "cpu_samples": [],

                        "memory_samples": [],

                        "executable": executable,

                        "command_line": command_line
                    }


                record = process_records[pid]


                # =================================================
                # STORE SAMPLE
                # =================================================

                record["cpu_samples"].append(
                    round(
                        cpu_usage,
                        2
                    )
                )

                record["memory_samples"].append(
                    memory_usage
                )


                # =================================================
                # UPDATE PROCESS METADATA
                # =================================================

                if executable:

                    record["executable"] = executable


                if command_line:

                    record["command_line"] = command_line


            except (
                psutil.NoSuchProcess,
                psutil.AccessDenied,
                psutil.ZombieProcess
            ):

                continue


    # ========================================================
    # BUILD FINAL PROCESS DATA
    # ========================================================

    final_processes = []


    for pid, record in process_records.items():

        cpu_samples = record["cpu_samples"]

        memory_samples = record[
            "memory_samples"
        ]


        if not cpu_samples:

            continue


        # ----------------------------------------------------
        # CPU STATISTICS
        # ----------------------------------------------------

        cpu_average = (
            sum(cpu_samples)
            / len(cpu_samples)
        )

        cpu_maximum = max(
            cpu_samples
        )

        cpu_minimum = min(
            cpu_samples
        )


        # ----------------------------------------------------
        # CPU RANGE
        # ----------------------------------------------------

        cpu_range = (
            cpu_maximum
            - cpu_minimum
        )


        # ----------------------------------------------------
        # PERSISTENCE
        # ----------------------------------------------------

        high_cpu_samples = sum(

            1

            for value in cpu_samples

            if value >= 25
        )


        persistence_ratio = (
            high_cpu_samples
            / len(cpu_samples)
        )


        # ----------------------------------------------------
        # PERSISTENCE CLASSIFICATION
        # ----------------------------------------------------

        if persistence_ratio >= 0.75:

            persistence = "PERSISTENT"

        elif persistence_ratio >= 0.40:

            persistence = "INTERMITTENT"

        else:

            persistence = "SHORT_SPIKE"


        # ----------------------------------------------------
        # MEMORY STATISTICS
        # ----------------------------------------------------

        memory_average = (
            sum(memory_samples)
            / len(memory_samples)
        )

        memory_maximum = max(
            memory_samples
        )


        # ----------------------------------------------------
        # FINAL RECORD
        # ----------------------------------------------------

        final_processes.append({

            "pid":
                pid,

            "name":
                record["name"],

            "cpu_percent":
                round(
                    cpu_average,
                    2
                ),

            "cpu_average":
                round(
                    cpu_average,
                    2
                ),

            "cpu_maximum":
                round(
                    cpu_maximum,
                    2
                ),

            "cpu_minimum":
                round(
                    cpu_minimum,
                    2
                ),

            "cpu_range":
                round(
                    cpu_range,
                    2
                ),

            "cpu_samples":
                cpu_samples,

            "memory_percent":
                round(
                    memory_average,
                    2
                ),

            "memory_maximum":
                round(
                    memory_maximum,
                    2
                ),

            "memory_samples":
                memory_samples,

            "samples":
                len(cpu_samples),

            "high_cpu_samples":
                high_cpu_samples,

            "persistence_ratio":
                round(
                    persistence_ratio,
                    2
                ),

            "persistence":
                persistence,

            "executable":
                record["executable"],

            "command_line":
                record["command_line"]
        })


    # ========================================================
    # SORT
    # ========================================================

    final_processes.sort(

        key=lambda process: (

            process["cpu_average"],

            process["cpu_maximum"],

            process["memory_percent"]

        ),

        reverse=True
    )


    # ========================================================
    # RETURN TOP PROCESSES
    # ========================================================

    return final_processes[:limit]