"""
Executor for skeleton (sequence of subgoals).

Executes each subgoal using action primitives.
"""

from typing import Generator, List, Tuple, Dict, Any

from core import Subgoal, Skeleton, SubgoalStatus, ExecutionResult
from low_level.primitive_wrapper import PrimitiveWrapper, ActionPrimitiveError


class SkeletonExecutor:
    """Executes a skeleton by calling action primitives for each subgoal"""

    def __init__(self, env, robot):
        """Initialize the skeleton executor

        Args:
            env: OmniGibson environment
            robot: Robot instance
        """
        self.env = env
        self.robot = robot
        # 我的理解这是专门为该任务准备的俩个sampler的动作原语执行函数，具体用的就是behavior官方提供的实现
        self.primitive_wrapper = PrimitiveWrapper(env, robot)

        print(f"[SkeletonExecutor] Initialized")

    def execute_skeleton(
        self,
        skeleton: Skeleton,
        object_scope: Dict[str, Any]
    ) -> Generator[None, None, ExecutionResult]:
        """Execute the entire skeleton

        Args:
            skeleton: Skeleton to execute
            object_scope: Mapping from BDDL instances to actual objects

        Yields:
            None (steps through execution)

        Returns:
            ExecutionResult: Execution result with detailed info
        """
        print(f"\n{'='*60}")
        print(f"[SkeletonExecutor] Executing skeleton: {skeleton.task_name}")
        print(f"[SkeletonExecutor] Number of subgoals: {len(skeleton)}")
        print(f"{'='*60}\n")

        subgoal_results = []
        total_steps = 0

        for i, subgoal in enumerate(skeleton):
            print(f"\n--- Subgoal {i+1}/{len(skeleton)} ---")
            print(f"Action: {subgoal.action_type}")
            print(f"Target: {subgoal.target_object}")

            # Log target object details
            if subgoal.target_object in object_scope:
                target_obj = object_scope[subgoal.target_object]
                target_pos = target_obj.get_position()
                target_ori = target_obj.get_orientation()
                print(f"Target position: {target_pos}")
                print(f"Target orientation: {target_ori}")

            # Log robot state before action
            robot_pos = self.robot.get_position()
            robot_ori = self.robot.get_orientation()
            print(f"Robot position (before): {robot_pos}")
            print(f"Robot orientation (before): {robot_ori}")

            # Update status
            subgoal.status = SubgoalStatus.RUNNING

            try:
                # Resolve target object
                if subgoal.target_object not in object_scope:
                    raise ValueError(
                        f"Target object '{subgoal.target_object}' not found in object_scope. "
                        f"Available: {list(object_scope.keys())}"
                    )

                target_obj = object_scope[subgoal.target_object]

                # Execute subgoal
                step_count = 0
                for _ in self._execute_subgoal(subgoal, target_obj):
                    step_count += 1
                    total_steps += 1
                    yield

                # Success
                subgoal.status = SubgoalStatus.SUCCESS

                # Log robot state after action
                robot_pos = self.robot.get_position()
                robot_ori = self.robot.get_orientation()
                print(f"Robot position (after): {robot_pos}")
                print(f"Robot orientation (after): {robot_ori}")

                subgoal_results.append({
                    "subgoal_index": i,
                    "action": subgoal.action_type,
                    "target": subgoal.target_object,
                    "success": True,
                    "error": "",
                    "steps": step_count
                })

                print(f"✓ Subgoal {i+1} completed in {step_count} steps")

            except ActionPrimitiveError as e:
                # Primitive execution failed
                subgoal.status = SubgoalStatus.FAILED
                subgoal.error_message = str(e)

                subgoal_results.append({
                    "subgoal_index": i,
                    "action": subgoal.action_type,
                    "target": subgoal.target_object,
                    "success": False,
                    "error": str(e),
                    "steps": 0
                })

                print(f"✗ Subgoal {i+1} failed: {e}")

                # Stop execution on first failure
                error_msg = f"Execution failed at subgoal {i+1}: {e}"
                return self._build_result(
                    skeleton,
                    False,
                    total_steps,
                    subgoal_results,
                    error_msg
                )

            except Exception as e:
                # Unexpected error
                subgoal.status = SubgoalStatus.FAILED
                subgoal.error_message = f"Unexpected error: {e}"

                subgoal_results.append({
                    "subgoal_index": i,
                    "action": subgoal.action_type,
                    "target": subgoal.target_object,
                    "success": False,
                    "error": f"Unexpected error: {e}",
                    "steps": 0
                })

                print(f"✗ Subgoal {i+1} failed with unexpected error: {e}")

                error_msg = f"Unexpected error at subgoal {i+1}: {e}"
                return self._build_result(
                    skeleton,
                    False,
                    total_steps,
                    subgoal_results,
                    error_msg
                )

        # All subgoals completed, check goal
        print(f"\n{'='*60}")
        print(f"[SkeletonExecutor] All subgoals completed")
        print(f"[SkeletonExecutor] Total steps: {total_steps}")
        print(f"{'='*60}\n")

        # Check if task goal is satisfied
        goal_satisfied, goal_status = self._check_goal()

        return self._build_result(
            skeleton,
            goal_satisfied,
            total_steps,
            subgoal_results,
            "" if goal_satisfied else "Goal not satisfied after executing all subgoals"
        )

    def _execute_subgoal(
        self,
        subgoal: Subgoal,
        target_obj
    ) -> Generator[None, None, bool]:
        """Execute a single subgoal

        Args:
            subgoal: Subgoal to execute
            target_obj: Resolved target object

        Yields:
            None (steps through execution)

        Returns:
            bool: True if successful

        Raises:
            ActionPrimitiveError: If execution fails
        """
        # Map action_type to primitive method
        if subgoal.action_type == "navigate_to":
            success = yield from self.primitive_wrapper.execute_navigate_to(target_obj)
            return success

        elif subgoal.action_type == "press_button":
            success = yield from self.primitive_wrapper.execute_press_button(target_obj)
            return success

        else:
            raise ActionPrimitiveError(
                f"Unknown action type: {subgoal.action_type}"
            )

    def _check_goal(self) -> Tuple[bool, Dict]:
        """Check if task goal is satisfied

        Returns:
            Tuple of (satisfied: bool, status: dict)
        """
        task = self.env.task

        if hasattr(task, 'compiled_task') and task.compiled_task is not None:
            # Use BDDL goal checking
            goal_satisfied, goal_status = task.compiled_task.check_goal(
                task._evaluate_predicate
            )
            return goal_satisfied, goal_status
        else:
            # No compiled task, assume success if we got here
            return True, {"satisfied": [], "unsatisfied": []}

    def _build_result(
        self,
        skeleton: Skeleton,
        success: bool,
        num_steps: int,
        subgoal_results: List[Dict],
        error_message: str
    ) -> ExecutionResult:
        """Build execution result

        Args:
            skeleton: Executed skeleton
            success: Whether task was successful
            num_steps: Total steps taken
            subgoal_results: Results for each subgoal
            error_message: Error message if failed

        Returns:
            ExecutionResult
        """
        # Get goal status
        _, goal_status = self._check_goal()

        return ExecutionResult(
            skeleton=skeleton,
            success=success,
            num_steps=num_steps,
            subgoal_results=subgoal_results,
            goal_status=goal_status,
            error_message=error_message
        )
