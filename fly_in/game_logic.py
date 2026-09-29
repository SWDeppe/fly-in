import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Lock

from PIL import Image

from fly_in.cbs.astar import TimedPath
from fly_in.cbs.solver import CBSSolver
from fly_in.graph import MapData
from fly_in.graphics import Canvas, GraphicsEngine
from fly_in.models import Zone
from fly_in.output import log_output


class GraphicMap:
    """Pixel position of every hub tile on the unscaled base map canvas."""

    def __init__(self,
                 positions: dict[str, tuple[int, int]],
                 tile_size: int) -> None:
        self.positions = positions
        self.tile_size = tile_size

    def hub_at(self, x: float, y: float) -> str | None:
        """Return the hub name whose tile contains base-canvas pixel (x, y)."""
        for name, (px, py) in self.positions.items():
            if (
                px <= x <= px + self.tile_size * 2
                and py <= y <= py + self.tile_size * 2
            ):
                return name
        return None


class GameLogic:
    # X11 keysyms reported by MLX for the arrow keys
    LEFT_KEY = 65361
    UP_KEY = 65362
    RIGHT_KEY = 65363
    DOWN_KEY = 65364
    MOVE_STEP = 40

    ZOOM_STEP = 0.1
    MIN_ZOOM = 0.25
    MAX_ZOOM = 2.0

    MOVE_OFFSET = 100

    # Real seconds per simulated turn
    SIM_TICK_SECONDS = 0.01

    # Drone sprite sheet: this many frames laid out side by side
    DRONE_FRAME_COUNT = 4
    DRONE_ANIMATION_FPS = 6

    def __init__(self, map: MapData, windowSiz: tuple[int, int]) -> None:
        self.map = map
        self.offset = [0, 0]
        self.zoom = 0.5
        self.mouse_pos: tuple[int, int] | None = None
        self.selected_hub: str | None = None
        self.hover_boxes: dict[str, Canvas] = {}
        self._render_lock = Lock()
        self._render_in_flight = False
        self._render_pending = False
        self.paths: dict[int, TimedPath] = {}
        self.sim_time = 0.0
        self._sim_tick = 0
        self.lastMsPos: tuple[int, int]

        self.t = 0
        self.is_arrived = [True for _ in range(map.drone_count)]
        self.drones_dir = ["" for _ in range(map.drone_count)]
        self.movement_count = 0
        self._drone_frame = 0
        self.tiles_t = 0
        self.drones_positions: list[tuple[int, int]] = [
            (0, 0) for _ in range(map.drone_count)
        ]

        self.mouse_down = False
        self.minWidth = None
        self.maxWidth = None
        self.minHeight = None
        self.maxHeight = None
        for zone in map.zones.values():
            if self.minWidth is None or self.minWidth > zone.x:
                self.minWidth = zone.x
            if self.maxWidth is None or self.maxWidth < zone.x:
                self.maxWidth = zone.x

            if self.minHeight is None or self.minHeight > zone.y:
                self.minHeight = zone.y
            if self.maxHeight is None or self.maxHeight < zone.y:
                self.maxHeight = zone.y

        self.windowSiz = windowSiz

    def launch(self) -> None:
        if not hasattr(self, "base_map_canvas"):
            self.make_map()

        with ThreadPoolExecutor(max_workers=4) as executor:
            self._solve_paths(executor)

            if hasattr(self, "graphic_map"):
                base_position = (
                    self.map.zones[self.map.start].x * 2,
                    self.map.zones[self.map.start].y * 2,
                )
                base_canvas_pos = self._tiles_map_positions[base_position[0]][
                    base_position[1]
                ]
                self.drones_positions = [
                    base_canvas_pos for _ in range(self.map.drone_count)
                ]
                self.drones_tile_path: list[list[tuple[int, int]]] = [
                    [] for _ in range(self.map.drone_count)
                ]
            self.executor = executor
            # dashbord = Dashboard()
            self.engine = GraphicsEngine(executor,
                                         *self.windowSiz,
                                         dashboard=None)

            self.engine.submit_canvas(self._compose_view())
            for key in (GraphicsEngine.SCROLL_UP_KEY,
                        GraphicsEngine.SCROLL_DOWN_KEY):
                self.engine.bind_immediate_key(key, self.map_zoom)
            for key in (self.LEFT_KEY, self.RIGHT_KEY):
                self.engine.bind_immediate_key(key, self.advence_t)
            self.engine.bind_mouse(down=self.on_mouse_click,
                                   up=self.on_mouse_click_up)
            self.engine.set_animation(self._advance_simulation)
            self.engine.bind_resize(self.on_resize)
            self.last_e = 0.0
            self.engine.start()

    def advence_t(self, key: int) -> None:
        if False in self.is_arrived:
            return
        self.sim_time = 0
        if key == self.LEFT_KEY and self.t > 0:  # TODO: make it go back
            self.is_arrived = [False for _ in self.is_arrived]
            self.tiles_t = 0
            for i in range(1, self.map.drone_count + 1):
                timed_step = self.paths[i].step_t(self.t)
                s = timed_step.source
                t = timed_step.target
                dur = timed_step.duration
                if (s, t) in self.paths_positions:
                    tile_path = self.paths_positions[(s, t)]
                else:
                    tile_path = list(reversed(self.paths_positions[(t, s)]))

                if dur == 2:
                    if timed_step.start_time == 0:
                        self.drones_tile_path[i - 1] = tile_path[
                            :int(len(tile_path) / 2)
                        ]
                    elif timed_step.start_time == 1:
                        self.drones_tile_path[i - 1] = tile_path[
                            int(len(tile_path) / 2):
                        ]
                else:
                    self.drones_tile_path[i - 1] = tile_path
            self._gen_drones_dir()
            self.t -= 1
            self.movement_count = 0

        elif key == self.RIGHT_KEY and self.t < self.longest_path:
            self.is_arrived = [False for _ in self.is_arrived]
            self.tiles_t = 0
            for i in range(1, self.map.drone_count + 1):
                try:
                    timed_step = self.paths[i].step_t(self.t)
                except IndexError:
                    self.is_arrived[i - 1] = True
                    continue

                s = timed_step.source
                t = timed_step.target
                if s == t:
                    self.is_arrived[i - 1] = True
                    continue
                dur = timed_step.duration

                if (s, t) in self.paths_positions:
                    tile_path = self.paths_positions[(s, t)]
                else:
                    tile_path = list(reversed(self.paths_positions[(t, s)]))

                if dur == 2:
                    if timed_step.start_time == self.t:
                        self.drones_tile_path[i - 1] = tile_path[
                            : int(len(tile_path) / 2)
                        ]
                    else:
                        self.drones_tile_path[i - 1] = tile_path[
                            int(len(tile_path) / 2) - 1:
                        ]
                else:
                    self.drones_tile_path[i - 1] = tile_path
            self._gen_drones_dir()
            self.t += 1
            self.movement_count = 0

    def on_resize(self, width: int, height: int) -> None:
        """Rebuild the view at the new window size
        so it fills the resized buffer."""
        self.windowSiz = (width, height)
        self._request_render()

    def _solve_paths(self, executor: ThreadPoolExecutor) -> None:
        """Compute a conflict-free plan for every
        drone before the window opens."""
        try:
            self.paths = CBSSolver(self.map).solve(executor)
            log_output(
                str(Path(__file__).resolve().parents[1] / "output.txt"),
                [path for path in self.paths.values()]
            )
            self.longest_path: int = max(
                path.arrival_time for path in self.paths.values()
            )
        except ValueError as error:
            print(f"CBS: {error}", flush=True)
            sys.exit()
            self.paths = {}

    def _gen_drones_dir(self) -> None:
        for i in range(self.map.drone_count):
            if self.is_arrived[i]:
                continue
            if len(self.drones_tile_path[i]) <= self.tiles_t + 1:
                self.is_arrived[i] = True
                continue
            if (
                self.drones_tile_path[i][self.tiles_t][0]
                < self.drones_tile_path[i][self.tiles_t + 1][0]
            ):
                self.drones_dir[i] = "S"
            elif (
                self.drones_tile_path[i][self.tiles_t][0]
                > self.drones_tile_path[i][self.tiles_t + 1][0]
            ):
                self.drones_dir[i] = "N"
            elif (
                self.drones_tile_path[i][self.tiles_t][1]
                < self.drones_tile_path[i][self.tiles_t + 1][1]
            ):
                self.drones_dir[i] = "E"
            elif (
                self.drones_tile_path[i][self.tiles_t][1]
                > self.drones_tile_path[i][self.tiles_t + 1][1]
            ):
                self.drones_dir[i] = "W"

    def _advance_simulation(
        self, elapsed: float, width: int, height: int
    ) -> Canvas | None:
        """Step simulated time and request a redraw
        when the turn or drone frame changes."""
        if elapsed - self.last_e > self.SIM_TICK_SECONDS:
            self.movement_count += int((elapsed - self.last_e)
                                       / self.SIM_TICK_SECONDS)
            self.sim_time += 0.02 * int((elapsed - self.last_e)
                                        / self.SIM_TICK_SECONDS)
            self.last_e = elapsed
            self._gen_positions()
            self._compose_view()
            self._request_render()

        if self.movement_count >= int(self.tile_siz / 2):
            self.movement_count = 0
            self.tiles_t += 1

            self._gen_drones_dir()

        return None

    def _request_render(self) -> None:
        """Coalesce render requests: at most one in flight,
        at most one queued behind it."""
        with self._render_lock:
            if self._render_in_flight:
                self._render_pending = True
                return
            self._render_in_flight = True

        # self.engine.get_mouse_pos()
        self.engine.executor.submit(self._render_and_publish)

    def _render_and_publish(self) -> None:
        if self.mouse_down:
            new_pos = self.engine.get_mouse_pos()
            self.offset[0] += new_pos[0] - self.lastMsPos[0]
            if self.offset[0] > int(self.windowSiz[0] / 2):
                self.offset[0] = int(self.windowSiz[0] / 2)
            elif self.offset[0] < -int(self.windowSiz[0] / 2):
                self.offset[0] = -int(self.windowSiz[0] / 2)

            self.offset[1] += new_pos[1] - self.lastMsPos[1]
            if self.offset[1] > int(self.windowSiz[1] / 2):
                self.offset[1] = int(self.windowSiz[1] / 2)

            elif self.offset[1] < -int(self.windowSiz[1] / 2):
                self.offset[1] = -int(self.windowSiz[1] / 2)

            self.lastMsPos = new_pos
        canvas = self._compose_view()
        self.engine.submit_canvas(canvas)
        with self._render_lock:
            rerun = self._render_pending
            self._render_pending = False
            self._render_in_flight = rerun
        if rerun:
            self.engine.executor.submit(self._render_and_publish)

    def on_mouse_click(self, button: int, x: int, y: int) -> None:
        """Show the info box for the clicked hub;
        click it again to close it."""
        if not self.mouse_down:
            self.mouse_down = True
            self.lastMsPos = x, y

        self.mouse_pos = (x, y)
        base_x = (x - self.offset[0]) / self.zoom
        base_y = (y - self.offset[1]) / self.zoom
        hub = self.graphic_map.hub_at(base_x, base_y)
        self.selected_hub = None if hub == self.selected_hub else hub

        # if button == self.LEFT_KEY:
        # self.map_movements(x, y)

        self._request_render()

    def on_mouse_click_up(self, button: int, x: int, y: int) -> None:
        """Show the info box for the clicked hub;
        click it again to close it."""
        self.mouse_down = False

    def map_zoom(self, key: int) -> None:
        """Zoom the map in or out on mouse wheel,
        keeping the viewport center anchored."""
        old_zoom = self.zoom
        if key == GraphicsEngine.SCROLL_UP_KEY:
            self.zoom = min(self.MAX_ZOOM, self.zoom + self.ZOOM_STEP)
        elif key == GraphicsEngine.SCROLL_DOWN_KEY:
            self.zoom = max(self.MIN_ZOOM, self.zoom - self.ZOOM_STEP)

        if self.zoom != old_zoom:
            # Without this, content scales away from the base-canvas origin
            # instead of the point the player is actually looking at.
            center_x = self.windowSiz[0] / 2
            center_y = self.windowSiz[1] / 2
            base_x = (center_x - self.offset[0]) / old_zoom
            base_y = (center_y - self.offset[1]) / old_zoom
            self.offset[0] = int(center_x - base_x * self.zoom)
            self.offset[1] = int(center_y - base_y * self.zoom)

        self._request_render()

    def _compose_view(self) -> Canvas:
        """Crop the visible region of the base map
        and scale only that, at the current zoom/offset."""
        base = self.base_map_canvas.image
        zoom = self.zoom
        off_x, off_y = self.offset

        # Bound the resize to the visible viewport instead of the whole map.
        left = max(0, int(-off_x / zoom))
        top = max(0, int(-off_y / zoom))
        right = min(base.width, int((self.windowSiz[0] - off_x) / zoom) + 1)
        bottom = min(base.height, int((self.windowSiz[1] - off_y) / zoom) + 1)

        view_image = Image.new("RGBA", self.windowSiz, (0, 0, 0, 0))
        if right > left and bottom > top:
            cropped = base.crop((left, top, right, bottom))
            scaled_size = (
                max(1, int(cropped.width * zoom)),
                max(1, int(cropped.height * zoom)),
            )
            scaled = cropped.resize(scaled_size,
                                    Image.Resampling.LANCZOS)
            paste_x = int(left * zoom + off_x)
            paste_y = int(top * zoom + off_y)
            # Image.paste clips out-of-bounds boxes,
            # unlike Canvas.paste's alpha_composite
            view_image.paste(scaled, (paste_x, paste_y), scaled)

        icon = self.drone_frames[
            int(self.sim_time * self.DRONE_ANIMATION_FPS)
            % len(self.drone_frames)
        ]
        same_poses: dict[tuple[int, int], int] = {}
        for base_x, base_y in self.drones_positions:
            im_pos = (
                int((base_x + self.tile_siz / 2) *
                    zoom + off_x - icon.width / 2),
                int((base_y + self.tile_siz / 4) *
                    zoom + off_y - icon.height / 2),
            )
            if im_pos in same_poses:
                same_poses[im_pos] += 1
            else:
                same_poses[im_pos] = 1
            # Image.paste clips safely even when a
            # drone is partly or fully off-screen
            view_image.paste(
                icon,
                im_pos,
                icon,
            )
        view = Canvas.from_image(view_image)

        for pos, value in same_poses.items():
            if value == 1:
                continue
            view.text(
                (int(pos[0] - self.tile_siz / 8),
                 int(pos[1] - self.tile_siz / 8)),
                str(value),
            )

        view.text((self.windowSiz[0] - (10 * len(str(self.t))), 0),
                  str(self.t))

        if self.selected_hub is not None and self.mouse_pos is not None:
            box = self.hover_boxes[self.selected_hub]
            box_x = min(self.mouse_pos[0] + 16,
                        self.windowSiz[0] - box.image.width)
            box_y = min(self.mouse_pos[1] + 16,
                        self.windowSiz[1] - box.image.height)
            view.paste(box, (max(0, box_x), max(0, box_y)))

        return view

    def _zone_center(self, zone_name: str) -> tuple[float, float]:
        """Return the base-canvas pixel center of a zone's tile."""
        px, py = self.graphic_map.positions[zone_name]
        half = self.graphic_map.tile_size / 2
        return (px + half, py + half)

    def _gen_positions(self) -> None:
        """Interpolate each drone's position along
        its path at the current sim time."""
        # positions: list[tuple[float, float]] = []
        for i, path in enumerate(self.drones_tile_path):
            if self.is_arrived[i]:
                continue
            tile_pos = self._tiles_map_positions[path[self.tiles_t][0]][
                path[self.tiles_t][1]
            ]
            match self.drones_dir[i]:
                case "N":
                    self.drones_positions[i] = (
                        tile_pos[0] - self.movement_count,
                        tile_pos[1] - self.movement_count,
                    )
                case "S":
                    self.drones_positions[i] = (
                        tile_pos[0] + self.movement_count,
                        tile_pos[1] + self.movement_count,
                    )
                case "E":
                    self.drones_positions[i] = (
                        tile_pos[0] + self.movement_count,
                        tile_pos[1] - self.movement_count,
                    )
                case "W":
                    self.drones_positions[i] = (
                        tile_pos[0] - self.movement_count,
                        tile_pos[1] + self.movement_count,
                    )
                case _:
                    continue

    def _hover_box(self, zone: Zone) -> Canvas:
        """Build a small black info box describing a hovered hub."""
        lines = [
            zone.name,
            f"type: {zone.zone_type}",
            f"capacity: {zone.capacity}",
            f"pos: ({zone.x}, {zone.y})",
        ]
        line_height = 18
        box = Canvas(160, 12 + line_height * len(lines), (0, 0, 0, 220))
        for index, line in enumerate(lines):
            box.text((8, 6 + index * line_height), line, fill="white")
        return box

    @staticmethod
    def _gen_tiles(is_city: bool, dirs: str) -> list[list[str]]:
        tiles = [["C" if is_city else "", ""], ["", ""]]
        if not is_city and len(dirs) == 1:
            raise ValueError("A tile witout city has just one dir")

        if is_city:
            tiles[0][1] += "W"
            if dirs != "N":
                tiles[0][1] += "S"
                tiles[1][1] += "N"
        if "W" in dirs:
            tiles[1][0] += "EW"
            tiles[1][1] += "W"
        if "N" in dirs:
            if dirs != "N":
                tiles[1][1] += "N"
                tiles[0][1] += "S"
            tiles[0][1] += "N"
        if "E" in dirs:
            tiles[1][1] += "E"
        if "S" in dirs:
            tiles[1][1] += "S"
        return tiles

    @staticmethod
    def _add_path_positions(
        map_path: list[tuple[int, int]],
        path_dirs: list[list[list[str]]],
        # map_pos: tuple[int, int]
    ) -> list[tuple[int, int]]:
        tiles_path: list[
            tuple[int, int]
        ] = [(map_path[0][0] * 2, map_path[0][1] * 2)]
        # curent =
        map_i = 0
        # x, y = [0, 1]
        dirs_pos = [0, 1]
        prev_dir = "W"
        while map_i < len(map_path):
            tiles_path.append(
                (
                    map_path[map_i][0] * 2 + dirs_pos[0],
                    map_path[map_i][1] * 2 + dirs_pos[1],
                )
            )
            curent = path_dirs[map_i][dirs_pos[0]][dirs_pos[1]]
            if curent == "C":
                return tiles_path
            to_ignore = ""
            match prev_dir:
                case "W":
                    to_ignore = "E"
                case "E":
                    to_ignore = "W"
                case "S":
                    to_ignore = "N"
                case "N":
                    to_ignore = "S"
                case _:
                    raise ValueError("Something went wrong")
            prev_dir = curent[0] if curent[1] == to_ignore else curent[1]
            match prev_dir:
                case "W":
                    dirs_pos[1] -= 1
                case "E":
                    dirs_pos[1] += 1
                case "S":
                    dirs_pos[0] += 1
                case "N":
                    dirs_pos[0] -= 1
                case _:
                    raise ValueError("Something went wrong")
            if dirs_pos[0] > 1:
                map_i += 1
                if (len(map_path) > map_i
                   and map_path[map_i - 1][0] > map_path[map_i][0]):
                    raise ValueError("Something went wrong")
                dirs_pos[0] = 0
            if dirs_pos[0] < 0:
                map_i += 1
                if (len(map_path) > map_i
                   and map_path[map_i - 1][0] > map_path[map_i][0]):
                    raise ValueError("Something went wrong")
                dirs_pos[0] = 1
            if dirs_pos[1] > 1:
                map_i += 1
                if (len(map_path) > map_i
                   and map_path[map_i - 1][1] > map_path[map_i][1]):
                    raise ValueError("Something went wrong")
                dirs_pos[1] = 0
            if dirs_pos[1] < 0:
                map_i += 1
                if (len(map_path) > map_i
                   and map_path[map_i - 1][1] < map_path[map_i][1]):
                    raise ValueError("Something went wrong")
                dirs_pos[1] = 1
        return tiles_path

    @staticmethod
    def _add_dirs_to_tile_map(
        dirs: list[list[str]],
        tiles_map: dict[int, dict[int, str]],
        map_pos: tuple[int, int],
    ) -> dict[int, dict[int, str]]:
        tiles_map_pos = (map_pos[0] * 2, map_pos[1] * 2)

        for x in [0, 1]:
            for y in [0, 1]:
                tiles_map[tiles_map_pos[0] + x][
                    tiles_map_pos[1] + y
                ] += dirs[x][y]

        return tiles_map

    def make_map(self) -> None:
        if (
            not isinstance(self.minWidth, int)
            or not isinstance(self.maxWidth, int)
            or not isinstance(self.minHeight, int)
            or not isinstance(self.maxHeight, int)
        ):
            raise TypeError("Something went wrong")
        gridWidth = self.maxWidth + 2 - self.minWidth + 2
        gridHeight = self.maxHeight + 2 - self.minHeight + 2
        self.tile_siz = int(self.windowSiz[0] / 10)
        self.under_offset = int(self.tile_siz / 8)

        # The diamond only spans half of
        # (gridWidth + gridHeight) tiles per axis
        canvas_side = int((gridWidth + gridHeight)
                          * self.tile_siz) + self.tile_siz * 2
        new_canvas = Canvas(canvas_side * 2, canvas_side * 2)
        ground = new_canvas.load_image("includes/routes/grassWhole.png")
        ground = ground.resize_to(self.tile_siz, self.tile_siz)
        tiles: dict[str, Canvas] = {}
        for hub in ["blocked", "normal", "priority", "restricted"]:
            tiles[hub] = new_canvas.load_image("includes/city/" + hub + ".png")
            tiles[hub] = tiles[hub].resize_to(self.tile_siz, self.tile_siz)

        # show the connections
        paths_positions: dict[tuple[str, str],
                              list[tuple[int, int]]] = {}
        tiles_map: dict[int, dict[int, str]] = {
            x: {
                y: ""
                for y in range(
                    self.minHeight * 2,
                    (self.maxHeight - self.minHeight + 1) * 2
                )
            }
            for x in range(self.minWidth * 2,
                           (self.maxWidth - self.minWidth + 1) * 2)
        }

        # each map pos is 4 tiles map pos with the direction of the road
        for connection in self.map.connections:
            pos1, pos2 = [
                (
                    self.map.zones[connection.first].x,
                    self.map.zones[connection.first].y,
                ),
                (
                    self.map.zones[connection.second].x,
                    self.map.zones[connection.second].y,
                ),
            ]

            from_to = [pos1, pos2]
            from_to.sort(key=lambda x: x[0])
            path = [
                (from_to[0][0] + i, from_to[0][1])
                for i in range(from_to[1][0] - from_to[0][0] + 1)
            ]
            if from_to[0][1] <= from_to[1][1]:
                direction = 1
            else:
                direction = -1
            path += [
                (from_to[1][0], from_to[0][1] + i * direction)
                for i in range(1, abs(from_to[0][1] - from_to[1][1]) + 1)
            ]
            paths_positions[(connection.first, connection.second)] = path
            # generate the appropriate tiles

            # make the first tiles
            to_ = path[1]
            from_ = path[0]
            dirs = ""
            if from_[0] > to_[0]:
                dirs = "N"
            elif from_[0] < to_[0]:
                dirs = "S"
            elif from_[1] < to_[1]:
                dirs = "E"
            elif from_[1] > to_[1]:
                dirs = "W"

            all_dirs: list[list[list[str]]] = []
            new_dirs = self._gen_tiles(True, dirs)
            all_dirs.append(new_dirs)
            self._add_dirs_to_tile_map(new_dirs, tiles_map, from_)
            for i in range(1, len(path) - 1):
                from_ = path[i - 1]
                current = path[i]
                to_ = path[i + 1]
                dirs = ""

                # come from
                if from_[0] < current[0]:
                    dirs += "N"
                elif from_[0] > current[0]:
                    dirs += "S"
                elif from_[1] < current[1]:
                    dirs += "W"
                elif from_[1] > current[1]:
                    dirs += "E"

                if to_[0] > current[0]:
                    dirs += "S"
                elif to_[0] < current[0]:
                    dirs += "N"
                elif to_[1] > current[1]:
                    dirs += "E"
                elif to_[1] < current[1]:
                    dirs += "W"

                new_dirs = self._gen_tiles(False, dirs)
                all_dirs.append(new_dirs)
                tiles_map = self._add_dirs_to_tile_map(new_dirs,
                                                       tiles_map,
                                                       current)
            from_ = path[-2]
            to_ = path[-1]

            dirs = ""
            if from_[0] > to_[0]:
                dirs = "S"
            elif from_[0] < to_[0]:
                dirs = "N"
            elif from_[1] < to_[1]:
                dirs = "W"
            elif from_[1] > to_[1]:
                dirs = "E"

            new_dirs = self._gen_tiles(True, dirs)
            all_dirs.append(new_dirs)
            tiles_map = self._add_dirs_to_tile_map(new_dirs, tiles_map, to_)

            paths_positions[(connection.first, connection.second)] = (
                self._add_path_positions(path, all_dirs)
            )
            if from_to != [pos1, pos2]:
                paths_positions[
                    (connection.first, connection.second)
                ].reverse()
            self.paths_positions = paths_positions

        ground_tiles: dict[str, Canvas] = {}
        dirs = "NESW"
        ground = new_canvas.load_image("includes/routes/grass.png")
        ground = ground.resize_to(self.tile_siz,
                                  self.tile_siz + self.under_offset)
        ground_tiles[""] = ground
        ground_tiles["C"] = ground
        for i in range(2, 16):
            if i in [2, 4, 8]:
                continue
            dir = ""
            ni = float(i)
            unit = 8.0
            for y in range(4):
                if ni / unit >= 1:
                    dir += dirs[y]
                    ni %= unit
                unit = unit / 2
            ground_tiles[dir] = Canvas.load_image(
                "includes/routes/" + dir + ".png"
            ).resize_to(self.tile_siz, self.tile_siz + self.under_offset)

        w = len(tiles_map)  # number of columns (x) in the window
        h = len(tiles_map[0])  # number of rows (y) in the window
        start = h * self.tile_siz / 2

        under_map_tile = Canvas.load_image(
            "includes/routes/dirt.png"
            ).resize_to(
            self.tile_siz, self.tile_siz + self.under_offset
        )

        new_start = (int(start + (w - h) * int(self.tile_siz / 2)),
                     int((h + w - 2) *
                         (self.tile_siz - self.under_offset) / 2))
        under_fill = 1000
        for i in range(under_fill):
            for y in range(1, h):
                px = int(new_start[0] + (h - y) * (self.tile_siz) / 2)
                py = int(
                    new_start[1]
                    + self.under_offset * (under_fill - i)
                    - (h - y) * (self.tile_siz - self.under_offset) / 2
                )
                new_canvas.paste(under_map_tile, (px, py))

            for x in range(w):
                px = int(new_start[0] - (w - 1 - x) * ((self.tile_siz) / 2))
                py = int(
                    new_start[1]
                    + self.under_offset * (under_fill - i)
                    - (w - 1 - x) * ((self.tile_siz - self.under_offset) / 2)
                )
                new_canvas.paste(under_map_tile, (px, py))

        self._tiles_map_positions: dict[int, dict[int, tuple[int, int]]] = {
            x: {
                y: (0, 0)
                for y in range(
                    self.minHeight * 2,
                    (self.maxHeight - self.minHeight + 1) * 2
                )
            }
            for x in range(self.minWidth * 2,
                           (self.maxWidth - self.minWidth + 1) * 2)
        }
        for y in range(h):
            for x in range(w):
                px = int(start - (y * self.tile_siz / 2)
                         + (x * self.tile_siz / 2))
                py = int((x + y) * (self.tile_siz - self.under_offset) / 2)
                dirs = tiles_map[x][self.minHeight * 2 + h - y - 1]
                self._tiles_map_positions[x][
                    self.minHeight * 2 + h - y - 1
                ] = (px, py)

                sorted_dirs = ""
                if "N" in dirs:
                    sorted_dirs += "N"
                if "E" in dirs:
                    sorted_dirs += "E"
                if "S" in dirs:
                    sorted_dirs += "S"
                if "W" in dirs:
                    sorted_dirs += "W"
                if "C" in dirs:
                    new_canvas.paste(ground_tiles["C"], (px, py))
                    continue
                if len(dirs) == 1:
                    continue
                new_canvas.paste(ground_tiles[sorted_dirs], (px, py))

        positions: dict[str, tuple[int, int]] = {}
        for zone in self.map.zones.values():
            x = zone.x * 2
            y = h + (self.minHeight * 2 + -zone.y * 2) - 1
            px = int(start - (y * self.tile_siz / 2) + (x * self.tile_siz / 2))
            py = (
                int((x + y) * (self.tile_siz - self.under_offset) / 2)
                - self.under_offset * 2
            )
            position = (px, py)
            new_canvas.paste(tiles[zone.zone_type], position)
            positions[zone.name] = position
            self.hover_boxes[zone.name] = self._hover_box(zone)

        self.graphic_map = GraphicMap(positions, int(self.tile_siz / 2))

        drone_size = max(1, int(self.tile_siz / 4))

        sprite_sheet = new_canvas.load_image(
            "includes/drone/Walk2.png"
            ).resize_to(
            drone_size * self.DRONE_FRAME_COUNT, drone_size
        )
        self.drone_frames = [
            sprite_sheet.image.crop(
                (i * drone_size, 0, (i + 1) * drone_size, drone_size)
            )
            for i in range(self.DRONE_FRAME_COUNT)
        ]

        self.base_map_canvas = new_canvas
