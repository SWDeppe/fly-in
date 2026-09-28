"""Top-level best-first Conflict-Based Search orchestration."""

from concurrent.futures import Executor

from astar import ConstrainedAStar, TimedPath
from conflicts import Conflict, Constraint
from node import CBSNode
from graph import StaticGraph
from models import MapData


class CBSSolver:
    """Build and explore a Conflict Tree ordered by node score."""

    def __init__(self, map_data: MapData) -> None:
        """Create the static graph and low-level A* service."""
        self.graph = StaticGraph(map_data)
        self.astar = ConstrainedAStar(self.graph)

    def initial_paths(self, executor: Executor) -> dict[int, TimedPath]:
        """Compute one unconstrained path for every drone."""
        raise NotImplementedError

    def detect_conflicts(
        self, paths: dict[int, TimedPath]
    ) -> tuple[Conflict, ...]:
        """Find vertex, edge, capacity, and restricted-transit conflicts."""
        raise NotImplementedError

    def branch(self, node: CBSNode, conflict: Conflict) -> list[CBSNode]:
        """Create one child per conflicting drone with a local constraint."""
        raise NotImplementedError

    def solve(self, executor: Executor) -> dict[int, TimedPath]:
        """Explore best-scored nodes until a conflict-free plan exists."""
        raise NotImplementedError

    @staticmethod
    def _score(paths: dict[int, TimedPath]) -> tuple[int, int, int]:
        raise NotImplementedError

    @staticmethod
    def constraint_for(drone_id: int, conflict: Conflict) -> Constraint:
        """Convert a detected conflict into a drone-local constraint."""
        raise NotImplementedError
