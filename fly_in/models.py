"""Typed domain objects shared by the parser, solver, and simulator."""

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Zone:
    """A map zone and its occupancy rules."""

    name: str
    x: int
    y: int
    zone_type: str = "normal"
    color: str = "none"
    capacity: int = 1

    @property
    def movement_cost(self) -> int:
        """Return the cost of entering this zone."""
        return 2 if self.zone_type == "restricted" else 1


@dataclass(frozen=True)
class Connection:
    """An undirected link between two zone names."""

    first: str
    second: str
    capacity: int = 1


@dataclass
class MapData:
    """Complete validated map loaded from an input file."""

    drone_count: int
    start: str
    end: str
    zones: dict[str, Zone] = field(default_factory=dict[str, Zone])
    connections: list[Connection] = field(default_factory=list[Connection])


@dataclass
class Drone:
    """Mutable state for one drone during the simulation."""

    identifier: int
    position: str
    path: list[str] = field(default_factory=list[str])
    path_index: int = 0
