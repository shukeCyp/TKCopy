from pathlib import Path
import unittest


class ViteConfigTests(unittest.TestCase):
    def test_build_uses_relative_asset_paths_for_pywebview_file_loading(self):
        config = Path("frontend/vite.config.ts").read_text(encoding="utf-8")

        self.assertIn("base: './'", config)


if __name__ == "__main__":
    unittest.main()
