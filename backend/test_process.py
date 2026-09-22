from tools.process_monitor import get_top_processes


processes = get_top_processes(10)

print("\n===== ORION PROCESS MONITOR =====\n")

for process in processes:
    print(
        f"{process['name']} | "
        f"PID: {process['pid']} | "
        f"RAM: {process['memory_percent']}% | "
        f"CPU: {process['cpu_percent']}%"
    )