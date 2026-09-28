"""Static graph operations used by CBS low-level searches."""

from dataclasses import dataclass

from fly_in.models import MapData


@dataclass(frozen=True)
class GraphEdge:
    """An available directed view of an undirected map connection."""

    source: str
    target: str
    duration: int
    capacity: int


class StaticGraph:
    """Build the map adjacency list and static heuristic distances."""

    def __init__(self, map_data: MapData) -> None:
        self.map_data = map_data
        neighbours: dict[str, list[GraphEdge]] = {}
        for connection in map_data.connections:
            a, b = connection.first, connection.second
            if (map_data.zones[a].zone_type == "blocked"
               or map_data.zones[b].zone_type == "blocked"):
                continue
            neighbours.setdefault(a, []).append(
                GraphEdge(source=a,
                          target=b,
                          duration=map_data.zones[b].movement_cost,
                          capacity=connection.capacity)
            )
            neighbours.setdefault(b, []).append(
                GraphEdge(source=b,
                          target=a,
                          duration=map_data.zones[a].movement_cost,
                          capacity=connection.capacity)
            )
        self._NEIGBOURS = neighbours

    def neighbours(self, zone: str) -> list[GraphEdge]:
        return self._NEIGBOURS.get(zone, [])

    def distances_to(self, goal: str) -> dict[str, int]:
        """Run reverse Dijkstra to provide A* heuristic values."""
        import heapq

        frontier: list[tuple[int, str]] = [(0, goal)]
        # previous: dict[str, str] = {}
        visited: dict[str, int] = {}

        while frontier:
            cost, name = heapq.heappop(frontier)

            if name in visited:
                continue

            visited[name] = cost

            for edge in self.neighbours(name):
                new_name = edge.target
                new_cost = cost + edge.duration

                if (new_name not in visited
                   or visited[new_name] > new_cost):
                    heapq.heappush(frontier, (new_cost, new_name))

        return visited
