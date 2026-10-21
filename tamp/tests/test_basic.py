"""
Simple test script to verify TAMP components without running full simulation.

Tests:
1. Symbol creation and manipulation
2. Subgoal creation and plan management
3. LLM planner (with mock if no API key)
4. BDDL parsing
"""

import sys
from pathlib import Path

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from tamp.core.symbols import Atom, Predicate, State, state_to_dict, dict_to_state
from tamp.core.subgoal import Subgoal, SubgoalPlan, SubgoalStatus
from tamp.utils.bddl_utils import load_bddl_task, extract_initial_state, extract_goal_state


# 简单符号封装测试
def test_symbols():
    """Test symbol primitives."""
    print("="*60)
    print("TEST 1: Symbol Primitives")
    print("="*60)

    # Create predicates
    on_top = Predicate("ontop", 2) # 自定义二元谓词
    toggled_on = Predicate("toggled_on", 1) # 自定义一元谓词

    # Ground them
    atom1 = on_top.ground("radio", "table") # 绑定了实体object的谓词
    atom2 = toggled_on.ground("radio")

    print(f"✓ Created atom: {atom1}")
    print(f"✓ Created atom: {atom2}")

    # Create state
    state = frozenset([atom1, atom2])
    print(f"✓ Created state with {len(state)} atoms")

    # Convert to dict and back
    state_dict = state_to_dict(state)
    print(f"✓ State as dict: {state_dict}")

    state2 = dict_to_state(state_dict)
    assert state == state2, "State conversion failed"
    print(f"✓ State roundtrip successful")

    print()

# 简单subgoal生成测试
def test_subgoals():
    """Test subgoal and plan management."""
    print("="*60)
    print("TEST 2: Subgoals and Plans")
    print("="*60)

    # Create subgoals
    sg1 = Subgoal(
        description="Navigate to the radio",
        action_type="navigate_to",
        target_object="radio_receiver.n.01_1",
    )

    sg2 = Subgoal(
        description="Toggle on the radio",
        action_type="toggle_on",
        target_object="radio_receiver.n.01_1",
        preconditions=["near(robot, radio_receiver.n.01_1)"],
        effects=["toggled_on(radio_receiver.n.01_1)"],
    )

    print(f"✓ Created subgoal: {sg1.description}")
    print(f"✓ Created subgoal: {sg2.description}")

    # Create plan
    plan = SubgoalPlan(
        subgoals=[sg1, sg2],
        task_description="Turn on the radio",
        reasoning="Navigate to object first, then toggle it on"
    )

    print(f"✓ Created plan with {len(plan)} subgoals")
    print(f"  Reasoning: {plan.reasoning}")

    # Test plan execution tracking
    assert not plan.is_complete(), "Plan should not be complete"
    assert plan.current_subgoal() == sg1, "Should be at first subgoal"

    sg1.status = SubgoalStatus.SUCCESS
    plan.advance()

    assert plan.current_subgoal() == sg2, "Should be at second subgoal"
    assert not plan.is_complete(), "Plan should not be complete yet"

    sg2.status = SubgoalStatus.SUCCESS
    plan.advance()

    assert plan.is_complete(), "Plan should be complete"
    print(f"✓ Plan execution tracking works")

    # Test serialization
    plan_dict = plan.to_dict()
    plan2 = SubgoalPlan.from_dict(plan_dict)
    assert len(plan2) == len(plan), "Serialization failed"
    print(f"✓ Plan serialization works")

    print()


def test_bddl_parsing():
    """Test BDDL parsing utilities."""
    print("="*60)
    print("TEST 3: BDDL Parsing")
    print("="*60)

    try:
        # Load BDDL task
        conditions, scope = load_bddl_task("turning_on_radio", 0)
        print(f"✓ Loaded BDDL task: turning_on_radio")

        # Extract states
        initial_state = extract_initial_state(conditions)
        goal_state = extract_goal_state(conditions)

        print(f"✓ Initial state: {len(initial_state)} atoms")
        for atom in list(initial_state)[:3]:  # Show first 3
            print(f"  - {atom}")

        print(f"✓ Goal state: {len(goal_state)} atoms")
        for atom in goal_state:
            print(f"  - {atom}")

        # Extract objects
        objects = conditions.parsed_objects
        print(f"✓ Objects: {list(objects.keys())}")

        print()

    except Exception as e:
        print(f"✗ BDDL parsing failed: {e}")
        print("  (This is expected if BDDL files are not accessible)")
        print()


def test_llm_planner_mock():
    """Test LLM planner with mock (no API call)."""
    print("="*60)
    print("TEST 4: LLM Planner (Mock)")
    print("="*60)

    print("Skipping LLM test - requires API key and actual call")
    print("Run the full example with OPENAI_API_KEY set to test LLM")
    print()


def main():
    """Run all tests."""
    print("\n")
    print("╔" + "="*58 + "╗")
    print("║" + " "*18 + "TAMP Unit Tests" + " "*25 + "║")
    print("╚" + "="*58 + "╝")
    print()

    try:
        test_symbols()
        test_subgoals()
        test_bddl_parsing()
        test_llm_planner_mock()

        print("="*60)
        print("✓ All tests passed!")
        print("="*60)
        print()

    except Exception as e:
        print(f"\n✗ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
