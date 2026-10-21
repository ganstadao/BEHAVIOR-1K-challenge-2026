"""
Core data structures for TAMP test.
"""

from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any
from enum import Enum


class SubgoalStatus(Enum):
    """Subgoal execution status"""
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"


@dataclass
class Subgoal:
    """High-level subgoal in the skeleton

    Attributes:
        action_type: Type of action (e.g., "navigate_to", "press_button")
        target_object: BDDL instance name (e.g., "radio_receiver.n.01_1")
        parameters: Additional parameters for the action
        preconditions: Symbolic preconditions (for PDDL)
        effects: Symbolic effects (for PDDL)
        status: Current execution status
        error_message: Error message if failed
    """
    action_type: str
    target_object: str
    parameters: Dict[str, Any] = field(default_factory=dict)
    preconditions: List[str] = field(default_factory=list)
    effects: List[str] = field(default_factory=list)
    status: SubgoalStatus = SubgoalStatus.PENDING
    error_message: str = ""

    def to_dict(self):
        """Convert to dictionary for JSON serialization"""
        return {
            "action_type": self.action_type,
            "target_object": self.target_object,
            "parameters": self.parameters,
            "preconditions": self.preconditions,
            "effects": self.effects,
            "status": self.status.value,
            "error_message": self.error_message
        }


@dataclass
class Skeleton:
    """Complete skeleton (sequence of subgoals)

    Attributes:
        subgoals: List of subgoals to execute
        task_name: Name of the task
        description: Human-readable description
    """
    subgoals: List[Subgoal]
    task_name: str
    description: str = ""

    def __len__(self):
        return len(self.subgoals)

    def __iter__(self):
        return iter(self.subgoals)

    def to_dict(self):
        """Convert to dictionary for JSON serialization"""
        return {
            "task_name": self.task_name,
            "description": self.description,
            "subgoals": [sg.to_dict() for sg in self.subgoals]
        }


@dataclass
class ExecutionResult:
    """Result of executing a skeleton

    Attributes:
        skeleton: The executed skeleton
        success: Whether the task was completed
        num_steps: Total simulation steps
        subgoal_results: Results for each subgoal
        goal_status: BDDL goal checking result
        error_message: Error message if failed
    """
    skeleton: Skeleton
    success: bool
    num_steps: int
    subgoal_results: List[Dict[str, Any]]
    goal_status: Dict[str, List[int]]
    error_message: str = ""

    def to_dict(self):
        """Convert to dictionary for JSON serialization"""
        return {
            "skeleton": self.skeleton.to_dict(),
            "success": self.success,
            "num_steps": self.num_steps,
            "num_subgoals": len(self.skeleton),
            "num_successful_subgoals": sum(
                1 for r in self.subgoal_results if r.get("success", False)
            ),
            "subgoal_results": self.subgoal_results,
            "goal_status": self.goal_status,
            "error_message": self.error_message
        }
