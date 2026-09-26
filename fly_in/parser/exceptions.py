class ParseError(ValueError):
    """Raised when an input map violates the Fly-in format."""
    def __init__(self, message: str, line: int) -> None:
        super().__init__(f"{message} (line: {line})")
