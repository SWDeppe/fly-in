import os
import queue
import sys
import tempfile
import time
import unittest
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import fly_in

from PIL import Image

from visual_engine import VEngine
from visual_engine import Textures
from visual_engine import Canvas
from visual_engine import Framebuffer


class CanvasFramebufferTests(unittest.TestCase):
    def test_canvas_can_draw_texture_and_framebuffer_can_copy(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            image_path = os.path.join(tmpdir, "sample.png")
            Image.new("RGBA", (2, 2), (255, 0, 0, 255)).save(image_path)

            texture_id = Textures.preload_image(image_path, name="sample")
            canvas = Canvas(None, None, width=4, height=4, name="main")
            canvas.put_texture(texture_id, pos=(0, 0))

            self.assertEqual(canvas.pil_image.getpixel((0, 0)), (255, 0, 0, 255))

            primary = Framebuffer("primary")
            primary.add_canvas(canvas)
            back = Framebuffer("back")
            back.add_canvas(Canvas(None, None, width=4, height=4, name="main"))
            back.copy_from(primary)

            self.assertEqual(back.get_canvas("main").pil_image.getpixel((0, 0)), (255, 0, 0, 255))

    def test_engine_can_generate_into_named_framebuffer_canvas(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            image_path = os.path.join(tmpdir, "sample.png")
            Image.new("RGBA", (2, 2), (0, 255, 0, 255)).save(image_path)

            texture_id = Textures.preload_image(image_path, name="sample")
            VEngine.context = None
            VEngine.load(wsiz=(4, 4), create_window=False)
            VEngine.generate("primary", "main", texture_id, pos=(0, 0))

            canvas = VEngine.context.framebuffers["primary"].get_canvas("main")
            self.assertEqual(canvas.pil_image.getpixel((0, 0)), (0, 255, 0, 255))

    def test_canvas_can_draw_text_from_a_preloaded_font(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            font_path = os.path.join(tmpdir, "sample.ttf")
            with open(font_path, "wb") as fh:
                fh.write(b"fake-font")

            font_id = Textures.preload_font(font_path, name="sample_font")
            canvas = Canvas(None, None, width=8, height=8, name="text")
            canvas.put_font(font_id, "A", pos=(0, 0), color=(255, 0, 0, 255))

            self.assertTrue(any(pixel[3] > 0 for pixel in canvas.pil_image.getdata()))

    def test_put_framebuffer_clears_window_before_rendering(self):
        class DummyMlx:
            def __init__(self):
                self.clear_calls = []
                self.put_calls = []

            def mlx_new_image(self, mlx_ptr, width, height):
                return object()

            def mlx_get_data_addr(self, img_ptr):
                return bytearray(16), 32, 4, 0

            def mlx_put_image_to_window(self, mlx_ptr, win_ptr, img_ptr, x, y):
                self.put_calls.append((mlx_ptr, win_ptr, img_ptr, x, y))

            def mlx_clear_window(self, mlx_ptr, win_ptr):
                self.clear_calls.append((mlx_ptr, win_ptr))
                return 0

        dummy_mlx = DummyMlx()
        canvas = Canvas(dummy_mlx, object(), width=2, height=2, name="main")
        primary = Framebuffer("primary")
        primary.add_canvas(canvas)

        VEngine.context = SimpleNamespace(
            mlx_inst=dummy_mlx,
            mlx_ptr=object(),
            window=object(),
            framebuffers={"primary": primary},
        )

        VEngine.put_framebuffer("primary")

        self.assertEqual(len(dummy_mlx.clear_calls), 1)

    def test_on_key_show_schedules_background_render(self):
        called = []

        def fake_render(show_text):
            called.append(show_text)

        with patch.object(fly_in, "_render_toggle_state", side_effect=fake_render):
            fly_in.is_showend = False
            fly_in._render_queue = queue.Queue()
            fly_in._render_worker_started = False
            fly_in.on_key_show(32, None)

            deadline = time.time() + 1.0
            while not called and time.time() < deadline:
                time.sleep(0.01)

            self.assertEqual(called, [True])


if __name__ == "__main__":
    unittest.main()
