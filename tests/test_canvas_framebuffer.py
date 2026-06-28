import os
import tempfile
import unittest

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


if __name__ == "__main__":
    unittest.main()
