"""
BDDL utilities for extracting state and task information.

Provides helpers to convert BDDL tasks into the symbolic representations
used by TAMP planners.
"""

from typing import List, Tuple, Dict, Any, Optional
from bddl.activity import Conditions, get_object_scope
from bddl.condition_evaluation import compile_state, evaluate_state

from tamp.core.symbols import Atom, State, Predicate


def load_bddl_task(
    activity_name: str,
    activity_definition: int = 0,
    simulator_name: str = "behavior-1k"
) -> Tuple[Conditions, dict]:
    """Load a BDDL task definition.

    Args:
        activity_name: Name of the activity (e.g., "turning_on_radio")
        activity_definition: Problem number (default 0)
        simulator_name: Simulator domain name

    Returns:
        Tuple of (Conditions object, object scope)
    """
    conditions = Conditions(activity_name, activity_definition, simulator_name)
    scope = get_object_scope(conditions)
    return conditions, scope


def extract_initial_state(conditions: Conditions) -> State:
    """Extract initial state from BDDL conditions.

    Args:
        conditions: Parsed BDDL conditions

    Returns:
        State: Symbolic state (frozenset of atoms)
    """
    atoms = []

    # Parse initial conditions - they are in list format
    # Example: [['not', ['toggled_on', 'radio_receiver.n.01_1']]]
    for cond in conditions.parsed_initial_conditions:
        atom = _parse_bddl_literal(cond)
        if atom is not None:
            atoms.append(atom)

    return atoms


def extract_goal_state(conditions: Conditions) -> State:
    """Extract goal state from BDDL conditions.

    Args:
        conditions: Parsed BDDL conditions

    Returns:
        State: Symbolic goal state
    """
    atoms = []

    # Parse goal conditions
    # Format can be: [['predicate', 'arg1', ...], ...] or ['and', [...], [...]]
    goal = conditions.parsed_goal_conditions

    if not goal:
        return frozenset()

    # Check if it's an 'and' expression
    if isinstance(goal, list) and len(goal) > 0 and goal[0] == 'and':
        # Format: ['and', literal1, literal2, ...]
        for literal in goal[1:]:
            atom = _parse_bddl_literal(literal)
            if atom is not None:
                atoms.append(atom)
    elif isinstance(goal, list) and len(goal) > 0 and isinstance(goal[0], list):
        # Format: [literal1, literal2, ...] where each literal is a list
        for literal in goal:
            atom = _parse_bddl_literal(literal)
            if atom is not None:
                atoms.append(atom)
    else:
        # Single goal literal
        atom = _parse_bddl_literal(goal)
        if atom is not None:
            atoms.append(atom)

    return frozenset(atoms)


def extract_objects(conditions: Conditions) -> Dict[str, List[str]]:
    """Extract objects from BDDL conditions.

    Args:
        conditions: Parsed BDDL conditions

    Returns:
        Dict mapping category to list of instance names

    Example:
        >>> extract_objects(conditions)
        {
            'radio_receiver.n.01': ['radio_receiver.n.01_1'],
            'table.n.02': ['table.n.02_1'],
            'agent.n.01': ['agent.n.01_1']
        }
    """
    return conditions.parsed_objects


def get_available_objects(conditions: Conditions) -> List[str]:
    """Get flat list of all object instance names.

    Args:
        conditions: Parsed BDDL conditions

    Returns:
        List of object instance names
    """
    objects = []
    for category, instances in conditions.parsed_objects.items():
        objects.extend(instances)
    return objects


def _parse_bddl_literal(literal) -> Optional[Atom]:
    """Parse a BDDL literal into an Atom.

    Args:
        literal: BDDL literal (nested list format)

    Returns:
        Atom or None if it's a negation (we don't represent negations explicitly)

    Example:
        >>> _parse_bddl_literal(['ontop', 'radio', 'table'])
        Atom('ontop', ('radio', 'table'))

        >>> _parse_bddl_literal(['not', ['toggled_on', 'radio']])
        None  # Negations not represented
    """
    if not isinstance(literal, list) or len(literal) == 0:
        return None

    # Handle negation - we don't explicitly represent negative facts
    if literal[0] == 'not':
        return None

    # Handle positive literal: [predicate, arg1, arg2, ...]
    predicate = literal[0]
    args = tuple(str(arg) for arg in literal[1:])

    return Atom(predicate, args)


def get_task_description(activity_name: str, conditions: Conditions) -> str:
    """Generate natural language task description.

    Args:
        activity_name: Name of the activity
        conditions: Parsed BDDL conditions

    Returns:
        Natural language description
    """
    # Convert activity name to natural language
    # E.g., "turning_on_radio" -> "Turn on the radio"
    words = activity_name.replace("_", " ").split()
    if words:
        words[0] = words[0].capitalize()

    # Add goal information
    goal = conditions.parsed_goal_conditions
    description = " ".join(words)

    return description


def get_available_actions() -> List[str]:
    """Get list of available action types.

    Returns:
        List of action type strings
    """
    return [
        "navigate_to",
        "grasp",
        "place_on_top",
        "place_inside",
        "open",
        "close",
        "toggle_on",
        "toggle_off",
        "release",
    ]
