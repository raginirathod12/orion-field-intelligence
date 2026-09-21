import subprocess
import re


def inspect_windows_services(target_pids=None):
    """
    Inspect Windows services hosted by specific svchost.exe PIDs.

    If target_pids is provided, ORION only investigates those PIDs.
    This creates a direct relationship:

        svchost PID -> Windows service -> evidence
    """

    services = []

    target_pids = set(target_pids or [])

    try:

        command = [
            "tasklist",
            "/svc"
        ]

        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=10
        )

        if result.returncode != 0:

            return {
                "status": "ERROR",
                "message": result.stderr.strip()
            }

        lines = result.stdout.splitlines()

        for line in lines:

            if "svchost.exe" not in line.lower():
                continue

            match = re.search(
                r"svchost\.exe\s+(\d+)\s+\S+\s+(.+)",
                line,
                re.IGNORECASE
            )

            if not match:
                continue

            pid = int(match.group(1))

            # If specific PIDs were requested,
            # ignore all other svchost processes.
            if target_pids and pid not in target_pids:
                continue

            service_text = match.group(2).strip()

            services.append({

                "process": "svchost.exe",

                "pid": pid,

                "services": service_text

            })


        return {

            "status": "INSPECTED",

            "target_pids": list(target_pids),

            "process_count": len(services),

            "services": services

        }


    except subprocess.TimeoutExpired:

        return {

            "status": "ERROR",

            "message":
                "Windows service inspection timed out."

        }


    except Exception as error:

        return {

            "status": "ERROR",

            "message": str(error)

        }