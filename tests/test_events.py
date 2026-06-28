import os
import sys
import tempfile
import unittest

from PIL import Image

# Ensure workspace package is preferred over any installed editable package
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from visual_engine import VEngine, EventManager, StopCall
from visual_engine import Textures


class EventTests(unittest.TestCase):
    def test_event_draws_text_and_is_removed(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            # prepare a small image to use as a texture
            image_path = os.path.join(tmpdir, "sample.png")
            Image.new("RGBA", (4, 4), (10, 20, 30, 255)).save(image_path)

            texture_id = Textures.preload_image(image_path, name="sample")

            VEngine.context = None
            VEngine.load(wsiz=(8, 8), create_window=False)

            # event that draws text into primary/main canvas once
            def my_event():
                fb = VEngine.context.framebuffers["primary"]
                c = fb.get_canvas("main")
                c.clear()
                c.draw_text("HI", pos=(0, 0), size=10, color=(0, 255, 0, 255))
                # return negative to indicate removal
                return -1

            EventManager.add(my_event)
            # run the engine (fallback python loop will execute the event)
            VEngine.launch()

            # after launch the event should be removed
            self.assertEqual(len(VEngine.context.events), 0)

            canvas = VEngine.context.framebuffers["primary"].get_canvas("main")
            # check that something green is present at 0,0
            px = canvas.pil_image.getpixel((0, 0))
            self.assertTrue(px[1] >= 1)


if __name__ == "__main__":
    unittest.main()
