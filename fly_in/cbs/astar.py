"""Low-level time-expanded A* search used by CBS nodes."""

from dataclasses import dataclass

from fly_in.cbs.conflicts import Constraint
from fly_in.graph import StaticGraph


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
        import heapq

        heuristic = self.h if goal == self.graph.map_data.end else (
            self.graph.distances_to(goal)
        )
        if start not in heuristic:
            raise ValueError(f"no path from {start!r} to {goal!r}")

        latest_constraint = max(
            (
                constraint.time + constraint.duration
                for constraint in constraints
            ),
            default=0,
        )
        simple_path_bound = sum(
            zone.movement_cost for zone in self.graph.map_data.zones.values()
        )
        horizon = latest_constraint + max(1, simple_path_bound)
        start_state = (start, 0)
        frontier: list[tuple[int, float, int, str, int]] = [
            (0, heuristic[start], 0, start, 0)
        ]
        previous: dict[tuple[str, int], tuple[str, int, TimedStep]] = {}
        best_cost: dict[tuple[str, int], tuple[int, int]] = {
            start_state: (0, 0)
        }

        while frontier:
            waits, _, cost, name, time = heapq.heappop(frontier)
            state = (name, time)
            if (waits, cost) != best_cost.get(state):
                continue

            if name == goal and not self._vertex_forbidden(
                name, time, constraints
            ):
                steps: list[TimedStep] = []
                while state != start_state:
                    old_name, old_time, step = previous[state]
                    steps.append(step)
                    state = (old_name, old_time)
                steps.reverse()
                return TimedPath(drone_id, tuple(steps))

            moves = [(edge.target, edge.duration)
                     for edge in self.graph.neighbours(name)]
            moves.append((name, 1))
            for target, duration in moves:
                new_time = time + duration
                if new_time > horizon:
                    continue
                if self._vertex_forbidden(name, time, constraints):
                    continue
                if self._vertex_forbidden(target, new_time, constraints):
                    continue
                if self._edge_forbidden(
                    name, target, time, new_time, constraints
                ):
                    continue

                new_state = (target, new_time)
                new_cost = new_time
                new_waits = waits + (target == name)
                new_score = (new_waits, new_cost)
                if new_score >= best_cost.get(
                    new_state, (float("inf"), float("inf"))
                ):
                    continue
                best_cost[new_state] = new_score
                previous[new_state] = (
                    name,
                    time,
                    TimedStep(name, target, time, duration),
                )
                heapq.heappush(frontier, (
                    new_waits,
                    new_cost + heuristic.get(target, float("inf")),
                    new_cost,
                    target,
                    new_time,
                ))

        raise ValueError(f"no constrained path from {start!r} to {goal!r}")

    @staticmethod
    def _overlaps(
        start_time: int,
        end_time: int,
        constraint_time: int,
        constraint_duration: int,
    ) -> bool:
        """Return whether two half-open time intervals overlap."""
        return start_time < constraint_time + constraint_duration and (
            constraint_time < end_time
        )

    @classmethod
    def _vertex_forbidden(
        cls,
        zone: str,
        time: int,
        constraints: frozenset[Constraint],
    ) -> bool:
        return any(
            constraint.kind.value == "vertex"
            and constraint.location == (zone,)
            and cls._overlaps(
                time, time + 1, constraint.time, constraint.duration
            )
            for constraint in constraints
        )

    @classmethod
    def _edge_forbidden(
        cls,
        source: str,
        target: str,
        start_time: int,
        end_time: int,
        constraints: frozenset[Constraint],
    ) -> bool:
        return any(
            constraint.kind.value == "edge"
            and constraint.location in ((source, target), (target, source))
            and cls._overlaps(
                start_time, end_time, constraint.time, constraint.duration
            )
            for constraint in constraints
        )
