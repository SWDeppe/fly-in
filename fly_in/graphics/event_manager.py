"""Non-blocking keyboard event dispatch for the MLX loop."""

from concurrent.futures import Executor, Future
from dataclasses import dataclass
from queue import Empty, Queue
from threading import Lock
from typing import Any, Callable


@dataclass(frozen=True)
class EventResult:
    """Result mailbox entry produced after an event handler completes."""

    key: int
    value: Any = None
    error: BaseException | None = None


class EventManager:
    """Receive MLX keys quickly and execute handlers outside MLX callbacks."""

    def __init__(self, executor: Executor) -> None:
        self._executor = executor
        self._handlers: dict[int, Callable[[int], Any]] = {}
        self._completed: Queue[EventResult] = Queue()
        self._lock = Lock()
        self._pending = 0

    def bind(self, key: int, handler: Callable[[int], Any]) -> None:
        """Associate a key with work that may take time."""
        self._handlers[key] = handler

    def receive(self, key: int) -> None:
        """Enqueue a key and return immediately from the MLX callback."""
        handler = self._handlers.get(key)
        if handler is None:
            return
        with self._lock:
            self._pending += 1
        future = self._executor.submit(handler, key)
        future.add_done_callback(lambda done: self._finish(key, done))

    def poll(self) -> list[EventResult]:
        """Drain completed handlers without waiting for unfinished work."""
        results: list[EventResult] = []
        while True:
            try:
                results.append(self._completed.get_nowait())
            except Empty:
                return results

    @property
    def pending(self) -> int:
        """Return the number of event handlers still running."""
        with self._lock:
            return self._pending

    def _finish(self, key: int, future: Future[Any]) -> None:
        try:
            result = EventResult(key, value=future.result())
        except BaseException as error:
            result = EventResult(key, error=error)
        with self._lock:
            self._pending -= 1
        self._completed.put(result)
