"""
Executor that uses OmniGibson's action primitives.

This bridges between high-level subgoals and low-level action primitives.
"""

import time
from typing import Generator, Any, Dict

from tamp.executors.base import BaseExecutor, ExecutionError
from tamp.core.subgoal import Subgoal, SubgoalStatus

# Lazy imports to avoid circular dependencies
SymbolicSemanticActionPrimitives = None
SymbolicSemanticActionPrimitiveSet = None


def _lazy_import_primitives():
    """Lazy import of OmniGibson primitives."""
    global SymbolicSemanticActionPrimitives, SymbolicSemanticActionPrimitiveSet
    if SymbolicSemanticActionPrimitives is None:
        from omnigibson.action_primitives.symbolic_semantic_action_primitives import (
            SymbolicSemanticActionPrimitives as SSAP,
            SymbolicSemanticActionPrimitiveSet as SSAPS,
        )
        SymbolicSemanticActionPrimitives = SSAP
        SymbolicSemanticActionPrimitiveSet = SSAPS


class PrimitiveExecutor(BaseExecutor):
    """Executor using OmniGibson's SymbolicSemanticActionPrimitives.

    Maps subgoal action_types to primitive actions and executes them.

    Args:
        env: OmniGibson environment
        robot: Robot instance
        max_attempts: Maximum execution attempts per subgoal

    Example:
        >>> executor = PrimitiveExecutor(env, robot)
        >>> subgoal = Subgoal("Toggle on radio", "toggle_on", "radio_receiver.n.01_1")
        >>> success = yield from executor.execute_subgoal(subgoal)
    """

    # Mapping from subgoal action_type to primitive enum
    ACTION_MAPPING = {
        "navigate_to": "NAVIGATE_TO",
        "grasp": "GRASP",
        "place_on_top": "PLACE_ON_TOP",
        "place_inside": "PLACE_INSIDE",
        "open": "OPEN",
        "close": "CLOSE",
        "toggle_on": "TOGGLE_ON",
        "toggle_off": "TOGGLE_OFF",
        "release": "RELEASE",
        "soak_under": "SOAK_UNDER",
        "soak_inside": "SOAK_INSIDE",
        "wipe": "WIPE",
        "cut": "CUT",
        "place_near_heating_element": "PLACE_NEAR_HEATING_ELEMENT",
    }

    def __init__(self, env, robot, max_attempts: int = 3, **kwargs):
        super().__init__(env, robot, kwargs)
        self.max_attempts = max_attempts

        # Lazy initialize primitives
        _lazy_import_primitives()
        self.primitives = SymbolicSemanticActionPrimitives(env, robot)

    def can_execute(self, subgoal: Subgoal) -> bool:
        """Check if we can execute this subgoal."""
        return subgoal.action_type in self.ACTION_MAPPING

    def execute_subgoal(self, subgoal: Subgoal) -> Generator[Any, None, bool]:
        """Execute a subgoal using action primitives.

        Args:
            subgoal: The subgoal to execute

        Yields:
            Actions from the primitive (internally handled by primitives)

        Returns:
            bool: True if successful
        """
        start_time = time.time()
        subgoal.status = SubgoalStatus.IN_PROGRESS

        # Check if we can execute this action
        if not self.can_execute(subgoal):
            subgoal.status = SubgoalStatus.FAILED
            subgoal.error_message = f"Unknown action type: {subgoal.action_type}"
            self._log_execution(subgoal, False, time.time() - start_time)
            return False

        # Get the primitive action enum
        primitive_name = self.ACTION_MAPPING[subgoal.action_type]
        primitive_enum = getattr(SymbolicSemanticActionPrimitiveSet, primitive_name)

        # Get the target object
        try:
            target_obj = self._resolve_object(subgoal.target_object)
        except Exception as e:
            subgoal.status = SubgoalStatus.FAILED
            subgoal.error_message = f"Failed to resolve object '{subgoal.target_object}': {e}"
            self._log_execution(subgoal, False, time.time() - start_time)
            return False

        # Get additional arguments based on action type
        args = self._get_primitive_args(subgoal, target_obj)

        # Execute the primitive with retries
        try:
            yield from self.primitives.apply_ref(
                primitive_enum,
                *args,
                attempts=self.max_attempts
            )

            # Success!
            subgoal.status = SubgoalStatus.SUCCESS
            subgoal.execution_time = time.time() - start_time
            self._log_execution(subgoal, True, subgoal.execution_time)
            return True

        except Exception as e:
            # Failure
            subgoal.status = SubgoalStatus.FAILED
            subgoal.error_message = str(e)
            subgoal.execution_time = time.time() - start_time
            self._log_execution(subgoal, False, subgoal.execution_time)
            return False

    def _resolve_object(self, obj_name: str):
        """Resolve object name to object instance.

        Args:
            obj_name: Object name (e.g., "radio_receiver.n.01_1")

        Returns:
            Object instance from the scene
        """
        # Try to get object by name
        obj = self.env.scene.object_registry("name", obj_name)
        if obj is None:
            # Try category match (e.g., if obj_name is just "radio")
            category = obj_name.split(".")[0] if "." in obj_name else obj_name
            objs = self.env.scene.object_registry("category", category)
            if objs:
                obj = objs[0]  # Take first match

        if obj is None:
            raise ValueError(f"Object not found: {obj_name}")

        return obj

    def _get_primitive_args(self, subgoal: Subgoal, target_obj) -> tuple:
        """Get arguments for the primitive based on action type.

        Args:
            subgoal: The subgoal being executed
            target_obj: The resolved target object

        Returns:
            tuple: Arguments to pass to the primitive
        """
        action_type = subgoal.action_type
        params = subgoal.parameters

        # Most actions just need the target object
        if action_type in ["navigate_to", "grasp", "open", "close", "toggle_on", "toggle_off"]:
            return (target_obj,)

        # Release needs no arguments
        if action_type == "release":
            return ()

        # Place actions need a second object
        if action_type in ["place_on_top", "place_inside"]:
            target_surface_name = params.get("target_surface") or params.get("target_container")
            if not target_surface_name:
                raise ValueError(f"Missing target_surface/target_container for {action_type}")
            target_surface = self._resolve_object(target_surface_name)
            return (target_surface,)

        # Soak, wipe, cut need the source/tool object
        if action_type in ["soak_under", "soak_inside", "wipe", "cut"]:
            return (target_obj,)

        # Default: just target object
        return (target_obj,)

    def _log_execution(self, subgoal: Subgoal, success: bool, duration: float):
        """Log execution result."""
        self.execution_history.append({
            "subgoal": subgoal.to_dict(),
            "success": success,
            "duration": duration,
            "timestamp": time.time(),
        })
