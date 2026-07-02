"""pywebview主入口 - React桌面应用"""
from copy import deepcopy
import json
import threading
import webview
from pathlib import Path
from tkcopy.logging_utils import print_log
from tkcopy.utils.script_planner import DEFAULT_RECAP_STYLE_PROMPT
from tkcopy.workflow import default_vad_model, run_workflow, WorkflowInputs


def default_whisper_model() -> str:
    """Prefer an existing local ggml model; fall back to whispercpp's bundled name."""
    candidates = [
        Path.cwd() / ".models" / "ggml-large-v3-turbo.bin",
        Path.cwd() / "model" / "ggml-large-v3-turbo.bin",
        Path.home() / "Documents" / "autocopy" / "model" / "ggml-large-v3-turbo.bin",
        Path.home() / "Downloads" / "爆款文案洗稿" / ".models" / "ggml-large-v3-turbo.bin",
    ]
    for candidate in candidates:
        if candidate.exists():
            return str(candidate)
    return "base"


DEFAULT_SETTINGS = {
    "whisper_model": default_whisper_model(),
    "vad_model": default_vad_model(),
    "vad": {
        "threshold": 0.25,
        "min_speech_ms": 10,
        "min_silence_ms": 50,
    },
    "demucs_model": "htdemucs",
    "frame_match": {
        "engine": "vmf",
        "vmf_bin": "/Users/chaiyapeng/Documents/autocopy/.venv/bin/vmf",
        "fps": 3.0,
        "model": "dinov2_vits14",
        "device": "cpu",
        "batch_size": 64,
        "inflight": 1,
        "padding_seconds": 90.0,
    },
    "speaker": {
        "enabled": True,
        "similarity_threshold": 0.82,
        "pyannote_model": "pyannote/wespeaker-voxceleb-resnet34-LM",
        "hf_token": "",
    },
    "asr": {
        "language": "en",
        "prompt": "",
        "max_len": 50,
        "split_on_word": True,
        "speaker_threshold": 0.3,
        "timing_offset_ms": 820,
    },
    "llm": {
        "api_key": "",
        "model": "gemini-3.5-flash",
        "base_url": "https://yunwu.ai",
    },
    "minimax": {
        "api_key": "",
        "group_id": "",
        "voice_id": "",
        "base_url": "https://api.minimax.chat",
        "speed": 1.2,
    },
    "tts_provider": "minimax",
    "voxcpm": {
        "base_url": "",
        "api_type": "synthesize",
        "voice": "Natasha",
        "voice_refs": {
            "Natasha": "",
            "Alex": "",
        },
        "control": "",
        "seed": 42,
        "cfg_value": 2.0,
        "inference_timesteps": 10,
        "do_normalize": False,
        "denoise": False,
        "audio_format": "wav",
        "timeout": 900,
    },
    "rewrite_style": DEFAULT_RECAP_STYLE_PROMPT,
}
OBSOLETE_SETTING_KEYS = {"tts_extract"}


def merge_settings(defaults: dict, loaded: dict | None) -> dict:
    """Merge saved settings over defaults while dropping obsolete top-level keys."""
    result = deepcopy(defaults)
    for key, value in (loaded or {}).items():
        if key in OBSOLETE_SETTING_KEYS:
            continue
        if isinstance(result.get(key), dict) and isinstance(value, dict):
            result[key] = merge_settings(result[key], value)
        else:
            result[key] = value
    return result


class Api:
    """前端API接口"""

    def __init__(self):
        print_log("初始化 API", "Initializing API")
        self.settings = merge_settings(DEFAULT_SETTINGS, {})
        self._load_settings()

    def _load_settings(self):
        settings_path = Path(".data/settings.json")
        if settings_path.exists():
            print_log("加载本地配置", "Loading local settings", path=settings_path)
            loaded = json.loads(settings_path.read_text())
            self.settings = merge_settings(DEFAULT_SETTINGS, loaded)
        else:
            print_log("使用默认配置", "Using default settings", path=settings_path)

    def _save_settings(self):
        Path(".data/settings.json").parent.mkdir(parents=True, exist_ok=True)
        Path(".data/settings.json").write_text(json.dumps(self.settings, indent=2))
        print_log("保存配置完成", "Settings saved", path=".data/settings.json")

    def get_settings(self):
        print_log("前端读取配置", "Frontend requested settings")
        return self.settings

    def update_settings(self, key: str, value):
        print_log("更新配置", "Updating setting", key=key)
        self.settings[key] = value
        self._save_settings()
        return {"ok": True}

    def run_workflow(self, params: dict):
        """执行工作流"""
        print_log(
            "收到工作流请求",
            "Workflow request received",
            output_dir=params.get("output_dir", "output"),
        )
        inputs = WorkflowInputs(
            viral_video=params["viral_video"],
            source_video=params["source_video"],
            output_dir=params.get("output_dir", "output"),
            rewrite_style=params.get("rewrite_style", ""),
            target_language=params.get("target_language", "English"),
        )

        def _run():
            try:
                print_log("工作流线程启动", "Workflow thread started")
                result = run_workflow(inputs, self.settings, lambda msg: emit_frontend_event("progress", msg))
                print_log("工作流完成", "Workflow completed", final_video=result.get("final_video", ""))
                emit_frontend_event("complete", result)
            except Exception as e:
                print_log("工作流失败", "Workflow failed", error=str(e))
                emit_frontend_event("error", str(e))

        threading.Thread(target=_run, daemon=True).start()
        print_log("工作流已后台启动", "Workflow started in background")
        return {"ok": True, "message": "workflow started"}

    def select_file(self):
        """打开文件选择对话框"""
        print_log("打开文件选择器", "Opening file picker")
        result = webview.windows[0].create_file_dialog(webview.OPEN_DIALOG)
        print_log("文件选择完成", "File picker completed", selected=bool(result))
        return {"path": result[0] if result else None}


def emit_frontend_event(name: str, detail):
    """Dispatch a browser CustomEvent into the frontend."""
    if not webview.windows:
        print_log("跳过前端事件", "Skipping frontend event", event=name, reason="no_window")
        return

    print_log("发送前端事件", "Dispatching frontend event", event=name)
    event_name = json.dumps(name, ensure_ascii=False)
    event_detail = json.dumps(detail, ensure_ascii=False)
    script = f"window.dispatchEvent(new CustomEvent({event_name}, {{ detail: {event_detail} }}));"
    webview.windows[0].run_js(script)


def main():
    """启动应用"""
    print_log("准备启动应用", "Preparing to start app")
    frontend_path = Path(__file__).parent.parent / "frontend" / "dist"
    index_path = frontend_path / "index.html"
    if not index_path.exists():
        print_log("前端静态文件缺失", "Frontend static file missing", path=index_path)
        raise FileNotFoundError("前端静态文件不存在，请先运行 ./run.sh 编译前端")

    print_log("加载静态前端", "Loading static frontend", path=index_path)
    api = Api()
    window = webview.create_window("TKCopy", str(index_path), js_api=api, maximized=True)
    print_log("窗口已创建", "Window created", maximized=True)
    print_log("进入 pywebview 主循环", "Entering pywebview main loop", debug=False)
    webview.start(debug=False)


if __name__ == "__main__":
    main()
