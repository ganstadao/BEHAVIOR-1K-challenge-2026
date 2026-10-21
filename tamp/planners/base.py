"""
Base interfaces for TAMP planners.

Defines the abstract interface that all planners must implement.
Planners can be LLM-based, search-based, or hybrid.
"""

from abc import ABC, abstractmethod
from typing import Optional, List, Dict, Any

from tamp.core.subgoal import SubgoalPlan
from tamp.core.symbols import State


class BasePlanner(ABC):
    """Abstract base class for all planners.

    A planner takes a task description and current state, and generates
    a plan (sequence of subgoals) to achieve the goal.
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """Initialize the planner.

        Args:
            config: Configuration dictionary (planner-specific)
        """
        self.config = config or {}
        self.planning_history: List[Dict[str, Any]] = []

    @abstractmethod
    def plan(
        self,
        task_description: str,
        initial_state: State,
        goal_state: State,
        available_objects: List[str],
        available_actions: List[str],
        context: Optional[Dict[str, Any]] = None,
    ) -> SubgoalPlan:
        """Generate a plan to achieve the goal.

        Args:
            task_description: Natural language task description
            initial_state: Current symbolic state
            goal_state: Desired symbolic state
            available_objects: List of object names in the scene
            available_actions: List of available action types
            context: Additional context (e.g., previous attempts, failures)

        Returns:
            SubgoalPlan: Sequence of subgoals to execute

        Raises:
            PlanningError: If planning fails
        """
        pass

    @abstractmethod
    def replan(
        self,
        original_plan: SubgoalPlan,
        current_state: State,
        failure_info: Dict[str, Any],
    ) -> SubgoalPlan:
        """Replan after a failure.

        Args:
            original_plan: The plan that failed
            current_state: Current state after failure
            failure_info: Information about the failure

        Returns:
            SubgoalPlan: New plan to try
        """
        pass

    def get_planning_stats(self) -> Dict[str, Any]:
        """Get statistics about planning performance.

        Returns:
            dict: Statistics (number of plans, success rate, etc.)
        """
        return {
            "total_plans": len(self.planning_history),
            "history": self.planning_history,
        }


class PlanningError(Exception):
    """Raised when planning fails."""
    pass
