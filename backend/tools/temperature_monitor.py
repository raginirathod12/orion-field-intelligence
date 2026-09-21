import time
import psutil


def read_temperatures():

    """
    Attempt to read available hardware temperatures.

    Windows hardware support through psutil can be limited,
    so an empty result is a valid outcome.
    """

    temperatures = []

    try:

        sensor_data = (
            psutil.sensors_temperatures()
        )

    except AttributeError:

        return temperatures

    except Exception:

        return temperatures


    if not sensor_data:

        return temperatures


    for sensor_name, entries in sensor_data.items():

        for entry in entries:

            temperature = getattr(
                entry,
                "current",
                None
            )

            if temperature is None:
                continue

            temperatures.append({

                "sensor":
                    sensor_name,

                "label":
                    entry.label,

                "temperature_c":
                    round(
                        temperature,
                        2
                    )
            })


    return temperatures


def monitor_temperature(
    duration=10,
    interval=2
):
    """
    Monitor available temperature sensors.
    """

    snapshots = []

    start_time = time.time()

    while time.time() - start_time < duration:

        readings = read_temperatures()

        snapshots.append({

            "timestamp":
                time.time(),

            "readings":
                readings
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


def analyze_temperature(
    snapshots
):
    """
    Analyze temperature measurements.
    """

    all_readings = []


    for snapshot in snapshots:

        for reading in snapshot.get(
            "readings",
            []
        ):

            all_readings.append(
                reading
            )


    if not all_readings:

        return {

            "status":
                "NO_DATA",

            "message":
                "No temperature sensors "
                "were exposed by the operating "
                "system."
        }


    sensor_groups = {}


    for reading in all_readings:

        sensor = reading[
            "sensor"
        ]

        temperature = reading[
            "temperature_c"
        ]

        if sensor not in sensor_groups:

            sensor_groups[sensor] = []

        sensor_groups[sensor].append(
            temperature
        )


    sensors = []


    for sensor, values in sensor_groups.items():

        sensors.append({

            "sensor":
                sensor,

            "minimum_c":
                round(
                    min(values),
                    2
                ),

            "maximum_c":
                round(
                    max(values),
                    2
                ),

            "average_c":
                round(
                    sum(values)
                    /
                    len(values),
                    2
                )
        })


    return {

        "status":
            "ANALYZED",

        "sensors":
            sensors,

        "samples":
            len(all_readings)
    }