from typing import Any

id = tuple[int, int]


def isId(var: Any):
    if isinstance(var, list) and len(var) == 2:
        return (
            isinstance(var, tuple)
            and isinstance(var[0], int)
            and isinstance(var[1], int)
        )
    else:
        return False


class Node:
    _id: id
    _neigbours: list["Node"]

    def __init__(self, id: id, neigbours: list["Node"]):
        self._id = id
        self._neigbours = neigbours

    def connect(self, node: "Node"):
        if isinstance(node, Node):
            self._neigbours.append(node)
            node._neigbours.append(self)
        else:
            raise TypeError("can juste connect to a Node object")


class Graph:
    _start: Node
    _end: Node
    map: dict[id, Node]

    def __init__(self, start: Node, end: Node):
        self._start = start
        self._end = end
        self.map = {start._id: start, end._id: end}

    def connect_childs(self, parent: id | Node, childs: list[Node] | Node):
        # verify parent is part of map
        lc: list[Node]
        if isinstance(childs, list) and isinstance(childs[0], Node):
            lc = childs
        elif isinstance(childs, Node):
            lc = [childs]
        else:
            raise TypeError("childs muste be: list[id] | id | list[Node] | Node")

        pid: Node
        if isinstance(parent, Node):
            pid = parent._id
        elif isinstance(parent, id):
            pid = parent

        try:
            for node in lc:
                self.map[pid].connect(node)
                if node._id not in self.map:
                    self.map[node._id] = node
        except KeyError:
            raise ValueError("Parent node not registered")

    # TODO: remove that ai generated code
    def __str__(self, width: int = 80, height: int = 24, iterations: int = 300) -> str:
        import math
        import random

        nodes = list(self.map.values())
        ids = [node._id for node in nodes]
        edges = [(node._id, child._id) for node in nodes for child in node._neigbours]

        n = len(ids)
        if n == 0:
            return ""

        # --- run the physics in a normalized 1x1 square, independent of ---
        # --- the terminal's width/height aspect ratio (fixes nodes getting ---
        # --- clamped/jammed against the top/bottom edges) ---
        rng = random.Random(42)
        k = math.sqrt(1.0 / n)
        pos = {node: [rng.uniform(0, 1), rng.uniform(0, 1)] for node in ids}

        edge_set = set()
        for a, b in edges:
            if a != b:
                edge_set.add((a, b) if a <= b else (b, a))

        initial_temperature = 0.1
        temperature = initial_temperature

        for it in range(iterations):
            disp = {node: [0.0, 0.0] for node in ids}

            for i in range(n):
                for j in range(i + 1, n):
                    u, v = ids[i], ids[j]
                    dx = pos[u][0] - pos[v][0]
                    dy = pos[u][1] - pos[v][1]
                    dist = math.sqrt(dx * dx + dy * dy) or 0.001
                    force = (k * k) / dist
                    fx, fy = (dx / dist) * force, (dy / dist) * force
                    disp[u][0] += fx
                    disp[u][1] += fy
                    disp[v][0] -= fx
                    disp[v][1] -= fy

            for a, b in edge_set:
                dx = pos[a][0] - pos[b][0]
                dy = pos[a][1] - pos[b][1]
                dist = math.sqrt(dx * dx + dy * dy) or 0.001
                force = (dist * dist) / k
                fx, fy = (dx / dist) * force, (dy / dist) * force
                disp[a][0] -= fx
                disp[a][1] -= fy
                disp[b][0] += fx
                disp[b][1] += fy

            for node in ids:
                dx, dy = disp[node]
                dist = math.sqrt(dx * dx + dy * dy) or 0.001
                capped = min(dist, temperature)
                pos[node][0] = min(
                    1.0,
                    max(0.0, pos[node][0] + (dx / dist) * capped)
                )
                pos[node][1] = min(
                        1.0,
                        max(0.0, pos[node][1] + (dy / dist) * capped)
                )

            # FIX: recompute from the original temperature each iteration
            # (linear cooling), instead of compounding a shrink factor every
            # step (which decayed geometrically and froze solid by ~iter 90).
            temperature = initial_temperature * (1 - (it + 1) / iterations)

        # --- map normalized positions onto the actual character grid ---
        # (small margin so labels don't get clipped at the edges)
        margin_x, margin_y = 4, 1
        scaled = {
            node: (
                margin_x + x * (width - 2 * margin_x),
                margin_y + y * (height - 2 * margin_y),
            )
            for node, (x, y) in pos.items()
        }

        grid = [[" " for _ in range(width)] for _ in range(height)]

        def put(x, y, ch):
            x, y = round(x), round(y)
            if 0 <= y < height and 0 <= x < width:
                grid[y][x] = ch

        def draw_line(p1, p2):
            x1, y1 = p1
            x2, y2 = p2
            steps = int(max(abs(x2 - x1), abs(y2 - y1))) or 1
            for s in range(steps + 1):
                t = s / steps
                put(x1 + (x2 - x1) * t, y1 + (y2 - y1) * t, ".")

        for a, b in edges:
            if a != b:
                draw_line(scaled[a], scaled[b])

        for node in ids:
            x, y = scaled[node]
            label = f"[{node}]"
            if node == self._start._id:
                label = f"*{node}*"
            elif node == self._end._id:
                label = f"({node})"
            start_x = round(x) - len(label) // 2
            for i, ch in enumerate(label):
                put(start_x + i, y, ch)

        return "\n".join("".join(row) for row in grid)


def parse(file_name: str):
    
    with open(file_name) as f:
        for line in f.readlines():
            


def main():
    parse("./text")
    nodes = [
        Node((2, 2), []),
        Node((5, 2), []),
        Node((3, 2), []),
        Node((4, 2), []),
        Node((5, 6), []),
    ]

    graph = Graph(nodes[0], nodes[4])
    graph.connect_childs(nodes[0], [nodes[3], nodes[1], nodes[2]])
    graph.connect_childs(nodes[4], [nodes[2], nodes[0], nodes[3], nodes[1]])
    graph.connect_childs(nodes[2], [nodes[1], nodes[3]])

    print(graph)


if __name__ == "__main__":
    main()
