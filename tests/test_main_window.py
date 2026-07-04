from unittest import TestCase
from unittest.mock import patch
from pathlib import Path
import io
import os

from tkcopy import main as app_main


class MainWindowTests(TestCase):
    def test_print_log_outputs_bilingual_message_with_details(self):
        output = io.StringIO()

        with patch("sys.stdout", output):
            app_main.print_log("启动应用", "Starting app", path="frontend/dist/index.html")

        self.assertEqual(
            output.getvalue().strip(),
            "[TKCopy] 启动应用 / Starting app | path=frontend/dist/index.html",
        )

    def test_main_window_starts_maximized_without_debug_tools(self):
        with (
            patch.dict(os.environ, {}, clear=True),
            patch.object(app_main.webview, "create_window") as create_window,
            patch.object(app_main.webview, "start") as start,
        ):
            app_main.main()

        create_window.assert_called_once()
        self.assertTrue(create_window.call_args.kwargs["maximized"])
        start.assert_called_once_with(debug=False)

    def test_dist_entry_uses_pywebview_local_path_instead_of_file_uri(self):
        expected_index = (
            Path(app_main.__file__).parent.parent / "frontend" / "dist" / "index.html"
        )

        with (
            patch.dict(os.environ, {}, clear=True),
            patch.object(app_main.webview, "create_window") as create_window,
            patch.object(app_main.webview, "start"),
        ):
            app_main.main()

        url = create_window.call_args.args[1]
        self.assertEqual(url, str(expected_index))
        self.assertFalse(url.startswith("file://"))

    def test_dist_entry_ignores_old_dev_server_environment_override(self):
        expected_index = (
            Path(app_main.__file__).parent.parent / "frontend" / "dist" / "index.html"
        )

        with (
            patch.dict(os.environ, {"TKCOPY_FRONTEND_URL": "http://localhost:5173"}, clear=True),
            patch.object(app_main.webview, "create_window") as create_window,
            patch.object(app_main.webview, "start"),
        ):
            app_main.main()

        self.assertEqual(create_window.call_args.args[1], str(expected_index))

    def test_frontend_events_are_dispatched_with_browser_custom_events(self):
        class Window:
            def __init__(self):
                self.scripts = []

            def run_js(self, script):
                self.scripts.append(script)

        window = Window()

        with patch.object(app_main.webview, "windows", [window]):
            app_main.emit_frontend_event("progress", "TTS分离")

        self.assertEqual(len(window.scripts), 1)
        self.assertIn("window.dispatchEvent(new CustomEvent", window.scripts[0])
        self.assertIn('"progress"', window.scripts[0])
        self.assertIn('"TTS分离"', window.scripts[0])

    def test_backend_does_not_call_missing_pywebview_emit_api(self):
        source = Path(app_main.__file__).read_text(encoding="utf-8")

        self.assertNotIn(".emit(", source)

    def test_saved_settings_are_deep_merged_and_drop_obsolete_tts_extract(self):
        merged = app_main.merge_settings(
            app_main.DEFAULT_SETTINGS,
            {
                "tts_extract": {"refresh_gemini": True},
                "llm": {"api_key": "llm-key"},
                "minimax": {"model": "speech-2.8-hd", "speed": 1.2},
            },
        )

        self.assertNotIn("tts_extract", merged)
        self.assertEqual(merged["llm"]["api_key"], "llm-key")
        self.assertEqual(merged["llm"]["model"], "gemini-3.5-flash")
        self.assertEqual(merged["minimax"]["model"], "speech-2.8-hd")
        self.assertEqual(merged["minimax"]["speed"], 1.2)
        self.assertEqual(merged["speaker"]["pyannote_model"], "pyannote/wespeaker-voxceleb-resnet34-LM")
        self.assertEqual(merged["asr"]["speaker_threshold"], 0.3)

    def test_default_minimax_speed_is_1_2(self):
        self.assertEqual(app_main.DEFAULT_SETTINGS["minimax"]["speed"], 1.2)

    def test_default_settings_include_voxcpm_remote_provider(self):
        merged = app_main.merge_settings(
            app_main.DEFAULT_SETTINGS,
            {
                "voxcpm": {
                    "base_url": "https://tts.example.com",
                    "api_type": "gradio",
                    "voice_refs": {"Natasha": "/voices/natasha.mp3"},
                }
            },
        )

        self.assertEqual(app_main.DEFAULT_SETTINGS["tts_provider"], "voxcpm")
        self.assertEqual(
            app_main.DEFAULT_SETTINGS["voxcpm"]["base_url"],
            "https://swc0syb3hwdavikr-8808.container.x-gpu.com/",
        )
        self.assertEqual(app_main.DEFAULT_SETTINGS["voxcpm"]["api_type"], "gradio")
        self.assertEqual(merged["voxcpm"]["base_url"], "https://tts.example.com")
        self.assertEqual(merged["voxcpm"]["api_type"], "gradio")
        self.assertEqual(merged["voxcpm"]["voice"], "Natasha")
        self.assertEqual(merged["voxcpm"]["voice_refs"]["Natasha"], "/voices/natasha.mp3")
        self.assertIn("Alex", merged["voxcpm"]["voice_refs"])
        self.assertFalse(merged["voxcpm"]["do_normalize"])
        self.assertFalse(merged["voxcpm"]["denoise"])
        self.assertEqual(merged["voxcpm"]["audio_format"], "wav")

    def test_default_rewrite_style_uses_overseas_recap_prompt(self):
        style = app_main.DEFAULT_SETTINGS["rewrite_style"]

        self.assertIn("fast-paced English short-form TV/movie recap style", style)
        self.assertIn("Most sentences should be 6-12 words", style)

    def test_default_rewrite_style_library_has_named_default_card(self):
        styles = app_main.DEFAULT_SETTINGS["rewrite_styles"]

        self.assertEqual(styles[0]["id"], "default")
        self.assertEqual(styles[0]["name"], "默认")
        self.assertEqual(styles[0]["prompt"], app_main.DEFAULT_SETTINGS["rewrite_style"])

    def test_legacy_rewrite_style_is_migrated_into_style_library(self):
        merged = app_main.merge_settings(
            app_main.DEFAULT_SETTINGS,
            {"rewrite_style": "Legacy custom style"},
        )

        self.assertEqual(merged["rewrite_styles"][0]["id"], "default")
        self.assertEqual(merged["rewrite_styles"][0]["name"], "默认")
        self.assertEqual(merged["rewrite_styles"][0]["prompt"], "Legacy custom style")
        self.assertEqual(merged["selected_rewrite_style_id"], "default")

    def test_default_settings_include_jianying_draft_folder(self):
        self.assertEqual(
            app_main.DEFAULT_SETTINGS["jianying"]["draft_folder"],
            "/Users/chaiyapeng/Downloads/草稿/JianyingPro Drafts",
        )

    def test_api_select_directory_uses_folder_dialog(self):
        api = app_main.Api()

        with patch.object(app_main.webview, "windows") as windows:
            windows.__bool__.return_value = True
            windows.__getitem__.return_value.create_file_dialog.return_value = ["/tmp/output"]

            result = api.select_directory()

        self.assertEqual(result, {"path": "/tmp/output"})
        windows.__getitem__.return_value.create_file_dialog.assert_called_once_with(app_main.webview.FOLDER_DIALOG)
