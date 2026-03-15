import subprocess
import re

test_files = [
    ("test_agents/test_units.py", "Units"),
    ("test_agents/test_phase1.py", "Phase 1"),
    ("test_agents/test_agent1.py", "Agent 1"),
    ("test_agents/test_agent2.py", "Agent 2"),
    ("test_agents/test_agent3.py", "Agent 3"),
    ("test_agents/test_agent4.py", "Agent 4"),
    ("test_agents/test_agent5.py", "Agent 5"),
    ("test_ks4_ks8.py", "KS4/KS8"),
    ("test_agents/test_pure_pa.py", "Pure PA")
]

total_orig = 0
for path, name in test_files:
    try:
        res = subprocess.run(["python3", path], capture_output=True, text=True)
        # On cherche les lignes "PASS" avec l'émoji ou non
        count = len(re.findall(r"PASS", res.stdout))
        print(f"{name} ({path}): {count}")
        total_orig += count
    except Exception as e:
        print(f"{name} FAILED: {e}")

print(f"\nTotal confirmés: {total_orig}")
