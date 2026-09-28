"""Low-overhead terminal dashboard for the graphics loop."""

from collections import deque
from dataclasses import dataclass
import sys
from threading import Event, Lock, Thread
from typing import Deque

try:
    from colored import attr, fg
except ImportError:  # pragma: no cover
    def fg(_color: str) -> str:
        """Keep the dashboard usable when colored is not installed."""
        return ""

    def attr(_name: str) -> str:
        """Keep the dashboard usable when colored is not installed."""
        return ""


@dataclass(frozen=True)
class DashboardSnapshot:
    fps: float
    tick_ms: float
    max_tick_ms: float
    pending: int
    completed: int
    failed: int
    generation: int
    width: int
    height: int
    messages: tuple[str, ...]


class Dashboard:
    """Render live graphics metrics without writing from the MLX callback."""

    def __init__(self, refresh: float = 0.5, message_limit: int = 12) -> None:
        self.refresh = refresh
        self._messages: Deque[str] = deque(maxlen=message_limit)
        self._lock = Lock()
        self._stop = Event()
        self._thread: Thread | None = None
        self._fps = 0.0
        self._tick_ms = 0.0
        self._max_tick_ms = 0.0
        self._pending = 0
        self._completed = 0
        self._failed = 0
        self._generation = 0
        self._width = 0
        self._height = 0

    def start(self) -> None:
        """Start the dashboard printer in a daemon thread."""
        if self._thread is not None and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = Thread(
            target=self._run, name="graphics-dashboard", daemon=True
        )
        self._thread.start()

    def stop(self) -> None:
        """Stop printing and leave the terminal in a usable state."""
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=max(self.refresh * 2, 0.1))
        sys.stdout.write("\033[0m\033[?25h\n")
        sys.stdout.flush()

    def tick(self, duration: float, fps: float) -> None:
        """Record one MLX loop tick."""
        with self._lock:
            self._tick_ms = duration * 1000
            self._max_tick_ms = max(self._max_tick_ms, self._tick_ms)
            self._fps = fps

    def state(
        self, pending: int, generation: int, width: int, height: int
    ) -> None:
        """Update current graphics state."""
        with self._lock:
            self._pending = pending
            self._generation = generation
            self._width = width
            self._height = height

    def task_done(
        self, message: str, error: BaseException | None = None
    ) -> None:
        """Record a worker completion or failure."""
        with self._lock:
            if error is None:
                self._completed += 1
                color = fg("green")
                self._messages.append(f"{color}OK{attr('reset')} {message}")
            else:
                self._failed += 1
                color = fg("red")
                self._messages.append(
                    f"{color}ERR{attr('reset')} {message}: {error}"
                )

    def message(self, message: str, color: str = "cyan") -> None:
        """Add a bounded informational message."""
        with self._lock:
            self._messages.append(f"{fg(color)}..{attr('reset')} {message}")

    def snapshot(self) -> DashboardSnapshot:
        """Copy metrics atomically for terminal rendering."""
        with self._lock:
            return DashboardSnapshot(
                self._fps,
                self._tick_ms,
                self._max_tick_ms,
                self._pending,
                self._completed,
                self._failed,
                self._generation,
                self._width,
                self._height,
                tuple(self._messages),
            )

    def _run(self) -> None:
        sys.stdout.write("\033[?25l")
        while not self._stop.wait(self.refresh):
            self._render(self.snapshot())

    @staticmethod
    def _render(snapshot: DashboardSnapshot) -> None:
        lines = [
            f"{fg('yellow')}FLY-IN GRAPHICS DASHBOARD{attr('reset')}",
            f"FPS {snapshot.fps:6.1f} | tick {snapshot.tick_ms:7.2f} ms | "
            f"max {snapshot.max_tick_ms:7.2f} ms",
            f"window {snapshot.width}x{snapshot.height} | buffer generation "
            f"{snapshot.generation} | tasks pending {snapshot.pending}",
            f"tasks completed {snapshot.completed} | failed {snapshot.failed}",
            "messages:",
        ]
        lines.extend(f"  {message}" for message in snapshot.messages)
        sys.stdout.write("\033[H\033[2J" + "\n".join(lines) + "\n")
        sys.stdout.flush()
