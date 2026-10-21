"""
Wrapper for OmniGibson action primitives.

Provides a clean interface to execute low-level actions.
"""

import numpy as np
from typing import Generator, Any

from omnigibson.action_primitives.starter_semantic_action_primitives import (
    StarterSemanticActionPrimitives,
    StarterSemanticActionPrimitiveSet
)
from omnigibson.object_states import ToggledOn


class ActionPrimitiveError(Exception):
    """Exception raised when action primitive fails"""
    pass


class PrimitiveWrapper:
    """Wrapper for OmniGibson action primitives

    This class provides a simplified interface to execute actions
    using OmniGibson's built-in primitives.
    """

    def __init__(self, env, robot):
        """Initialize the primitive wrapper

        Args:
            env: OmniGibson environment
            robot: Robot instance
        """
        self.env = env
        self.robot = robot

        # Initialize action primitives
        # Note: StarterSemanticActionPrimitives uses ground truth object positions by default
        # CuRobo is enabled for Tiago (config files exist)
        self.primitives = StarterSemanticActionPrimitives(
            env=env,
            robot=robot
            # skip_curobo_initilization removed - Tiago has CuRobo configs
        )

        print(f"[PrimitiveWrapper] Initialized with robot: {robot.name}")

    def execute_navigate_to(self, target_obj) -> Generator[None, None, bool]:
        """Execute navigate_to action

        Args:
            target_obj: Target object to navigate to

        Yields:
            None (steps through the action)

        Returns:
            bool: True if successful

        Raises:
            ActionPrimitiveError: If navigation fails
        """
        print(f"[PrimitiveWrapper] Executing navigate_to: {target_obj.name}")

        # Log initial state
        robot_pos = self.robot.get_position()
        target_pos = target_obj.get_position()
        distance = np.linalg.norm(np.array(robot_pos) - np.array(target_pos))
        print(f"[PrimitiveWrapper]   Robot position: {robot_pos}")
        print(f"[PrimitiveWrapper]   Target position: {target_pos}")
        print(f"[PrimitiveWrapper]   Initial distance: {distance:.3f}m")

        try:
            # Get the primitive enum
            primitive_enum = StarterSemanticActionPrimitiveSet.NAVIGATE_TO

            # Execute the primitive (generator)
            step_count = 0
            for action in self.primitives.apply_ref(primitive_enum, target_obj):
                step_count += 1

                # Execute the action in the environment
                self.env.step(action)

                # Log progress every 10 steps
                if step_count % 10 == 0:
                    robot_pos = self.robot.get_position()
                    distance = np.linalg.norm(np.array(robot_pos) - np.array(target_pos))
                    print(f"[PrimitiveWrapper]   Step {step_count}, distance: {distance:.3f}m, position: {robot_pos}")

                yield  # Yield control back to caller

            # Verify we reached the target
            robot_pos = self.robot.get_position()
            final_distance = np.linalg.norm(np.array(robot_pos) - np.array(target_pos))
            print(f"[PrimitiveWrapper]   Final position: {robot_pos}")
            print(f"[PrimitiveWrapper]   Final distance: {final_distance:.3f}m")

            if self._is_near(target_obj):
                print(f"[PrimitiveWrapper] ✓ Navigation successful (total steps: {step_count})")
                return True
            else:
                raise ActionPrimitiveError(
                    f"Navigation completed but robot not near target. "
                    f"Distance: {self._get_distance(target_obj):.2f}m"
                )

        except Exception as e:
            print(f"[PrimitiveWrapper] ✗ Navigation failed: {e}")
            raise ActionPrimitiveError(f"Navigate failed: {e}")

    def execute_press_button(self, target_obj) -> Generator[None, None, bool]:
        """Execute press_button action (mapped to TOGGLE_ON)

        Args:
            target_obj: Target object to toggle

        Yields:
            None (steps through the action)

        Returns:
            bool: True if successful

        Raises:
            ActionPrimitiveError: If toggle fails
        """
        print(f"[PrimitiveWrapper] Executing press_button: {target_obj.name}")

        # Check if object is toggleable
        if ToggledOn not in target_obj.states:
            raise ActionPrimitiveError(
                f"Object {target_obj.name} does not have ToggledOn state"
            )

        # Get initial state
        initial_state = target_obj.states[ToggledOn].get_value()
        print(f"[PrimitiveWrapper] Initial toggled state: {initial_state}")

        try:
            # Get the primitive enum
            primitive_enum = StarterSemanticActionPrimitiveSet.TOGGLE_ON

            # Execute the primitive
            for action in self.primitives.apply_ref(primitive_enum, target_obj):
                # Execute the action in the environment
                self.env.step(action)
                yield

            # Verify state changed
            final_state = target_obj.states[ToggledOn].get_value()
            print(f"[PrimitiveWrapper] Final toggled state: {final_state}")

            if final_state != initial_state:
                print(f"[PrimitiveWrapper] ✓ Button press successful")
                return True
            else:
                raise ActionPrimitiveError(
                    f"Toggle action did not change state. "
                    f"State remains: {final_state}"
                )

        except Exception as e:
            print(f"[PrimitiveWrapper] ✗ Button press failed: {e}")
            raise ActionPrimitiveError(f"Press button failed: {e}")

    def _is_near(self, obj, threshold=2.0):
        """Check if robot is near the object

        Args:
            obj: Object to check
            threshold: Distance threshold in meters

        Returns:
            bool: True if robot is within threshold
        """
        distance = self._get_distance(obj)
        return distance < threshold

    def _get_distance(self, obj):
        """Get distance between robot and object

        Args:
            obj: Object to measure distance to

        Returns:
            float: Distance in meters
        """
        robot_pos = self.robot.get_position()
        obj_pos = obj.get_position()
        distance = np.linalg.norm(robot_pos - obj_pos)
        return distance
