import os
import tempfile
import unittest

from modules.visual_engine.visual_engine.assets.VTextures import Textures


class VTexturesTests(unittest.TestCase):
    def test_preload_image_and_font_are_cached(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            image_path = os.path.join(tmpdir, "sample.png")
            font_path = os.path.join(tmpdir, "sample.ttf")

            from PIL import Image

            Image.new("RGBA", (1, 1), (255, 0, 0, 255)).save(image_path)
            with open(font_path, "wb") as fh:
                fh.write(b"fake-font")

            image_id = Textures.preload_image(image_path, name="sample")
            font_id = Textures.preload_font(font_path, name="sample_font")

            self.assertIn(image_id, Textures.get_all_ids())
            self.assertIn(font_id, Textures.get_all_ids())
            self.assertEqual(Textures.get_entry(image_id)["type"], "image")
            self.assertEqual(Textures.get_entry(font_id)["type"], "font")
            self.assertEqual(Textures.get_entry(image_id)["path"], image_path)
            self.assertEqual(Textures.get_entry(font_id)["path"], font_path)


if __name__ == "__main__":
    unittest.main()
