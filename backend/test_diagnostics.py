from tools.system_info import get_system_info
from tools.process_monitor import get_top_processes
from tools.diagnostic_engine import diagnose_system


system_info = get_system_info()
process_info = get_top_processes(10)

diagnosis = diagnose_system(
    system_info,
    process_info
)

print("\n===== ORION DIAGNOSTIC ENGINE =====\n")

print("Overall Status:")
print(diagnosis["overall_status"])

print("\nFindings:\n")

for finding in diagnosis["findings"]:
    print(
        f"[{finding['severity']}] "
        f"{finding['type']}: "
        f"{finding['message']}"
    )