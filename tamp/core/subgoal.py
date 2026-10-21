"""
Subgoal representation for LLM-based planning.

A subgoal is a high-level action like "navigate to radio" or "toggle on radio".
The LLM planner generates a sequence of subgoals, which are then grounded to
action primitives and executed.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any
from enum import Enum


class SubgoalStatus(Enum):
    """Execution status of a subgoal."""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    SUCCESS = "success"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class Subgoal:
    """A high-level subgoal that the robot should achieve.

    Args:
        description: Natural language description (e.g., "Navigate to the radio")
        action_type: Type of action (e.g., "navigate_to", "toggle_on")
        target_object: Primary object for this action
        parameters: Additional parameters (e.g., target location, reference object)
        preconditions: Required state before execution (optional)
        effects: Expected state changes after execution (optional)

    Example:
        >>> subgoal = Subgoal(
        ...     description="Toggle on the radio",
        ...     action_type="toggle_on",
        ...     target_object="radio_receiver.n.01_1"
        ... )
    """
    description: str
    action_type: str
    target_object: str
    parameters: Dict[str, Any] = field(default_factory=dict)
    preconditions: List[str] = field(default_factory=list)
    effects: List[str] = field(default_factory=list)

    # Execution tracking
    status: SubgoalStatus = SubgoalStatus.PENDING
    error_message: Optional[str] = None
    execution_time: Optional[float] = None

    def __str__(self) -> str:
        return f"Subgoal({self.action_type}: {self.target_object}) - {self.status.value}"

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            "description": self.description,
            "action_type": self.action_type,
            "target_object": self.target_object,
            "parameters": self.parameters,
            "preconditions": self.preconditions,
            "effects": self.effects,
            "status": self.status.value,
            "error_message": self.error_message,
            "execution_time": self.execution_time,
        }

    @staticmethod
    def from_dict(d: dict) -> Subgoal:
        """Create from dictionary."""
        status = SubgoalStatus(d.get("status", "pending"))
        return Subgoal(
            description=d["description"],
            action_type=d["action_type"],
            target_object=d["target_object"],
            parameters=d.get("parameters", {}),
            preconditions=d.get("preconditions", []),
            effects=d.get("effects", []),
            status=status,
            error_message=d.get("error_message"),
            execution_time=d.get("execution_time"),
        )


@dataclass
class SubgoalPlan:
    """A sequence of subgoals that achieves the task goal.

    Args:
        subgoals: Ordered list of subgoals
        task_description: Natural language task description
        reasoning: LLM's reasoning for this plan (optional)

    Example:
        >>> plan = SubgoalPlan(
        ...     subgoals=[
        ...         Subgoal("Navigate to radio", "navigate_to", "radio"),
        ...         Subgoal("Toggle on radio", "toggle_on", "radio"),
        ...     ],
        ...     task_description="Turn on the radio"
        ... )
    """
    subgoals: List[Subgoal]
    task_description: str
    reasoning: Optional[str] = None

    # Execution tracking
    current_index: int = 0
    start_time: Optional[float] = None
    end_time: Optional[float] = None

    def __len__(self) -> int:
        return len(self.subgoals)

    def __getitem__(self, idx: int) -> Subgoal:
        return self.subgoals[idx]

    def is_complete(self) -> bool:
        """Check if all subgoals are complete."""
        return self.current_index >= len(self.subgoals)

    def current_subgoal(self) -> Optional[Subgoal]:
        """Get the current subgoal to execute."""
        if self.is_complete():
            return None
        return self.subgoals[self.current_index]

    def advance(self):
        """Move to the next subgoal."""
        self.current_index += 1

    def get_status_summary(self) -> Dict[str, int]:
        """Get count of subgoals by status."""
        summary = {status.value: 0 for status in SubgoalStatus}
        for subgoal in self.subgoals:
            summary[subgoal.status.value] += 1
        return summary

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            "subgoals": [sg.to_dict() for sg in self.subgoals],
            "task_description": self.task_description,
            "reasoning": self.reasoning,
            "current_index": self.current_index,
            "start_time": self.start_time,
            "end_time": self.end_time,
        }

    @staticmethod
    def from_dict(d: dict) -> SubgoalPlan:
        """Create from dictionary."""
        plan = SubgoalPlan(
            subgoals=[Subgoal.from_dict(sg) for sg in d["subgoals"]],
            task_description=d["task_description"],
            reasoning=d.get("reasoning"),
        )
        plan.current_index = d.get("current_index", 0)
        plan.start_time = d.get("start_time")
        plan.end_time = d.get("end_time")
        return plan
