from __future__ import annotations

import threading
from pathlib import Path
from typing import Any

from visual_engine import VEngine

from src.parsing.parser import Parsing


class MapRuntime:
    def __init__(self, map_path: str | Path) -> None:
        self.map_path = Path(map_path)
        self.parser = Parsing()
        self._stop_event = threading.Event()
        self._lock = threading.Lock()
        self._framebuffers: dict[str, dict[str, Any]] = {}

    def run(self) -> None:
        data = parse_map_file(self.map_path)
        self._framebuffers = build_framebuffers(data)
        self._start_workers()

    def _start_workers(self) -> None:
        threads = []
        for name, worker in self._build_workers().items():
            thread = threading.Thread(target=worker, daemon=True, name=name)
            thread.start()
            threads.append(thread)
        for thread in threads:
            thread.join(timeout=0.2)

    def _build_workers(self) -> dict[str, Any]:
        return {
            "parse": lambda: self._parse_worker(),
            "render": lambda: self._render_worker(),
        }

    def _parse_worker(self) -> None:
        if self._stop_event.is_set():
            return
        data = parse_map_file(self.map_path)
        with self._lock:
            self._framebuffers = build_framebuffers(data)

    def _render_worker(self) -> None:
        if self._stop_event.is_set():
            return
        with self._lock:
            payload = self._framebuffers.copy()
        if not payload:
            return
        draw_framebuffers(payload)


def parse_map_file(map_path: str | Path) -> dict[str, Any]:
    parser = Parsing()
    return parser.parse_file(map_path)


def build_framebuffers(
    data: dict[str, Any], width: int = 800, height: int = 600
) -> dict[str, dict[str, Any]]:
    hubs = data.get("hubs", {})
    return {
        "primary": {
            "width": width,
            "height": height,
            "hub_count": len(hubs),
            "data": data,
        },
        "back": {
            "width": width,
            "height": height,
            "hub_count": len(hubs),
            "data": data,
        },
    }


def draw_framebuffers(framebuffers: dict[str, dict[str, Any]]) -> None:
    for name, framebuffer in framebuffers.items():
        print(f"rendering {name} with {framebuffer['hub_count']} hubs")


def _render_framebuffer_to_canvas(framebuffer_name: str, payload: dict[str, Any]) -> None:
    if VEngine.context is None:
        return

    framebuffer = VEngine.context.framebuffers[framebuffer_name]
    canvas = framebuffer.get_canvas("main")
    canvas.clear()
    canvas.draw_text(
        f"{framebuffer_name} :: drones={payload['data'].get('nb_drones', 0)}",
        (8, 8),
        size=16,
        color=(255, 255, 255, 255),
    )

    for hub_name, hub in payload["data"].get("hubs", {}).items():
        position = hub.get("position", [0, 0])
        canvas.draw_text(hub_name, (position[0] + 10, position[1] + 10), size=12)

    if VEngine.context.window is not None:
        VEngine.put_framebuffer(framebuffer_name)


def run_runtime(
    map_path: str | Path,
    *,
    width: int = 800,
    height: int = 600,
    create_window: bool = False,
) -> dict[str, Any]:
    framebuffers = prepare_window(
        map_path, width=width, height=height, create_window=create_window
    )
    primary = render_framebuffer_from_data(
        "primary", framebuffers, create_window=create_window
    )
    back = render_framebuffer_from_data(
        "back", framebuffers, create_window=create_window
    )
    return {"framebuffers": framebuffers, "primary": primary, "back": back}


def prepare_window(
    map_path: str | Path,
    *,
    width: int = 800,
    height: int = 600,
    create_window: bool = False,
) -> dict[str, Any]:
    data = parse_map_file(map_path)
    VEngine.load((width, height), create_window=create_window)
    return build_framebuffers(data, width=width, height=height)


def render_framebuffer_from_data(
    framebuffer_name: str, data: dict[str, Any], *, create_window: bool = False
) -> dict[str, Any]:
    if VEngine.context is None:
        VEngine.load(
            (data["primary"]["width"], data["primary"]["height"]),
            create_window=create_window,
        )

    payload = {
        "framebuffer": framebuffer_name,
        "hub_count": data[framebuffer_name]["hub_count"],
        "width": data[framebuffer_name]["width"],
        "height": data[framebuffer_name]["height"],
        "data": data[framebuffer_name]["data"],
    }
    _render_framebuffer_to_canvas(framebuffer_name, payload)
    return payload


def launch_visualizer() -> None:
    if VEngine.context is not None:
        VEngine.launch()
