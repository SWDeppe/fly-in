from __future__ import annotations

from dataclasses import dataclass, field
from .VCanvas import Canvas


@dataclass
class Framebuffer:
    """A frame buffer containing one or several canvases."""

    name: str
    canvases: dict[str, Canvas] = field(default_factory=dict)

    def add_canvas(self, canvas: Canvas) -> None:
        self.canvases[canvas.name] = canvas

    def get_canvas(self, name: str) -> Canvas:
        return self.canvases[name]

    def copy_from(self, other: "Framebuffer") -> None:
        for name, canvas in other.canvases.items():
            self.canvases.setdefault(name, Canvas(None,
                                                  None,
                                                  width=canvas.width,
                                                  height=canvas.height,
                                                  name=name))
            self.canvases[name].pil_image = canvas.pil_image.copy()

    def clear(self) -> None:
        for canvas in self.canvases.values():
            canvas.clear()
