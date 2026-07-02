from pathlib import Path
import unittest


class FrontendContractTests(unittest.TestCase):
    def test_pywebview_api_is_resolved_at_call_time(self):
        source = Path("frontend/src/App.jsx").read_text(encoding="utf-8")

        self.assertIn("function getApi()", source)
        self.assertIn("requiredApiMethods.every", source)
        self.assertIn("typeof pywebviewApi[method] === 'function'", source)
        self.assertIn("getApi().select_file()", source)
        self.assertNotIn("const api = window.pywebview?.api", source)

    def test_pywebview_events_use_browser_window_event_target(self):
        source = Path("frontend/src/App.jsx").read_text(encoding="utf-8")

        self.assertIn("window.addEventListener('progress'", source)
        self.assertIn("window.addEventListener('complete'", source)
        self.assertIn("window.addEventListener('error'", source)
        self.assertNotIn("window.pywebview.addEventListener", source)
        self.assertNotIn("window.pywebview?.removeEventListener", source)


if __name__ == "__main__":
    unittest.main()
