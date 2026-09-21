import time
import psutil


def monitor_cpu_frequency(
    duration=10,
    interval=2
):
    """
    Monitor CPU frequency over time.

    Frequency information depends on what the operating
    system and hardware expose through psutil.
    """

    snapshots = []

    start_time = time.time()

    while time.time() - start_time < duration:

        frequency = psutil.cpu_freq(
            percpu=False
        )

        if frequency:

            snapshots.append({

                "timestamp":
                    time.time(),

                "current_mhz":
                    round(
                        frequency.current,
                        2
                    ),

                "minimum_mhz":
                    round(
                        frequency.min,
                        2
                    ),

                "maximum_mhz":
                    round(
                        frequency.max,
                        2
                    )
            })

        else:

            snapshots.append({

                "timestamp":
                    time.time(),

                "current_mhz":
                    None,

                "minimum_mhz":
                    None,

                "maximum_mhz":
                    None
            })


        elapsed = (
            time.time()
            - start_time
        )

        if elapsed < duration:

            time.sleep(
                interval
            )

    return snapshots


def analyze_cpu_frequency(
    snapshots
):
    """
    Analyze CPU frequency behavior.
    """

    valid_samples = [

        snapshot

        for snapshot in snapshots

        if snapshot.get(
            "current_mhz"
        ) is not None
    ]


    if not valid_samples:

        return {

            "status":
                "NO_DATA",

            "message":
                "CPU frequency information "
                "is not available."
        }


    current_values = [

        item["current_mhz"]

        for item in valid_samples
    ]


    average_frequency = (

        sum(current_values)
        /
        len(current_values)
    )


    minimum_frequency = min(
        current_values
    )

    maximum_frequency = max(
        current_values
    )


    return {

        "status":
            "ANALYZED",

        "samples":
            len(valid_samples),

        "current_average_mhz":
            round(
                average_frequency,
                2
            ),

        "observed_minimum_mhz":
            round(
                minimum_frequency,
                2
            ),

        "observed_maximum_mhz":
            round(
                maximum_frequency,
                2
            ),

        "frequency_range_mhz":
            round(
                maximum_frequency
                -
                minimum_frequency,
                2
            )
    }