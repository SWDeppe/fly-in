"""Pillow canvases used as complete render snapshots."""

from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFont


class Canvas:
    """An RGBA image that can be composed before being published."""

    def __init__(
        self, width: int, height: int, color: str | tuple[int, ...] = "black"
    ) -> None:
        if width < 1 or height < 1:
            raise ValueError("canvas dimensions must be positive")
        self.image = Image.new("RGBA", (width, height), color)

    @classmethod
    def from_image(cls, image: Image.Image) -> "Canvas":
        """Create a canvas detached from a Pillow image owned elsewhere."""
        canvas = cls(*image.size)
        canvas.image = image.convert("RGBA").copy()
        return canvas

    @classmethod
    def load_image(cls, path: str | Path) -> "Canvas":
        """Load an image file into a detached canvas."""
        with Image.open(path) as image:
            return cls.from_image(image)

    @staticmethod
    def load_font(path: str | Path | None = None, size: int = 16) -> Any:
        """Load a font for drawing text on a canvas."""
        if path is None:
            return ImageFont.load_default()
        return ImageFont.truetype(str(path), size)

    def ellipse(
        self,
        box: tuple[int, int, int, int],
        fill: str | tuple[int, ...],
    ) -> "Canvas":
        """Draw an ellipse on the canvas."""
        ImageDraw.Draw(self.image).ellipse(box, fill=fill)
        return self

    def line(
        self,
        points: tuple[int, int, int, int],
        fill: str | tuple[int, ...],
        width: int = 2,
    ) -> "Canvas":
        """Draw a debug or interaction line on the canvas."""
        ImageDraw.Draw(self.image).line(points, fill=fill, width=width)
        return self

    def paste(
        self, canvas: "Canvas | Image.Image", position: tuple[int, int]
    ) -> "Canvas":
        """Paste another canvas with alpha
            compositing at an absolute position."""
        source = canvas.image if isinstance(canvas, Canvas) else canvas
        self.image.alpha_composite(source.convert("RGBA"), dest=position)
        return self

    def text(
        self,
        position: tuple[int, int],
        value: str,
        font: Any = None,
        fill: str | tuple[int, ...] = "white",
    ) -> "Canvas":
        """Draw text without exposing mutable drawing state."""
        ImageDraw.Draw(self.image).text(
            position, value, font=font or ImageFont.load_default(), fill=fill
        )
        return self

    def copy(self) -> "Canvas":
        """Return an independent snapshot suitable for publication."""
        return Canvas.from_image(self.image)

    def resize_to(
        self,
        width: int,
        height: int,
        resampling: Image.Resampling = Image.Resampling.LANCZOS,
    ) -> "Canvas":
        """Return a pixel-sized copy at the requested dimensions."""
        return Canvas.from_image(
            self.image.resize((width, height), resampling)
        )

    def mlx_bytes(self) -> bytes:
        """Convert RGBA pixels to the BGRA byte order used by MLX images."""
        red, green, blue, alpha = self.image.split()
        return Image.merge("RGBA",
                           (blue, green, red, alpha)).tobytes("raw", "RGBA")
