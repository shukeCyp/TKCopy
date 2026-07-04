from pathlib import Path
import unittest


def read_frontend_sources():
    return "\n".join(
        path.read_text(encoding="utf-8")
        for path in sorted(Path("frontend/src").rglob("*.jsx"))
    )


class FrontendContractTests(unittest.TestCase):
    def test_pywebview_api_is_resolved_at_call_time(self):
        source = Path("frontend/src/App.jsx").read_text(encoding="utf-8")

        self.assertIn("function getApi()", source)
        self.assertIn("requiredApiMethods.every", source)
        self.assertIn("typeof pywebviewApi[method] === 'function'", source)
        self.assertIn("getApi().select_file()", source)
        self.assertIn("getApi().select_directory()", source)
        self.assertIn("getApi().scan_batch_cases(", source)
        self.assertIn("getApi().run_batch_workflow(", source)
        self.assertNotIn("const api = window.pywebview?.api", source)

    def test_pywebview_events_use_browser_window_event_target(self):
        source = Path("frontend/src/App.jsx").read_text(encoding="utf-8")

        self.assertIn("window.addEventListener('progress'", source)
        self.assertIn("window.addEventListener('complete'", source)
        self.assertIn("window.addEventListener('error'", source)
        self.assertIn("window.addEventListener('batch_progress'", source)
        self.assertNotIn("window.pywebview.addEventListener", source)
        self.assertNotIn("window.pywebview?.removeEventListener", source)

    def test_frontend_exposes_single_batch_settings_and_logs_views(self):
        source = read_frontend_sources()

        self.assertIn("单集任务", source)
        self.assertIn("批量任务", source)
        self.assertIn("设置", source)
        self.assertIn("日志", source)
        self.assertIn("BatchView", source)
        self.assertIn("LogsView", source)

    def test_frontend_removes_view_titles_and_uses_stage_setting_cards(self):
        source = read_frontend_sources()

        self.assertNotIn("<h1>", source)
        self.assertIn('className="settings-card"', source)
        self.assertIn("阶段1 TTS分离", source)
        self.assertIn("阶段2 解说规划", source)
        self.assertIn("阶段3 画面匹配", source)
        self.assertIn("阶段4 语音生成", source)
        self.assertIn("阶段5 剪映草稿", source)

    def test_frontend_exposes_rewrite_style_library_cards(self):
        source = read_frontend_sources()

        self.assertIn("rewrite_styles", source)
        self.assertIn("改写风格库", source)
        self.assertIn("StyleLibraryView", source)
        self.assertIn("StyleLibrary", source)
        self.assertIn("activeView === 'styles'", source)
        self.assertIn("默认", source)
        self.assertIn("style-card", source)

    def test_frontend_defaults_to_voxcpm_cloud_settings(self):
        source = Path("frontend/src/App.jsx").read_text(encoding="utf-8")

        self.assertIn("tts_provider: 'voxcpm'", source)
        self.assertIn("https://swc0syb3hwdavikr-8808.container.x-gpu.com/", source)
        self.assertIn("/Users/chaiyapeng/Downloads/草稿/JianyingPro Drafts", source)

    def test_frontend_uses_component_library_and_split_views(self):
        app_source = Path("frontend/src/App.jsx").read_text(encoding="utf-8")
        required_files = [
            "frontend/src/components/ui/index.jsx",
            "frontend/src/components/layout/AppShell.jsx",
            "frontend/src/views/SingleTaskView.jsx",
            "frontend/src/views/BatchView.jsx",
            "frontend/src/views/SettingsView.jsx",
            "frontend/src/views/StyleLibraryView.jsx",
            "frontend/src/views/LogsView.jsx",
        ]

        for filename in required_files:
            self.assertTrue(Path(filename).exists(), filename)

        self.assertIn("import { AppShell } from './components/layout/AppShell.jsx'", app_source)
        self.assertIn("import { SingleTaskView } from './views/SingleTaskView.jsx'", app_source)
        self.assertIn("import { BatchView } from './views/BatchView.jsx'", app_source)
        self.assertIn("import { SettingsView } from './views/SettingsView.jsx'", app_source)
        self.assertIn("import { StyleLibraryView } from './views/StyleLibraryView.jsx'", app_source)
        self.assertIn("import { LogsView } from './views/LogsView.jsx'", app_source)

    def test_outer_shell_is_fixed_and_workspace_owns_vertical_scroll(self):
        source = Path("frontend/src/index.css").read_text(encoding="utf-8")

        self.assertRegex(source, r"html,\s*body,\s*#root\s*\{[^}]*height:\s*100%;[^}]*overflow:\s*hidden;")
        self.assertRegex(source, r"\.app-shell\s*\{[^}]*height:\s*100vh;[^}]*overflow:\s*hidden;")
        self.assertRegex(source, r"\.workspace\s*\{[^}]*height:\s*100vh;[^}]*overflow-y:\s*auto;")


if __name__ == "__main__":
    unittest.main()
