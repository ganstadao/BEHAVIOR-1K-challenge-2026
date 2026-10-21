"""
Symbolic primitives for TAMP: predicates, atoms, and states.

Inspired by TANDEM's design but tailored for BEHAVIOR-1K/BDDL.
These are lightweight, serializable representations used by the LLM planner.
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import Tuple, FrozenSet


@dataclass(frozen=True)
class Predicate:
    """A predicate like OnTop, ToggledOn, etc.

    Args:
        name: Predicate name (e.g., "ontop", "toggled_on")
        arity: Number of arguments (1 for unary, 2 for binary)

    Example:
        >>> on_top = Predicate("ontop", 2)
        >>> toggled_on = Predicate("toggled_on", 1)
    """
    name: str
    arity: int

    def ground(self, *values: str) -> Atom:
        """Ground this predicate with specific objects.

        Args:
            *values: Object names to bind to parameters

        Returns:
            Atom: Grounded predicate

        Example:
            >>> on_top = Predicate("ontop", 2)
            >>> on_top.ground("apple", "table")
            Atom(predicate='ontop', values=('apple', 'table'))
        """
        if len(values) != self.arity:
            raise ValueError(
                f"{self.name} expects {self.arity} arguments, got {len(values)}: {values}"
            )
        return Atom(self.name, tuple(str(v) for v in values))


@dataclass(frozen=True)
class Atom:
    """A grounded predicate: predicate applied to specific objects.

    Args:
        predicate: Predicate name
        values: Tuple of object names

    Example:
        >>> atom = Atom("ontop", ("apple", "table"))
        >>> str(atom)
        'ontop(apple, table)'
    """
    predicate: str
    values: Tuple[str, ...] = ()

    def __post_init__(self):
        object.__setattr__(self, "values", tuple(self.values))

    def __str__(self) -> str:
        if self.values:
            return f"{self.predicate}({', '.join(self.values)})"
        return self.predicate

    def __repr__(self) -> str:
        return f"Atom({self.predicate!r}, {self.values!r})"

    @staticmethod
    def from_string(s: str) -> Atom:
        """Parse atom from string like 'ontop(apple, table)'.

        Args:
            s: String representation

        Returns:
            Atom: Parsed atom
        """
        s = s.strip()
        if "(" not in s:
            return Atom(s, ())

        predicate, rest = s.split("(", 1)
        rest = rest.rstrip(")")
        if not rest:
            return Atom(predicate.strip(), ())

        values = tuple(v.strip() for v in rest.split(","))
        return Atom(predicate.strip(), values)


# A symbolic state is a frozen set of atoms that hold
State = FrozenSet[Atom]


def state_to_dict(state: State) -> dict:
    """Convert state to a readable dict for LLM prompts.

    Args:
        state: Symbolic state

    Returns:
        dict: Grouped by predicate type

    Example:
        >>> state = frozenset([
        ...     Atom("ontop", ("apple", "table")),
        ...     Atom("toggled_on", ("radio",))
        ... ])
        >>> state_to_dict(state)
        {'ontop': [['apple', 'table']], 'toggled_on': [['radio']]}
    """
    result = {}
    for atom in state:
        if atom.predicate not in result:
            result[atom.predicate] = []
        result[atom.predicate].append(list(atom.values))
    return result


def dict_to_state(d: dict) -> State:
    """Convert dict back to state.

    Args:
        d: Dict from state_to_dict

    Returns:
        State: Symbolic state
    """
    atoms = []
    for predicate, value_lists in d.items():
        for values in value_lists:
            atoms.append(Atom(predicate, tuple(values)))
    return frozenset(atoms)
