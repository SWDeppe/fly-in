"""Low-level time-expanded A* search used by CBS nodes."""

from dataclasses import dataclass

from cbs.conflicts import Constraint
from graph import StaticGraph


@dataclass(frozen=True)
class TimedStep:
    """One occupancy or connection-traversal step in a drone path."""

    source: str
    target: str
    start_time: int
    duration: int

    @property
    def end_time(self) -> int:
        """Return the first time at which the step is complete."""
        return self.start_time + self.duration


@dataclass(frozen=True)
class TimedPath:
    """A complete path in space and time for one drone."""

    drone_id: int
    steps: tuple[TimedStep, ...]

    @property
    def arrival_time(self) -> int:
        """Return the path's final arrival time."""
        return self.steps[-1].end_time if self.steps else 0

    def step_t(self, t: int) -> TimedStep:
        for step in self.steps:
            if step.start_time <= t and step.end_time > t:
                return step
        raise IndexError()

    @property
    def wait_count(self) -> int:
        """Return how many turns the drone spends waiting in place."""
        return sum(
            step.source == step.target and step.duration == 1
            for step in self.steps
        )


class ConstrainedAStar:
    """Find one drone path while respecting only its own constraints."""
    graph: StaticGraph

    def __init__(self, graph: StaticGraph) -> None:
        """Store the static graph and its precomputed heuristic source."""
        self.graph = graph
        self.h = graph.distances_to(graph.map_data.end)

    def search(
        self,
        drone_id: int,
        start: str,
        goal: str,
        constraints: frozenset[Constraint],
    ) -> TimedPath:
        """Run A* over ``(zone, time)`` and reject forbidden states/actions."""
        raise NotImplementedError
