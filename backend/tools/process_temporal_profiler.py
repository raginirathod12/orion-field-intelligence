import time
import psutil


def profile_process(
    pid,
    duration=10,
    interval=2
):
    """
    Monitor one process over time.

    This is a read-only investigation.

    CPU measurements are reported as process CPU
    activity relative to one logical CPU equivalent.
    """

    if pid is None:

        return {
            "status": "ERROR",
            "message": "No PID was provided."
        }

    try:

        process = psutil.Process(pid)

        try:
            name = process.name()
        except Exception:
            name = "Unknown"

        # Prime CPU measurement.
        try:
            process.cpu_percent(None)

        except (
            psutil.NoSuchProcess,
            psutil.AccessDenied
        ):

            return {
                "status":
                    "PROCESS_UNAVAILABLE",

                "pid":
                    pid
            }

        samples = []

        start_time = time.time()

        while time.time() - start_time < duration:

            time.sleep(interval)

            try:

                cpu_raw = process.cpu_percent(None)

                memory = process.memory_percent()

                cpu_normalized = round(
                    cpu_raw,
                    2
                )

                samples.append({

                    "timestamp":
                        time.time(),

                    "cpu_percent":
                        cpu_normalized,

                    "memory_percent":
                        round(
                            memory,
                            2
                        )
                })

            except (
                psutil.NoSuchProcess,
                psutil.AccessDenied
            ):

                break

        if not samples:

            return {

                "status":
                    "NO_DATA",

                "pid":
                    pid,

                "name":
                    name,

                "message":
                    "No process samples were collected."

            }

        cpu_values = [

            sample["cpu_percent"]

            for sample in samples

        ]

        memory_values = [

            sample["memory_percent"]

            for sample in samples

        ]

        cpu_average = (

            sum(cpu_values)
            /
            len(cpu_values)

        )

        cpu_minimum = min(
            cpu_values
        )

        cpu_maximum = max(
            cpu_values
        )

        cpu_range = (

            cpu_maximum
            -
            cpu_minimum

        )

        high_cpu_samples = sum(

            1

            for value in cpu_values

            if value >= 25

        )

        elevated_cpu_samples = sum(

            1

            for value in cpu_values

            if value >= 15

        )

        persistence_ratio = (

            high_cpu_samples
            /
            len(cpu_values)

        )

        elevated_ratio = (

            elevated_cpu_samples
            /
            len(cpu_values)

        )

        if persistence_ratio >= 0.75:

            persistence = "PERSISTENT"

        elif elevated_ratio >= 0.50:

            persistence = "INTERMITTENT"

        elif cpu_maximum >= 25:

            persistence = "SHORT_SPIKE"

        else:

            persistence = "LOW_ACTIVITY"

        memory_average = (

            sum(memory_values)
            /
            len(memory_values)

        )

        memory_maximum = max(
            memory_values
        )

        actual_duration = (
            time.time()
            - start_time
        )

        return {

            "status":
                "PROFILED",

            "pid":
                pid,

            "name":
                name,

            "samples":
                len(samples),

            "duration_seconds":
                round(
                    actual_duration,
                    2
                ),

            "cpu": {

                "average":
                    round(
                        cpu_average,
                        2
                    ),

                "minimum":
                    round(
                        cpu_minimum,
                        2
                    ),

                "maximum":
                    round(
                        cpu_maximum,
                        2
                    ),

                "range":
                    round(
                        cpu_range,
                        2
                    )

            },

            "memory": {

                "average":
                    round(
                        memory_average,
                        2
                    ),

                "maximum":
                    round(
                        memory_maximum,
                        2
                    )

            },

            "high_cpu_samples":
                high_cpu_samples,

            "elevated_cpu_samples":
                elevated_cpu_samples,

            "persistence_ratio":
                round(
                    persistence_ratio,
                    2
                ),

            "elevated_ratio":
                round(
                    elevated_ratio,
                    2
                ),

            "persistence":
                persistence,

            "samples_data":
                samples

        }

    except psutil.NoSuchProcess:

        return {

            "status":
                "PROCESS_EXITED",

            "pid":
                pid,

            "message":
                "The process exited during investigation."

        }

    except psutil.AccessDenied:

        return {

            "status":
                "ACCESS_DENIED",

            "pid":
                pid,

            "message":
                "Operating system denied access to this process."

        }

    except Exception as error:

        return {

            "status":
                "ERROR",

            "pid":
                pid,

            "message":
                str(error)

        }