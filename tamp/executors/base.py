"""
Base interfaces for TAMP executors.

Defines the abstract interface that all executors must implement.
Executors take subgoals and execute them using action primitives.
"""

from abc import ABC, abstractmethod
from typing import Optional, Dict, Any, Generator

from tamp.core.subgoal import Subgoal, SubgoalStatus


class BaseExecutor(ABC):
    """Abstract base class for all executors.

    An executor takes a subgoal and executes it using low-level
    action primitives in the simulation environment.
    """

    def __init__(self, env, robot, config: Optional[Dict[str, Any]] = None):
        """Initialize the executor.

        Args:
            env: OmniGibson environment
            robot: Robot instance
            config: Configuration dictionary (executor-specific)
        """
        self.env = env
        self.robot = robot
        self.config = config or {}
        self.execution_history = []

    @abstractmethod
    def execute_subgoal(self, subgoal: Subgoal) -> Generator[Any, None, bool]:
        """Execute a single subgoal.

        This is a generator that yields low-level actions to the environment.

        Args:
            subgoal: The subgoal to execute

        Yields:
            Low-level actions (depends on the primitive implementation)

        Returns:
            bool: True if execution succeeded, False otherwise

        Example:
            >>> executor = PrimitiveExecutor(env, robot)
            >>> subgoal = Subgoal("Navigate to radio", "navigate_to", "radio")
            >>> for action in executor.execute_subgoal(subgoal):
            ...     obs, reward, done, info = env.step(action)
        """
        pass

    @abstractmethod
    def can_execute(self, subgoal: Subgoal) -> bool:
        """Check if this executor can execute the given subgoal.

        Args:
            subgoal: The subgoal to check

        Returns:
            bool: True if this executor can handle this subgoal
        """
        pass

    def get_execution_stats(self) -> Dict[str, Any]:
        """Get statistics about execution performance.

        Returns:
            dict: Statistics (success rate, average time, etc.)
        """
        total = len(self.execution_history)
        if total == 0:
            return {"total_executions": 0}

        successes = sum(1 for h in self.execution_history if h.get("success", False))
        return {
            "total_executions": total,
            "success_rate": successes / total,
            "history": self.execution_history,
        }


class ExecutionError(Exception):
    """Raised when execution fails."""
    pass
