#!/usr/bin/python3.10
import queue
import threading
from pprint import pformat
from visual_engine import VEngine, Textures
from subprocess import call
from pathlib import Path
from src.parsing import parser


_CURRENT_DATA: dict | None = None
_CURRENT_TEXTURE: int | None = None
_CURRENT_TEXT: str | None = None


def main():
    ...


def test_c():
    call(["./build/fly_in"])


# def test_VEngine():
#     # Textures.preload_image()
#     VEngine.load()
#     # print("all fine")
#     VEngine.launch()
#     print(VEngineError.get_errors())

def show_data(data: dict, texture: int):
    global _CURRENT_DATA, _CURRENT_TEXTURE, _CURRENT_TEXT
    _CURRENT_DATA = data
    _CURRENT_TEXTURE = texture
    _CURRENT_TEXT = pformat(data)
    # VEngine.generate("primary", "main", texture, text="hello world", font_size=10)
    # VEngine.put_framebuffer("primary")


def in_loop_show():
    global _CURRENT_TEXT, _CURRENT_TEXTURE
    if _CURRENT_TEXTURE is None or _CURRENT_TEXT is None:
        return

    VEngine.generate("primary", "main", _CURRENT_TEXTURE, text=_CURRENT_TEXT, font_size=10)
    VEngine.put_framebuffer("primary")


is_showend = False
_render_queue: queue.Queue[bool] = queue.Queue()
_render_worker_started = False
_render_worker_lock = threading.Lock()


def _render_toggle_state(show_text: bool) -> None:
    if VEngine.context is None or _CURRENT_TEXTURE is None:
        return

    canvas = VEngine.context.framebuffers["primary"].canvases["main"]
    canvas.clear()

    if show_text and _CURRENT_TEXT is not None:
        VEngine.generate("primary", "main", _CURRENT_TEXTURE, text=_CURRENT_TEXT, font_size=10)

    VEngine.put_framebuffer("primary")


def _render_worker() -> None:
    while True:
        try:
            show_text = _render_queue.get(timeout=0.1)
        except queue.Empty:
            continue

        _render_toggle_state(show_text)
        _render_queue.task_done()


def _start_render_worker() -> None:
    global _render_worker_started
    if _render_worker_started:
        return

    with _render_worker_lock:
        if _render_worker_started:
            return
        threading.Thread(target=_render_worker, daemon=True).start()
        _render_worker_started = True


def on_key_show(key: int, _):
    global is_showend
    if key != 32:
        return

    show_text = not is_showend
    is_showend = show_text
    _start_render_worker()
    _render_queue.put(show_text)



def test_VEngine():
    # Textures.preload_image()
    # launch visual engine
    try:
        map_path = Path(__file__).resolve().parents[0] / "maps" / "easy" / "01_linear_path.txt"
        parse = parser.Parsing()
        print("parsing done !")
        data = parse.parse_file(map_path)
        print(data)
        font_path = Path(__file__).resolve().parents[0] / "includes" / "fonts" / "Roboto-Black.ttf"
        font_id = Textures.preload_font(font_path, name="Roboto-Black", size=6)

    except Exception as e:
        print(e.__str__())
        # print(map_path)
    else:
        VEngine.load()
        show_data(data, font_id)
        VEngine.put_framebuffer("primary")
        # VEngine.add_event(in_loop_show)
        VEngine.context.mlx_inst.mlx_key_hook(
            VEngine.context.window,
            on_key_show,
            None
        )
        VEngine.launch()


if __name__ == "__main__":
    test_VEngine()
