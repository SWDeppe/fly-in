import os
from typing import Any

from PIL import Image, ImageFont
from ..errors.VErrors import VEngineError


class Textures:
    """Preload and keep image/font assets ready for later use."""

    _entries: dict[int, dict[str, Any]] = {}
    _next_id = 0

    @classmethod
    def _next_entry_id(cls) -> int:
        cls._next_id += 1
        return cls._next_id

    @classmethod
    def preload_image(
        cls,
        path: str,
        *,
        name: str | None = None,
        size: tuple[int, int] | None = None,
        mode: str = "RGBA",
    ) -> int:
        """Load an image file and store its decoded data for later use."""
        if not os.path.exists(path):
            raise VEngineError(f"Image file not found: {path}")

        image = Image.open(path).convert(mode)
        if size is not None:
            image = image.resize(size)

        entry_id = cls._next_entry_id()
        cls._entries[entry_id] = {
            "id": entry_id,
            "type": "image",
            "name": name or os.path.basename(path),
            "path": path,
            "image": image,
            "size": image.size,
            "mode": image.mode,
        }
        return entry_id

    @classmethod
    def preload_font(
        cls,
        path: str,
        *,
        name: str | None = None,
        size: int = 12,
    ) -> int:
        """Load a font file and keep the font object for later rendering."""
        if not os.path.exists(path):
            raise VEngineError(f"Font file not found: {path}")

        font = None
        loaded = False
        try:
            font = ImageFont.truetype(path, size)
            loaded = True
        except (OSError, AttributeError):
            font = None

        entry_id = cls._next_entry_id()
        cls._entries[entry_id] = {
            "id": entry_id,
            "type": "font",
            "name": name or os.path.basename(path),
            "path": path,
            "font": font,
            "size": size,
            "loaded": loaded,
        }
        return entry_id

    @classmethod
    def get_entry(cls, entry_id: int) -> dict[str, Any]:
        """Return a stored asset entry by its ID."""
        return cls._entries[entry_id]

    @classmethod
    def get_all_ids(cls) -> list[int]:
        """Return all currently stored asset IDs."""
        return list(cls._entries.keys())

    @classmethod
    def clear(cls) -> None:
        """Clear the asset registry."""
        cls._entries.clear()
        cls._next_id = 0

    @classmethod
    def get_image(cls, entry_id: int) -> Image.Image:
        """Retrieve a preloaded image by ID."""
        entry = cls.get_entry(entry_id)
        if entry["type"] != "image":
            raise VEngineError("Entry is not an image")
        return entry["image"]

    @classmethod
    def get_font(cls, entry_id: int) -> Any:
        """Retrieve a preloaded font by ID."""
        entry = cls.get_entry(entry_id)
        if entry["type"] != "font":
            raise VEngineError("Entry is not a font")
        return entry["font"]