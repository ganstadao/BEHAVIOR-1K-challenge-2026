"""
TAMP (Task and Motion Planning) for BEHAVIOR-1K

A modern TAMP system using LLM for high-level planning and
action primitives for low-level execution.

Architecture:
- LLM Planner: Generates symbolic subgoals
- Grounding: Maps subgoals to action primitives
- Executor: Executes primitives in simulation
- Feedback Loop: Replans on failure
"""

__version__ = "0.1.0"

from tamp.core.symbols import Predicate, Atom, State
from tamp.core.subgoal import Subgoal, SubgoalPlan
from tamp.planners.base import BasePlanner
from tamp.executors.base import BaseExecutor

__all__ = [
    "Predicate",
    "Atom",
    "State",
    "Subgoal",
    "SubgoalPlan",
    "BasePlanner",
    "BaseExecutor",
]
