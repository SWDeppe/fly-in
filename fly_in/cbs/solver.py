"""Top-level best-first Conflict-Based Search orchestration."""

from concurrent.futures import Executor
import heapq

from fly_in.cbs.astar import ConstrainedAStar, TimedPath
from fly_in.cbs.conflicts import Conflict, ConflictKind, Constraint
from fly_in.cbs.node import CBSNode
from fly_in.graph import StaticGraph
from fly_in.models import MapData


class CBSSolver:
    """Build and explore a Conflict Tree ordered by node score."""

    def __init__(self, map_data: MapData) -> None:
        """Create the static graph and low-level A* service."""
        self.graph = StaticGraph(map_data)
        self.astar = ConstrainedAStar(self.graph)

    def initial_paths(self, executor: Executor) -> dict[int, TimedPath]:
        """Compute one unconstrained path for every drone."""
        futures = {
            drone_id: executor.submit(
                self.astar.search,
                drone_id,
                self.graph.map_data.start,
                self.graph.map_data.end,
                frozenset(),
            )
            for drone_id in range(1, self.graph.map_data.drone_count + 1)
        }
        return {
            drone_id: future.result()
            for drone_id, future in futures.items()
        }

    def prioritized_paths(self) -> dict[int, TimedPath] | None:
        """Build a fast conflict-free plan by fixing drones in order."""
        paths: dict[int, TimedPath] = {}
        for drone_id in range(1, self.graph.map_data.drone_count + 1):
            constraints: frozenset[Constraint] = frozenset()
            for _ in range(100):
                path = self.astar.search(
                    drone_id,
                    self.graph.map_data.start,
                    self.graph.map_data.end,
                    constraints,
                )
                trial_paths = dict(paths)
                trial_paths[drone_id] = path
                conflicts = tuple(
                    conflict for conflict in self.detect_conflicts(trial_paths)
                    if drone_id in (
                        conflict.first_drone,
                        conflict.second_drone,
                    )
                )
                if not conflicts:
                    paths[drone_id] = path
                    break
                constraints |= frozenset(
                    self.constraint_for(drone_id, conflict)
                    for conflict in conflicts
                )
            else:
                return None
        return paths

    def detect_conflicts(
        self, paths: dict[int, TimedPath]
    ) -> tuple[Conflict, ...]:
        """Find vertex, edge, capacity, and restricted-transit conflicts."""
        conflicts: list[Conflict] = []
        zone_occupancy: dict[tuple[str, int], set[int]] = {}
        edge_usage: dict[tuple[str, str], list[tuple[int, int, int]]] = {}

        for drone_id, path in paths.items():
            if not path.steps:
                continue
            for step in path.steps:
                if step.source not in (
                    self.graph.map_data.start,
                    self.graph.map_data.end,
                ):
                    zone_occupancy.setdefault(
                        (step.source, step.start_time), set()
                    ).add(drone_id)
                if step.target not in (
                    self.graph.map_data.start,
                    self.graph.map_data.end,
                ):
                    zone_occupancy.setdefault(
                        (step.target, step.end_time), set()
                    ).add(drone_id)
                if step.source != step.target:
                    edge = (
                        (step.source, step.target)
                        if step.source < step.target
                        else (step.target, step.source)
                    )
                    edge_usage.setdefault(edge, []).append(
                        (step.start_time, step.end_time, drone_id)
                    )

        for (zone, time), occupied_drones in zone_occupancy.items():
            drones = sorted(occupied_drones)
            capacity = self.graph.map_data.zones[zone].capacity
            if len(drones) > capacity:
                for first in drones[:capacity]:
                    second = drones[capacity]
                    conflicts.append(
                        Conflict(first, second, ConflictKind.VERTEX,
                                 (zone,), time)
                    )

        for edge, usages in edge_usage.items():
            source, target = edge
            connection_capacity = next(
                graph_edge.capacity
                for graph_edge in self.graph.neighbours(source)
                if graph_edge.target == target
            )
            capacity = max(
                connection_capacity,
                self.graph.map_data.zones[source].capacity,
                self.graph.map_data.zones[target].capacity,
            )
            usages = sorted(usages, key=lambda usage: usage[2])
            if len(usages) <= capacity:
                continue
            for fir in usages[:capacity]:
                sec = usages[capacity]
                start = max(fir[0], sec[0])
                end = min(fir[1], sec[1])
                if end > start and len(usages) > capacity:
                    conflicts.append(
                        Conflict(fir[2], sec[2], ConflictKind.EDGE,
                                 (source, target), start, end - start)
                    )

        unique_conflicts = {
            (
                conflict.first_drone,
                conflict.second_drone,
                conflict.kind,
                conflict.location,
                conflict.time,
                conflict.duration,
            ): conflict
            for conflict in conflicts
        }
        return tuple(sorted(unique_conflicts.values(), key=lambda conflict: (
            conflict.time,
            conflict.first_drone,
            conflict.second_drone,
            conflict.kind.value,
        )))

    def branch(self, node: CBSNode, conflict: Conflict) -> list[CBSNode]:
        """Create one child per conflicting drone with a local constraint."""
        children: list[CBSNode] = []
        drone_ids = (conflict.first_drone, conflict.second_drone)
        first_path = node.paths[conflict.first_drone]
        second_path = node.paths[conflict.second_drone]
        if first_path.steps == second_path.steps:
            drone_ids = (max(drone_ids), max(drone_ids))

        for drone_id in drone_ids:
            constraint = self.constraint_for(drone_id, conflict)
            child = node.with_constraint(constraint)
            drone_constraints = frozenset(
                item for item in child.constraints
                if item.drone_id == drone_id
            )
            try:
                child.paths[drone_id] = self.astar.search(
                    drone_id,
                    self.graph.map_data.start,
                    self.graph.map_data.end,
                    drone_constraints,
                )
            except ValueError:
                continue
            child.conflicts = self.detect_conflicts(child.paths)
            child.score = self._score(child.paths)
            children.append(child)
        return children

    def solve(self, executor: Executor) -> dict[int, TimedPath]:
        """Explore best-scored nodes until a conflict-free plan exists."""
        if self.graph.map_data.drone_count > 4:
            prioritized = self.prioritized_paths()
            if prioritized is not None:
                return prioritized

        paths = self.initial_paths(executor)
        root = CBSNode(
            constraints=frozenset(),
            paths=paths,
            score=self._score(paths),
            conflicts=self.detect_conflicts(paths),
        )
        frontier: list[tuple[tuple[int, int, int], int, CBSNode]] = [
            (root.score, 0, root)
        ]
        sequence = 1

        while frontier:
            _, _, node = heapq.heappop(frontier)
            if node.is_solution():
                return node.paths
            children = self.branch(node, node.conflicts[0])
            bypasses = [
                child for child in children
                if child.score == node.score
                and len(child.conflicts) < len(node.conflicts)
            ]
            if bypasses:
                children = [min(
                    bypasses,
                    key=lambda child: len(child.conflicts),
                )]
            for child in children:
                heapq.heappush(frontier, (child.score, sequence, child))
                sequence += 1

        raise ValueError("no conflict-free solution exists")

    @staticmethod
    def _score(paths: dict[int, TimedPath]) -> tuple[int, int, int]:
        arrivals = [path.arrival_time for path in paths.values()]
        return (
            max(arrivals, default=0),
            sum(arrivals),
            sum(path.wait_count for path in paths.values()),
        )

    @staticmethod
    def constraint_for(drone_id: int, conflict: Conflict) -> Constraint:
        """Convert a detected conflict into a drone-local constraint."""
        return Constraint(
            drone_id=drone_id,
            kind=conflict.kind,
            location=conflict.location,
            time=conflict.time,
            duration=conflict.duration,
        )
