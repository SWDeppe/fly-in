"""Behavior tests for the high-level conflict-based search."""

from concurrent.futures import ThreadPoolExecutor

from fly_in.cbs.astar import ConstrainedAStar
from fly_in.cbs.conflicts import ConflictKind, Constraint
from fly_in.cbs.solver import CBSSolver
from fly_in.graph import StaticGraph
from fly_in.models import Connection, MapData, Zone


def make_line_map(drone_count: int = 2) -> MapData:
    zones = {
        "start": Zone("start", 0, 0),
        "middle": Zone("middle", 1, 0),
        "end": Zone("end", 2, 0),
    }
    return MapData(
        drone_count,
        "start",
        "end",
        zones,
        [Connection("start", "middle"), Connection("middle", "end")],
    )


def test_detect_conflicts_ignores_shared_start_and_end() -> None:
    solver = CBSSolver(make_line_map())

    with ThreadPoolExecutor(max_workers=2) as executor:
        paths = solver.initial_paths(executor)

    conflicts = solver.detect_conflicts(paths)
    assert any(conflict.kind is ConflictKind.VERTEX for conflict in conflicts)
    assert all(
        conflict.location != ("start",) for conflict in conflicts
    )


def test_solve_returns_conflict_free_best_score() -> None:
    solver = CBSSolver(make_line_map())

    with ThreadPoolExecutor(max_workers=2) as executor:
        paths = solver.solve(executor)

    assert max(path.arrival_time for path in paths.values()) == 3
    assert {path.arrival_time for path in paths.values()} == {2, 3}
    assert solver.detect_conflicts(paths) == ()


def test_constrained_search_uses_detour_before_waiting() -> None:
    zones = {
        "start": Zone("start", 0, 0),
        "junction": Zone("junction", 1, 0),
        "detour": Zone("detour", 1, 1),
        "end": Zone("end", 2, 0),
    }
    map_data = MapData(
        1,
        "start",
        "end",
        zones,
        [
            Connection("start", "junction"),
            Connection("junction", "end"),
            Connection("start", "detour"),
            Connection("detour", "end"),
        ],
    )
    astar = ConstrainedAStar(StaticGraph(map_data))

    path = astar.search(
        1,
        "start",
        "end",
        frozenset({Constraint(1, ConflictKind.VERTEX, ("junction",), 1)}),
    )

    assert path.wait_count == 0
    assert [step.target for step in path.steps] == ["detour", "end"]

def test_bonus_requirements():
    from fly_in.parser import Parser

    max_steps = {
        "easy/01_linear_path.txt": 6, 
        "easy/02_simple_fork.txt": 6, 
        "easy/03_basic_capacity.txt": 8, 
        "medium/01_dead_end_trap.txt": 15, 
        "medium/02_circular_loop.txt": 20,
        "medium/03_priority_puzzle.txt": 12, 
        "hard/01_maze_nightmare.txt": 45, 
        "hard/02_capacity_hell.txt": 60, 
        "hard/03_ultimate_challenge.txt": 35, 
        "challenger/01_the_impossible_dream.txt": 45, 
    }

    for map_file, max_steps in max_steps.items():
        map = Parser.parse("maps/" + map_file)
        
        solver = CBSSolver(map)
    
        with ThreadPoolExecutor(max_workers=20) as executor:
            paths = solver.solve(executor)


        used = max(path.arrival_time + 1 for path in paths.values())
        print(f"{map_file}: {used}/{max_steps} steps")
        assert used <= max_steps


# test_bonus_requirements()