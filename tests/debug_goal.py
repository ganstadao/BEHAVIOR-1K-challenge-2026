import sys
from pathlib import Path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "bddl3"))

from tamp.utils.bddl_utils import load_bddl_task

# Load BDDL task
conditions, scope = load_bddl_task("turning_on_radio", 0)

print("Goal conditions:")
print(conditions.parsed_goal_conditions)
print("\nType:", type(conditions.parsed_goal_conditions))

if isinstance(conditions.parsed_goal_conditions, list):
    print("\nLength:", len(conditions.parsed_goal_conditions))
    for i, item in enumerate(conditions.parsed_goal_conditions):
        print(f"  [{i}]: {item} (type: {type(item)})")
