import inspect
import io
import linecache
import tokenize
from types import FrameType
from typing import Any


class VEngineError(Exception):
    errors: list[dict[str, Any]] = []

    def __init__(
        self,
        message: str,
        *,
        line: int | None = None,
        col: int | None = None,
        file: str | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message

        caller_frame: FrameType | None = inspect.currentframe()
        if caller_frame is not None and caller_frame.f_back is not None:
            caller = caller_frame.f_back
            if file is None:
                file = caller.f_code.co_filename
            if line is None:
                line = caller.f_lineno
            if col is None:
                col = self._infer_column(caller)
        else:
            file = file or "<unknown>"
            line = line if line is not None else -1
            col = col if col is not None else -1

        error: dict[str, Any] = {
            "line": line if line is not None else -1,
            "col": col if col is not None else -1,
            "file": file or "<unknown>",
            "msg": message,
        }
        self.error = error
        self.register(error)

    @staticmethod
    def _infer_column(frame: FrameType) -> int:
        try:
            source_line = linecache.getline(
                frame.f_code.co_filename, frame.f_lineno
            )
        except Exception:
            return -1

        if not source_line:
            return -1

        try:
            tokens = tokenize.generate_tokens(
                io.StringIO(source_line).readline
            )
            for token in tokens:
                if token.start[0] == 1:
                    return token.start[1]
        except (tokenize.TokenError, IndentationError):
            pass

        return -1

    def __str__(self) -> str:
        return self.message

    @classmethod
    def register(cls, error: dict[str, Any]) -> None:
        cls.errors.append(error)

    @classmethod
    def get_errors(cls) -> list[dict[str, Any]]:
        return list(cls.errors)

    @classmethod
    def clear_errors(cls) -> None:
        cls.errors.clear()

    @classmethod
    def format_errors(cls) -> str:
        if not cls.errors:
            return "No errors recorded."

        lines = []
        for index, error in enumerate(cls.errors, start=1):
            location = (
                f"{error['file']}:{error['line']}:{error['col']}"
            )
            lines.append(f"{index}. {location} - {error['msg']}")
        return "\n".join(lines)


class StopCall(Exception):
    """Raised by event callbacks to indicate they should be removed."""
