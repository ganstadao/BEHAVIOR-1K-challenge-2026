"""
Complete example: Using TAMP to solve turning_on_radio task.

This demonstrates the full pipeline:
1. Load BDDL task
2. Extract symbolic state
3. LLM generates plan
4. Execute plan using primitives
"""

import os
import json
from pathlib import Path

# Add parent directory to path
import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import omnigibson as og
from omnigibson.macros import gm

# TAMP imports
from tamp.planners.llm_planner import LLMPlanner
from tamp.executors.primitive_executor import PrimitiveExecutor
from tamp.utils.bddl_utils import (
    load_bddl_task,
    extract_initial_state,
    extract_goal_state,
    get_available_objects,
    get_available_actions,
    get_task_description,
)
from tamp.core.subgoal import SubgoalStatus


def setup_environment(task_name: str = "turning_on_radio"):
    """Setup OmniGibson environment for the task.

    Args:
        task_name: BDDL task name

    Returns:
        Tuple of (env, robot, conditions)
    """
    # Set headless mode
    gm.HEADLESS = True
    gm.USE_GPU_DYNAMICS = True

    # Load BDDL task
    conditions, scope = load_bddl_task(task_name)

    # Create environment config
    config = {
        "scene": {
            "type": "InteractiveTraversableScene",
            "scene_model": "Rs_int",  # Simple scene
        },
        "robots": [
            {
                "type": "R1",
                "obs_modalities": ["rgb", "proprio"],
                "action_type": "continuous",
                "action_normalize": False,
            }
        ],
        "task": {
            "type": "BehaviorTask",
            "activity_name": task_name,
            "activity_definition": 0,
            "online_object_sampling": False,
        }
    }

    # Create environment
    env = og.Environment(configs=config)
    robot = env.robots[0]

    print(f"✓ Environment loaded: {task_name}")
    print(f"✓ Scene: {env.scene.scene_model}")
    print(f"✓ Robot: {robot.name}")

    return env, robot, conditions


def run_tamp_pipeline(
    env,
    robot,
    conditions,
    llm_model: str = "gpt-4",
    api_key: str = None,
    max_replans: int = 2,
):
    """Run the complete TAMP pipeline.

    Args:
        env: OmniGibson environment
        robot: Robot instance
        conditions: BDDL conditions
        llm_model: LLM model name
        api_key: API key for LLM
        max_replans: Maximum replanning attempts

    Returns:
        dict: Results including plan, execution status, statistics
    """
    # 1. Extract task information
    print("\n" + "="*60)
    print("STEP 1: Extracting task information from BDDL")
    print("="*60)

    task_description = get_task_description(
        conditions.behavior_activity, conditions
    )
    initial_state = extract_initial_state(conditions)
    goal_state = extract_goal_state(conditions)
    available_objects = get_available_objects(conditions)
    available_actions = get_available_actions()

    print(f"Task: {task_description}")
    print(f"Objects: {available_objects}")
    print(f"Initial state: {len(initial_state)} atoms")
    print(f"Goal state: {len(goal_state)} atoms")

    # 2. Initialize planner and executor
    print("\n" + "="*60)
    print("STEP 2: Initializing LLM planner and executor")
    print("="*60)

    planner = LLMPlanner(
        model=llm_model,
        api_key=api_key,
        temperature=0.7,
    )
    executor = PrimitiveExecutor(env, robot, max_attempts=3)

    print(f"✓ Planner: {llm_model}")
    print(f"✓ Executor: PrimitiveExecutor")

    # 3. Generate initial plan
    print("\n" + "="*60)
    print("STEP 3: Generating plan with LLM")
    print("="*60)

    plan = planner.plan(
        task_description=task_description,
        initial_state=initial_state,
        goal_state=goal_state,
        available_objects=available_objects,
        available_actions=available_actions,
    )

    print(f"✓ Plan generated with {len(plan)} subgoals")
    if plan.reasoning:
        print(f"Reasoning: {plan.reasoning}")

    print("\nPlan:")
    for i, subgoal in enumerate(plan.subgoals):
        print(f"  {i+1}. {subgoal.description}")
        print(f"     Action: {subgoal.action_type}({subgoal.target_object})")

    # 4. Execute plan
    print("\n" + "="*60)
    print("STEP 4: Executing plan")
    print("="*60)

    replan_count = 0
    execution_success = False

    while not plan.is_complete() and replan_count <= max_replans:
        current_subgoal = plan.current_subgoal()

        print(f"\n→ Executing: {current_subgoal.description}")

        # Execute the subgoal
        try:
            success = yield from executor.execute_subgoal(current_subgoal)

            if success:
                print(f"  ✓ Success in {current_subgoal.execution_time:.2f}s")
                plan.advance()
            else:
                print(f"  ✗ Failed: {current_subgoal.error_message}")

                # Try to replan
                if replan_count < max_replans:
                    print(f"\n  Replanning (attempt {replan_count + 1}/{max_replans})...")

                    # Get current state (simplified - should query env)
                    current_state = initial_state  # TODO: get actual current state

                    failure_info = {
                        "step": plan.current_index,
                        "action": current_subgoal.action_type,
                        "error": current_subgoal.error_message,
                    }

                    plan = planner.replan(plan, current_state, failure_info)
                    replan_count += 1

                    print(f"  ✓ New plan with {len(plan)} subgoals")
                else:
                    print(f"  Max replanning attempts reached.")
                    break

        except Exception as e:
            print(f"  ✗ Execution error: {e}")
            break

    # 5. Check if goal is achieved
    execution_success = plan.is_complete()

    print("\n" + "="*60)
    print("STEP 5: Results")
    print("="*60)

    status_summary = plan.get_status_summary()
    print(f"Plan completion: {execution_success}")
    print(f"Status: {status_summary}")
    print(f"Replans: {replan_count}")

    # 6. Gather statistics
    results = {
        "success": execution_success,
        "task": task_description,
        "plan": plan.to_dict(),
        "replans": replan_count,
        "status_summary": status_summary,
        "planning_stats": planner.get_planning_stats(),
        "execution_stats": executor.get_execution_stats(),
    }

    return results


def main():
    """Main entry point."""
    print("="*60)
    print("TAMP for BEHAVIOR-1K: turning_on_radio Example")
    print("="*60)

    # Check for API key
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        print("\n⚠ Warning: OPENAI_API_KEY not set. Using mock planner.")
        print("Set OPENAI_API_KEY environment variable to use real LLM.\n")

    # Setup environment
    env, robot, conditions = setup_environment("turning_on_radio")

    try:
        # Run TAMP pipeline
        results = yield from run_tamp_pipeline(
            env, robot, conditions,
            llm_model="gpt-4",
            api_key=api_key,
        )

        # Save results
        output_dir = Path(__file__).parent / "outputs"
        output_dir.mkdir(exist_ok=True)
        output_file = output_dir / "turning_on_radio_results.json"

        with open(output_file, "w") as f:
            json.dump(results, f, indent=2)

        print(f"\n✓ Results saved to: {output_file}")

        if results["success"]:
            print("\n🎉 Task completed successfully!")
        else:
            print("\n❌ Task failed.")

    finally:
        # Cleanup
        env.close()
        print("\n✓ Environment closed")


if __name__ == "__main__":
    # Run the example
    gen = main()
    try:
        while True:
            next(gen)
    except StopIteration:
        pass
