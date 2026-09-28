"""Time-indexed CBS constraints and detected conflicts."""

from dataclasses import dataclass
from enum import Enum


class ConflictKind(Enum):
    """Kinds of collision that the planner must prevent."""

    VERTEX = "vertex"
    EDGE = "edge"


@dataclass(frozen=True)
class Constraint:
    """Restriction assigned to one drone in a CBS child node."""

    drone_id: int
    kind: ConflictKind
    location: tuple[str, ...]
    time: int
    duration: int = 1


@dataclass(frozen=True)
class Conflict:
    """First collision found between two planned drone paths."""

    first_drone: int
    second_drone: int
    kind: ConflictKind
    location: tuple[str, ...]
    time: int
    duration: int = 1
