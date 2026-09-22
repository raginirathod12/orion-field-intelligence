from tools.performance_monitor import (
    monitor_system,
    analyze_trends
)


print("===== ORION CONTINUOUS MONITOR =====")

snapshots = monitor_system(
    duration=10,
    interval=2
)

analysis = analyze_trends(snapshots)

print("\nSnapshots:")

for snapshot in snapshots:
    print(snapshot)

print("\nTrend Analysis:")
print(analysis)