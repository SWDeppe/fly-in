from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable

from mlx import Mlx
from .errors.VErrors import VEngineError

from .assets.VTextures import Textures
from .buffer.VCanvas import Canvas
from .buffer.VFramebuffer import Framebuffer

Vec2 = tuple[int, int]
Vec3 = tuple[int, int, int]


class VEngine:
    context: "VEngine.Context | None" = None

    @classmethod
    def load(
        cls,
        wsiz: Vec2 = (600, 800),
        context: "VEngine.Context | None" = None,
        *,
        create_window: bool = True,
        window_title: str = "fly in",
    ) -> None:
        if context is not None:
            cls.context = context
            return
        mlx_instance = Mlx()
        mlx_ptr = mlx_instance.mlx_init()
        mlx_window = None
        if create_window:
            mlx_window = mlx_instance.mlx_new_window(
                mlx_ptr, wsiz[0], wsiz[1], window_title
            )

        framebuffers = {
            "primary": Framebuffer("primary"),
            "back": Framebuffer("back"),
        }
        framebuffers["primary"].add_canvas(
            Canvas(mlx_instance,
                   mlx_ptr,
                   width=wsiz[0],
                   height=wsiz[1],
                   name="main")
        )
        framebuffers["back"].add_canvas(
            Canvas(mlx_instance,
                   mlx_ptr,
                   width=wsiz[0],
                   height=wsiz[1],
                   name="main")
        )

        cls.context = cls.Context(
            mlx_inst=mlx_instance,
            mlx_ptr=mlx_ptr,
            window=mlx_window,
            wsiz=wsiz,
            framebuffers=framebuffers,
            events=[],
        )        

    @classmethod
    def load_texture(
        cls, path: str, *, name: str | None = None, size: Vec2 | None = None
    ) -> int:
        """Load an image texture and return its texture id."""
        if size is None:
            return Textures.preload_image(path, name=name)
        return Textures.preload_image(path, name=name, size=size)

    @classmethod
    def attach_canvas(cls, framebuffer_name: str, canvas: Canvas) -> None:
        if cls.context is None:
            raise VEngineError("VEngine context is not loaded")
        cls.context.framebuffers[framebuffer_name].add_canvas(canvas)

    @classmethod
    def put_framebuffer(cls, framebuffer_name: str) -> None:
        if cls.context is None:
            raise VEngineError("VEngine context is not loaded")
        framebuffer = cls.context.framebuffers[framebuffer_name]
        for canvas in framebuffer.canvases.values():
            if canvas.mlx_image is not None:
                cls.context.mlx_inst.mlx_put_image_to_window(
                    cls.context.mlx_ptr,
                    cls.context.window,
                    canvas.mlx_image,
                    0,
                    0,
                )

    @classmethod
    def add_event(cls, func: Callable[[], int | None]) -> None:
        if cls.context is None:
            raise VEngineError("VEngine context is not loaded")
        cls.context.events.append(func)

    @classmethod
    def launch(cls) -> None:
        if cls.context is None:
            raise VEngineError("VEngine context is not loaded")

        # Prefer registering a loop hook with mlx so callbacks run from the
        # C main loop. Fall back to a short Python-side loop for tests.
        def _run_once():
            to_remove: list[Callable[[], int | None]] = []
            for fn in list(cls.context.events):
                try:
                    res = fn()
                    if isinstance(res, int) and res < 0:
                        to_remove.append(fn)
                except StopCall:
                    to_remove.append(fn)
            for fn in to_remove:
                if fn in cls.context.events:
                    cls.context.events.remove(fn)

        # If no window (headless / tests), avoid registering the MLX C
        # callback which can repeatedly invoke Python code and surface
        # unhandled exceptions via the ctypes machinery. Instead run a
        # bounded Python-side loop until events are empty.
        if cls.context.window is None:
            max_iter = 50
            for _ in range(max_iter):
                _run_once()
                if not cls.context.events:
                    break
            return

        def close(_):
            cls.context.mlx_inst.mlx_destroy_window(
                cls.context.mlx_ptr,
                cls.context.window
            )
            cls.context.mlx_inst.mlx_loop_exit(
                cls.context.mlx_ptr
            )

        try:
            # register mlx loop hook if available. Wrap the call in a
            # protective try/except so exceptions from callbacks don't
            # escape into the ctypes layer (which prints repeated
            # 'Exception ignored on calling ctypes callback function').
            def _safe_hook(p):
                try:
                    _run_once()
                except Exception as e:
                    # Register the error but do not propagate into the
                    # ctypes callback layer (which would spam output).
                    VEngineError(f"Callback error: {e}")
                    return 0

            cls.context.mlx_inst.mlx_loop_hook(
                cls.context.mlx_ptr, lambda p: _safe_hook(p), None
            )
            cls.context.mlx_inst.mlx_key_hook(
                cls.context.window, lambda p: _safe_hook(p), None
            )
            cls.context.mlx_inst.mlx_hook(
                cls.context.window,
                33,
                0,
                close,
                None
            )
            # cls.context.mlx_inst.mlx_loop_hook(
            #     cls.context.mlx_ptr, cls.context.mlx_ptr, None
            # )
            cls.context.mlx_inst.mlx_loop(cls.context.mlx_ptr)
            print("loop launched")
        except Exception:
            # fallback: run a few iterations synchronously
            print("Somthing went wrong")
            for _ in range(10):
                _run_once()

    @classmethod
    def generate(
        cls,
        framebuffer_name: str,
        canvas_name: str,
        texture_id: int,
        pos: Vec2 = (0, 0),
    ) -> None:
        if cls.context is None:
            raise VEngineError("VEngine context is not loaded")
        framebuffer = cls.context.framebuffers[framebuffer_name]
        canvas = framebuffer.get_canvas(canvas_name)
        canvas.put_texture(texture_id, pos=pos)

    @dataclass
    class Context:
        mlx_inst: Mlx
        mlx_ptr: Any
        window: Any | None
        wsiz: Vec2
        framebuffers: dict[str, Framebuffer] = field(default_factory=dict)
        events: list[Callable[[], int | None]] = field(default_factory=list)


class EventManager:
    """Helper to manage event callbacks attached to VEngine.context.events."""

    @staticmethod
    def add(fn: Callable[[], int | None]) -> None:
        VEngine.add_event(fn)

    @staticmethod
    def remove(fn: Callable[[], int | None]) -> None:
        if VEngine.context is not None and fn in VEngine.context.events:
            VEngine.context.events.remove(fn)
