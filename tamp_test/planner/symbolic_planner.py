"""
Fixed skeleton planner for turning_on_radio task.

This is a simple planner that returns a hardcoded skeleton.
No search is performed.
"""

from typing import List
from core import Subgoal, Skeleton


class FixedSkeletonPlanner:
    """Planner that returns a fixed, hardcoded skeleton

    For the turning_on_radio task, the skeleton is:
    1. navigate_to(radio)
    2. press_button(radio)
    """

    def __init__(self):
        self.task_skeletons = self._build_task_skeletons()

    def _build_task_skeletons(self):
        """Build hardcoded skeletons for known tasks"""
        return {
            "turning_on_radio": self._build_turning_on_radio_skeleton,
            # Add more tasks here as needed
        }

    def plan(self, task_name: str, object_scope: dict) -> Skeleton:
        """Generate a skeleton for the given task

        Args:
            task_name: Name of the task
            object_scope: Mapping from BDDL instances to actual objects

        Returns:
            Skeleton: A fixed skeleton for the task

        Raises:
            NotImplementedError: If task is not supported
        """
        if task_name not in self.task_skeletons:
            raise NotImplementedError(
                f"No skeleton defined for task '{task_name}'. "
                f"Supported tasks: {list(self.task_skeletons.keys())}"
            )

        skeleton_builder = self.task_skeletons[task_name]
        return skeleton_builder(object_scope)

    def _build_turning_on_radio_skeleton(self, object_scope: dict) -> Skeleton:
        """Build skeleton for turning_on_radio task

        Skeleton:
        1. navigate_to(radio)
        2. press_button(radio) -> toggle_on
        """
        # Find the radio object in object_scope
        radio_inst = None
        for inst_name in object_scope.keys():
            if "radio_receiver" in inst_name:
                radio_inst = inst_name
                break

        if radio_inst is None:
            raise ValueError("Could not find radio object in object_scope")

        # 自定义了类似pddl的subgoal子结构
        subgoals = [
            Subgoal(
                action_type="navigate_to",
                target_object=radio_inst,
                preconditions=["reachable(living_room)"],
                effects=[f"near(robot, {radio_inst})", "at(robot, living_room)"]
            ),
            Subgoal(
                action_type="press_button",
                target_object=radio_inst,
                preconditions=[
                    f"near(robot, {radio_inst})",
                    f"toggleable({radio_inst})",
                    f"not(toggled_on({radio_inst}))"
                ],
                effects=[f"toggled_on({radio_inst})"]
            )
        ]

        skeleton = Skeleton(
            subgoals=subgoals,
            task_name="turning_on_radio",
            description="Navigate to radio and press button to turn it on"
        )

        return skeleton
