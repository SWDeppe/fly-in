"""Thread-safe double buffering for complete Pillow canvases."""

from threading import Lock

from fly_in.graphics.canvas import Canvas


class Buffer:
    """Compose a back canvas and atomically publish it for MLX to display."""

    def __init__(self, width: int, height: int, color: str = "black") -> None:
        self.width = width
        self.height = height
        self._lock = Lock()
        self._front: Canvas | None = None
        self._back = Canvas(width, height, color)
        self._generation = 0

    def clear(self, color: str | tuple[int, ...] = "black") -> None:
        """Clear the back canvas without touching the visible front canvas."""
        with self._lock:
            self._back = Canvas(self.width, self.height, color)

    def load(self, canvas: Canvas, position: tuple[int, int] = (0, 0)) -> None:
        """Load a canvas at a position in the back buffer."""
        with self._lock:
            self._back.paste(canvas, position)

    def publish(self) -> int:
        """Make the complete back canvas visible in one atomic swap."""
        with self._lock:
            self._front, self._back = self._back, self._front
            if self._back is None:
                self._back = Canvas(self.width, self.height)
            self._generation += 1
            return self._generation

    def acquire(self, copy: bool = True) -> tuple[int, Canvas] | None:
        """Read the latest canvas, optionally avoiding a second pixel copy."""
        with self._lock:
            if self._front is None:
                return None
            canvas = self._front.copy() if copy else self._front
            return self._generation, canvas
