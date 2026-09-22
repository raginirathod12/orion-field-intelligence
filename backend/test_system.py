from tools.system_info import get_system_info

info = get_system_info()

print("\n===== ORION SYSTEM INTELLIGENCE =====\n")

for key, value in info.items():
    print(f"{key}: {value}")