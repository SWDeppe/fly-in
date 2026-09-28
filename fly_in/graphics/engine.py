"""MLX adapter that keeps all potentially slow work out of callbacks."""

import time
from concurrent.futures import Executor
from typing import Any, Callable

from fly_in.graphics.buffer import Buffer
from fly_in.graphics.canvas import Canvas
from fly_in.graphics.dashboard import Dashboard
from fly_in.graphics.event_manager import EventManager, EventResult


class GraphicsEngine:
    """Own the MLX loop while workers prepare complete Pillow canvases."""

    ESCAPE_KEY = 65307
    # X11 button codes reported by mlx_mouse_hook for the scroll wheel
    SCROLL_UP_BUTTON = 4
    SCROLL_DOWN_BUTTON = 5
    # Pseudo keys used to route scroll events through the key handler pipeline
    SCROLL_UP_KEY = -1
    SCROLL_DOWN_KEY = -2
    # X11 event code/mask for pointer motion
    MOTION_EVENT = 6
    POINTER_MOTION_MASK = 1 << 6

    def __init__(
        self,
        executor: Executor,
        width: int = 1200,
        height: int = 800,
        resize_debounce: float = 0.2,
        dashboard: Dashboard | None = None,
    ) -> None:
        self.executor = executor
        self.buffer = Buffer(width, height)
        self.events = EventManager(executor)
        self.width = width
        self.height = height
        self._mlx: Any = None
        self._mlx_ptr: Any = None
        self._window: Any = None
        self._image: Any = None
        self._last_generation = 0
        self._stopped = False
        self._animation: Callable[[float, int, int],
                                  Canvas | None] | None = None
        self._started_at = 0.0
        self._title = "Fly-in"
        self._overlay: Canvas | None = None
        self._resize_debounce = resize_debounce
        self._pending_size: tuple[int, int] | None = None
        self._resize_seen_at = 0.0
        self.dashboard = dashboard
        self._frame_count = 0
        self._fps_started_at = 0.0
        self._mouse_down: Callable[[int, int, int], None] | None = None
        self._mouse_up: Callable[[int, int, int], None] | None = None
        self._mouse_move: Callable[[int, int], None] | None = None
        self._mouse_move_min_interval = 1.0 / 30.0
        self._last_mouse_move_at = 0.0
        self._animation_owns_scene = False
        self._immediate_handlers: dict[int, Callable[[int], None]] = {}
        self._resize_handler: Callable[[int, int], None] | None = None
        # Cap the expensive MLX blit; mlx_loop_hook can
        # fire far faster than any display refresh.
        self._min_frame_interval = 1.0 / 60.0
        self._last_frame_at = 0.0

    def get_mouse_pos(self) -> tuple[int, int]:
        _, x, y = self._mlx.mlx_mouse_get_pos(self._mlx_ptr, self._window)
        # print("Mouse pos returns",_, x, y)
        return (x, y)

    def bind_key(self,
                 key: int,
                 handler: Callable[[int], Canvas | None]) -> None:
        """Register a worker handler; its Canvas result is published later."""
        self.events.bind(key, handler)
        if self.dashboard is not None:
            self.dashboard.message(f"bind key {key} -> {handler.__name__}")

    def bind_immediate_key(self,
                           key: int,
                           handler: Callable[[int], None]) -> None:
        """Register a handler run synchronously in the MLX callback.

        Unlike ``bind_key``, this bypasses the executor queue entirely, so a
        burst of repeated presses can never pile up unfinished work that
        blocks shutdown. The handler must be fast and non-blocking (e.g. plain
        state mutation), not do any rendering itself.
        """
        self._immediate_handlers[key] = handler

    def bind_resize(self, handler: Callable[[int, int], None]) -> None:
        """Register a callback invoked with the new (width, height)
        after a resize.

        Without this, a consumer's overlay keeps the old size while the
        window (and buffer) grow/shrink, leaving a black border where the
        stale-sized content no longer fills the new background.
        """
        self._resize_handler = handler

    def set_animation(
        self,
        animation: Callable[[float, int, int], Canvas | None],
        owns_scene: bool = False,
    ) -> None:
        """Register a short render callback called once per MLX loop tick."""
        self._animation = animation
        self._animation_owns_scene = owns_scene

    def bind_mouse(
        self,
        down: Callable[[int, int, int], None] | None = None,
        up: Callable[[int, int, int], None] | None = None,
        move: Callable[[int, int], None] | None = None,
        move_max_rate: float = 30.0,
    ) -> None:
        """Register non-blocking mouse callbacks for pan and drag actions.

        ``move_max_rate`` caps ``move`` to at most that many calls per second,
        since raw X11 PointerMotionMask events can fire far more often (rate
        depends on the device, not on anything we control) than any handler
        needs.
        """
        self._mouse_down = down
        self._mouse_up = up
        self._mouse_move = move
        self._mouse_move_min_interval = 1.0 / max(1.0, move_max_rate)
        self._last_mouse_move_at = 0.0

    def submit_canvas(self,
                      canvas: Canvas,
                      position: tuple[int, int] = (0, 0)) -> None:
        """Compose a completed worker result into the back buffer."""
        self._overlay = canvas.copy()
        self._publish_scene()

    def _publish_scene(self, background: Canvas | None = None) -> None:
        """Publish the animated background with the latest event result."""
        canvas = background
        if canvas is None:
            canvas = Canvas(self.width, self.height)
        if canvas.image.size != (self.width, self.height):
            fitted = Canvas(self.width, self.height)
            fitted.paste(canvas, (0, 0))
            canvas = fitted
        if self._overlay is not None and not self._animation_owns_scene:
            overlay = self._overlay
            if overlay.image.size != (self.width, self.height):
                fitted = Canvas(self.width, self.height)
                fitted.paste(overlay, (0, 0))
                overlay = fitted
            canvas.paste(overlay, (0, 0))
        self.buffer.load(canvas)
        self.buffer.publish()

    def _set_overlay(self, canvas: Canvas) -> None:
        """Keep an event result visible across animated frames."""
        self._overlay = canvas.copy()
        self._publish_scene()

    def _submit_worker_canvas(
        self, canvas: Canvas, position: tuple[int, int] = (0, 0)
    ) -> None:
        """Store a worker canvas without letting animation erase it."""
        if (canvas.image.size != (self.width, self.height)
           or position != (0, 0)):
            fitted = Canvas(self.width, self.height)
            fitted.paste(canvas, position)
            canvas = fitted
        self._set_overlay(canvas)

    def start(self, mlx: Any = None, title: str = "Fly-in") -> None:
        """Start MLX; every callback performs bounded, non-blocking work."""
        if mlx is None:
            from mlx import Mlx  # pyright: ignore[reportMissingTypeStubs]

            mlx = Mlx()
        self._mlx = mlx
        self._title = title
        self._started_at = time.monotonic()
        self._fps_started_at = self._started_at
        if self.dashboard is not None:
            self.dashboard.start()
            self.dashboard.message("MLX loop starting", "green")
        self._mlx_ptr = mlx.mlx_init()
        if not self._mlx_ptr:
            raise RuntimeError("mlx_init failed")
        self._create_window()
        mlx.mlx_loop_hook(self._mlx_ptr, self._on_loop, None)
        try:
            mlx.mlx_loop(self._mlx_ptr)
        finally:
            if self._image is not None:
                mlx.mlx_destroy_image(self._mlx_ptr, self._image)
            if self._window is not None:
                mlx.mlx_destroy_window(self._mlx_ptr, self._window)
            self._image = None
            self._window = None
            self._mlx_ptr = None
            if self.dashboard is not None:
                self.dashboard.message("MLX loop stopped", "yellow")
                self.dashboard.stop()

    def stop(self) -> None:
        """Leave the MLX loop without waiting for worker tasks."""
        self._stopped = True
        if self._mlx is not None and self._mlx_ptr is not None:
            self._mlx.mlx_loop_exit(self._mlx_ptr)

    def _on_key(self, key: int, _param: Any) -> None:
        print(key)
        if key == self.ESCAPE_KEY:
            print("Escape pressed: closing Fly-in", flush=True)
            self.stop()
            return
        self._dispatch(key)

    def _dispatch(self, key: int) -> None:
        """Route a key to its immediate handler,
        or queue it on the executor."""
        immediate = self._immediate_handlers.get(key)
        if immediate is not None:
            immediate(key)
            return
        if self.dashboard is not None:
            self.dashboard.message(f"key {key} submitted as task", "blue")
        self.events.receive(key)

    def _on_close(self, _param: Any) -> None:
        print("Window close requested: closing Fly-in", flush=True)
        self.stop()

    def _on_loop(self, _param: Any) -> None:
        tick_started = time.perf_counter()
        if self._stopped:
            return
        try:
            if not self._sync_window_size():
                return
            if self._animation is not None:
                animated = self._animation(
                    time.monotonic() - self._started_at,
                    self.width,
                    self.height,
                )
                if animated is not None:
                    self._publish_scene(animated)
            for result in self.events.poll():
                self._consume_event(result)
            current = self.buffer.acquire(copy=False)
            if current is not None and current[0] != self._last_generation:
                now = time.monotonic()
                if now - self._last_frame_at >= self._min_frame_interval:
                    self._copy_to_mlx(current[1])
                    self._last_generation = current[0]
                    self._last_frame_at = now
        except BaseException as error:
            if self.dashboard is not None:
                self.dashboard.task_done("loop callback", error)
            raise
        finally:
            self._frame_count += 1
            elapsed = time.perf_counter() - tick_started
            total = time.monotonic() - self._fps_started_at
            fps = self._frame_count / total if total > 0 else 0.0
            if self.dashboard is not None:
                self.dashboard.tick(elapsed, fps)
                self.dashboard.state(
                    self.events.pending,
                    self._last_generation,
                    self.width,
                    self.height,
                )

    def _sync_window_size(self) -> bool:
        result, width, height = self._mlx.mlx_get_window_size(
            self._mlx_ptr, self._window
        )
        if result != 0 or (width, height) == (self.width, self.height):
            self._pending_size = None
            return True
        size = (width, height)
        now = time.monotonic()
        if self._pending_size != size:
            self._pending_size = size
            self._resize_seen_at = now
            return False
        if now - self._resize_seen_at < self._resize_debounce:
            return False
        self._recreate_window(width, height)
        self._pending_size = None
        return True

    def _create_window(self) -> None:
        self._window = self._mlx.mlx_new_window(
            self._mlx_ptr, self.width, self.height, self._title
        )
        if self._window is None:
            raise RuntimeError("mlx_new_window failed")
        self._image = self._mlx.mlx_new_image(self._mlx_ptr,
                                              self.width,
                                              self.height)
        if self._image is None:
            raise RuntimeError("mlx_new_image failed")
        self._mlx.mlx_key_hook(self._window, self._on_key, None)
        self._mlx.mlx_mouse_hook(self._window, self._on_mouse_button, None)
        if self._mouse_move is not None:
            # Only register PointerMotionMask when something needs it: every
            # tiny mouse move is otherwise a C->Python callback for nothing.
            self._mlx.mlx_hook(
                self._window,
                self.MOTION_EVENT,
                self.POINTER_MOTION_MASK,
                self._on_mouse_move,
                None,
            )
        self._mlx.mlx_hook(self._window, 33, 0, self._on_close, None)
        self._mlx.mlx_hook(self._window, 5, 1 << 3, self._on_mouse_up, None)

    def _on_mouse_button(self,
                         button: int,
                         x: int,
                         y: int,
                         _param: Any) -> None:
        if button == self.SCROLL_UP_BUTTON:
            self._dispatch(self.SCROLL_UP_KEY)
        elif button == self.SCROLL_DOWN_BUTTON:
            self._dispatch(self.SCROLL_DOWN_KEY)
        elif self._mouse_down is not None:
            self._mouse_down(button, x, y)

    def _on_mouse_up(self, button: int, x: int, y: int, _param: Any) -> None:
        if self._mouse_up is not None:
            self._mouse_up(button, x, y)

    def _on_mouse_move(self, x: int, y: int, _param: Any) -> None:
        if self._mouse_move is None:
            return
        now = time.monotonic()
        if now - self._last_mouse_move_at < self._mouse_move_min_interval:
            return
        self._last_mouse_move_at = now
        self._mouse_move(x, y)

    def _recreate_window(self, width: int, height: int) -> None:
        if self._image is not None:
            self._mlx.mlx_destroy_image(self._mlx_ptr, self._image)
        if self._window is not None:
            self._mlx.mlx_destroy_window(self._mlx_ptr, self._window)
        self.width = width
        self.height = height
        self.buffer = Buffer(width, height)
        self._create_window()
        self._last_generation = 0
        if self._resize_handler is not None:
            self._resize_handler(width, height)

    def _consume_event(self, result: EventResult) -> None:
        if result.error is not None:
            if self.dashboard is not None:
                self.dashboard.task_done(f"key {result.key}", result.error)
            raise result.error
        if self.dashboard is not None:
            self.dashboard.task_done(f"key {result.key}")
        if isinstance(result.value, Canvas) and not self._animation_owns_scene:
            self._submit_worker_canvas(result.value)

    def _copy_to_mlx(self, canvas: Canvas) -> None:
        data_addr = self._mlx.mlx_get_data_addr(self._image)
        data, bits_per_pixel, size_line, _ = data_addr
        if bits_per_pixel != 32:
            raise RuntimeError("MLX image must use 32 bits per pixel")
        pixels = canvas.mlx_bytes()
        row_size = self.width * 4
        if size_line == row_size:
            # No row padding: one bulk copy instead of a per-row Python loop.
            data[: row_size * self.height] = pixels
        else:
            for row in range(self.height):
                start = row * row_size
                destination = row * size_line
                data[destination: destination + row_size] = pixels[
                    start: start + row_size
                ]
        self._mlx.mlx_put_image_to_window(
            self._mlx_ptr, self._window, self._image, 0, 0
        )
