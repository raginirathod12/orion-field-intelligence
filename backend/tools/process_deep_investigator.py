import psutil


def investigate_process(pid):
    """
    Perform a deeper investigation of one process.

    ORION collects process metadata, resource usage,
    process relationships, threads and network information
    where the operating system allows access.

    This function does NOT modify or terminate the process.
    It is read-only investigation.
    """

    if pid is None:
        return {
            "status": "ERROR",
            "message": "No PID was provided."
        }

    try:

        process = psutil.Process(pid)

        # ====================================================
        # BASIC PROCESS INFORMATION
        # ====================================================

        try:
            name = process.name()
        except Exception:
            name = "Unknown"

        try:
            status = process.status()
        except Exception:
            status = "Unknown"

        try:
            executable = process.exe()
        except (
            psutil.AccessDenied,
            psutil.NoSuchProcess
        ):
            executable = None

        try:
            command_line = process.cmdline()

            if isinstance(command_line, list):
                command_line = " ".join(
                    str(item)
                    for item in command_line
                )

        except (
            psutil.AccessDenied,
            psutil.NoSuchProcess
        ):
            command_line = ""

        # ====================================================
        # PROCESS CREATION TIME
        # ====================================================

        try:
            create_time = process.create_time()
        except Exception:
            create_time = None

        # ====================================================
        # PARENT PROCESS
        # ====================================================

        parent_pid = None
        parent_name = None

        try:

            parent = process.parent()

            if parent:

                parent_pid = parent.pid

                try:
                    parent_name = parent.name()
                except Exception:
                    parent_name = "Unknown"

        except (
            psutil.NoSuchProcess,
            psutil.AccessDenied
        ):
            pass

        # ====================================================
        # CHILD PROCESSES
        # ====================================================

        children = []

        try:

            child_processes = process.children(
                recursive=False
            )

            for child in child_processes:

                try:

                    children.append({

                        "pid":
                            child.pid,

                        "name":
                            child.name(),

                        "status":
                            child.status()

                    })

                except (
                    psutil.NoSuchProcess,
                    psutil.AccessDenied
                ):
                    continue

        except (
            psutil.NoSuchProcess,
            psutil.AccessDenied
        ):
            pass

        # ====================================================
        # CPU INFORMATION
        # ====================================================

        try:
            cpu_percent = process.cpu_percent(
                interval=1
            )
        except (
            psutil.NoSuchProcess,
            psutil.AccessDenied
        ):
            cpu_percent = None

        # ====================================================
        # MEMORY INFORMATION
        # ====================================================

        memory_percent = None
        memory_rss_mb = None
        memory_vms_mb = None

        try:

            memory = process.memory_info()

            memory_rss_mb = round(
                memory.rss / (1024 ** 2),
                2
            )

            memory_vms_mb = round(
                memory.vms / (1024 ** 2),
                2
            )

            memory_percent = round(
                process.memory_percent(),
                2
            )

        except (
            psutil.NoSuchProcess,
            psutil.AccessDenied
        ):
            pass

        # ====================================================
        # THREAD INFORMATION
        # ====================================================

        thread_count = None

        try:

            thread_count = process.num_threads()

        except (
            psutil.NoSuchProcess,
            psutil.AccessDenied
        ):
            pass

        # ====================================================
        # CONTEXT SWITCHES
        # ====================================================

        voluntary_context_switches = None
        involuntary_context_switches = None

        try:

            context = process.num_ctx_switches()

            voluntary_context_switches = (
                context.voluntary
            )

            involuntary_context_switches = (
                context.involuntary
            )

        except (
            psutil.NoSuchProcess,
            psutil.AccessDenied
        ):
            pass

        # ====================================================
        # OPEN FILES
        # ====================================================

        open_file_count = None

        try:

            open_files = process.open_files()

            open_file_count = len(
                open_files
            )

        except (
            psutil.NoSuchProcess,
            psutil.AccessDenied
        ):
            pass

        # ====================================================
        # NETWORK CONNECTIONS
        # ====================================================

        network_connection_count = None

        try:

            connections = process.net_connections()

            network_connection_count = len(
                connections
            )

        except (
            psutil.NoSuchProcess,
            psutil.AccessDenied
        ):
            pass

        # ====================================================
        # PROCESS STATUS ANALYSIS
        # ====================================================

        flags = []

        if cpu_percent is not None:

            if cpu_percent >= 50:

                flags.append(
                    "VERY_HIGH_CPU"
                )

            elif cpu_percent >= 25:

                flags.append(
                    "HIGH_CPU"
                )

            elif cpu_percent >= 15:

                flags.append(
                    "ELEVATED_CPU"
                )

        if memory_percent is not None:

            if memory_percent >= 15:

                flags.append(
                    "HIGH_MEMORY"
                )

            elif memory_percent >= 8:

                flags.append(
                    "ELEVATED_MEMORY"
                )

        if thread_count is not None:

            if thread_count >= 100:

                flags.append(
                    "HIGH_THREAD_COUNT"
                )

        # ====================================================
        # FINAL RESULT
        # ====================================================

        return {

            "status":
                "INVESTIGATED",

            "pid":
                pid,

            "name":
                name,

            "process_status":
                status,

            "executable":
                executable,

            "command_line":
                command_line,

            "create_time":
                create_time,

            "parent_pid":
                parent_pid,

            "parent_process":
                parent_name,

            "children":
                children,

            "child_count":
                len(children),

            "cpu_percent":
                cpu_percent,

            "memory_percent":
                memory_percent,

            "memory_rss_mb":
                memory_rss_mb,

            "memory_vms_mb":
                memory_vms_mb,

            "thread_count":
                thread_count,

            "voluntary_context_switches":
                voluntary_context_switches,

            "involuntary_context_switches":
                involuntary_context_switches,

            "open_file_count":
                open_file_count,

            "network_connection_count":
                network_connection_count,

            "flags":
                flags
        }


    except psutil.NoSuchProcess:

        return {

            "status":
                "PROCESS_EXITED",

            "pid":
                pid,

            "message":
                "The process no longer exists."

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