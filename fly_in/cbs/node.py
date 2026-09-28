"""CBS high-level nodes and conflict detection contracts."""

from dataclasses import dataclass, field

from cbs.astar import TimedPath
from cbs.conflicts import Conflict, Constraint


@dataclass
class CBSNode:
    """One branch of the Conflict Tree with a complete path assignment."""

    constraints: frozenset[Constraint]
    paths: dict[int, TimedPath]
    score: tuple[int, int, int]
    conflicts: tuple[Conflict, ...] = field(default_factory=tuple)

    def with_constraint(self, constraint: Constraint) -> "CBSNode":
        """Create a child constraint set without mutating this node."""
        return CBSNode(
            constraints=self.constraints | frozenset((constraint,)),
            paths=dict(self.paths),
            score=self.score,
            conflicts=self.conflicts,
        )

    def is_solution(self) -> bool:
        """Return whether no pair of paths conflicts."""
        return not self.conflicts
