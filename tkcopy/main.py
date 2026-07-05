"""pywebview主入口 - React桌面应用"""
from copy import deepcopy
from datetime import datetime
import json
import threading
import webview
from pathlib import Path
from tkcopy.batch import run_batch_workflows, scan_batch_cases
from tkcopy.logging_utils import print_log
from tkcopy.utils.script_planner import DEFAULT_RECAP_STYLE_PROMPT
from tkcopy.workflow import default_vad_model, run_workflow, WorkflowInputs


DEFAULT_VOXCPM_BASE_URL = "https://swc0syb3hwdavikr-8808.container.x-gpu.com/"
DEFAULT_JIANYING_DRAFT_FOLDER = "/Users/chaiyapeng/Downloads/草稿/JianyingPro Drafts"
DEFAULT_NATASHA_REF = "/Users/chaiyapeng/Documents/VoxCPM/reference_audio/Natasha.mp3"
DEFAULT_ALEX_REF = "/Users/chaiyapeng/Documents/VoxCPM/reference_audio/Alex.mp3"
DEFAULT_REWRITE_STYLES = [
    {
        "id": "default",
        "name": "默认",
        "prompt": DEFAULT_RECAP_STYLE_PROMPT,
    }
]


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
    "tts_provider": "voxcpm",
    "voxcpm": {
        "base_url": DEFAULT_VOXCPM_BASE_URL,
        "api_type": "gradio",
        "voice": "Natasha",
        "voice_refs": {
            "Natasha": DEFAULT_NATASHA_REF,
            "Alex": DEFAULT_ALEX_REF,
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
    "jianying": {
        "draft_folder": DEFAULT_JIANYING_DRAFT_FOLDER,
    },
    "rewrite_style": DEFAULT_RECAP_STYLE_PROMPT,
    "rewrite_styles": DEFAULT_REWRITE_STYLES,
    "selected_rewrite_style_id": "default",
}
OBSOLETE_SETTING_KEYS = {"tts_extract"}


def normalize_rewrite_settings(settings: dict, rewrite_styles_was_loaded: bool = True) -> dict:
    """Keep the legacy rewrite_style field and the style library in sync."""
    legacy_prompt = settings.get("rewrite_style") or DEFAULT_RECAP_STYLE_PROMPT
    raw_styles = settings.get("rewrite_styles") if rewrite_styles_was_loaded else []
    normalized_styles = []

    if isinstance(raw_styles, list):
        for index, style in enumerate(raw_styles):
            if not isinstance(style, dict):
                continue
            style_id = str(style.get("id") or ("default" if index == 0 else f"style_{index + 1}"))
            name = str(style.get("name") or ("默认" if style_id == "default" else f"风格 {index + 1}"))
            normalized_styles.append(
                {
                    "id": style_id,
                    "name": name,
                    "prompt": str(style.get("prompt") or ""),
                }
            )

    if not normalized_styles:
        normalized_styles = [
            {
                "id": "default",
                "name": "默认",
                "prompt": legacy_prompt,
            }
        ]
    elif not any(style["id"] == "default" for style in normalized_styles):
        normalized_styles.insert(
            0,
            {
                "id": "default",
                "name": "默认",
                "prompt": legacy_prompt,
            },
        )

    selected_style_id = settings.get("selected_rewrite_style_id")
    if not any(style["id"] == selected_style_id for style in normalized_styles):
        selected_style_id = normalized_styles[0]["id"]
    active_style = next(style for style in normalized_styles if style["id"] == selected_style_id)

    settings["rewrite_styles"] = normalized_styles
    settings["selected_rewrite_style_id"] = selected_style_id
    settings["rewrite_style"] = active_style.get("prompt") or legacy_prompt
    return settings


def merge_settings(defaults: dict, loaded: dict | None) -> dict:
    """Merge saved settings over defaults while dropping obsolete top-level keys."""
    result = deepcopy(defaults)
    rewrite_styles_was_loaded = isinstance(loaded, dict) and "rewrite_styles" in loaded
    for key, value in (loaded or {}).items():
        if key in OBSOLETE_SETTING_KEYS:
            continue
        if isinstance(result.get(key), dict) and isinstance(value, dict):
            result[key] = merge_settings(result[key], value)
        else:
            result[key] = value
    if "rewrite_style" in result or "rewrite_styles" in result:
        normalize_rewrite_settings(result, rewrite_styles_was_loaded)
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
        Path(".data/settings.json").write_text(json.dumps(self.settings, indent=2, ensure_ascii=False))
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
                print_log("工作流完成", "Workflow completed", jianying_draft=result.get("jianying_draft", ""))
                emit_frontend_event("complete", result)
            except Exception as e:
                print_log("工作流失败", "Workflow failed", error=str(e))
                emit_frontend_event("error", str(e))

        threading.Thread(target=_run, daemon=True).start()
        print_log("工作流已后台启动", "Workflow started in background")
        return {"ok": True, "message": "workflow started"}

    def scan_batch_cases(self, params: dict):
        """扫描批量任务目录"""
        root_dir = params.get("root_dir", "")
        voice_split_count = int(params.get("voice_split_count", 5))
        print_log("收到批量扫描请求", "Batch scan request received", root_dir=root_dir)
        cases = scan_batch_cases(root_dir, voice_split_count=voice_split_count)
        return {"ok": True, "cases": cases}

    def run_batch_workflow(self, params: dict):
        """按顺序执行批量工作流"""
        root_dir = params.get("root_dir", "")
        output_base = Path(params.get("output_dir") or "output").expanduser()
        output_root = output_base / f"batch_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        cases = params.get("cases") or scan_batch_cases(root_dir, voice_split_count=int(params.get("voice_split_count", 5)))
        rewrite_style = params.get("rewrite_style", "")
        target_language = params.get("target_language", "English")
        print_log("收到批量工作流请求", "Batch workflow request received", cases=len(cases), output_root=output_root)

        def _run():
            try:
                result = run_batch_workflows(
                    cases,
                    self.settings,
                    output_root,
                    rewrite_style=rewrite_style,
                    target_language=target_language,
                    progress=lambda detail: emit_frontend_event("batch_progress", detail),
                )
                emit_frontend_event("complete", result)
            except Exception as e:
                print_log("批量工作流失败", "Batch workflow failed", error=str(e))
                emit_frontend_event("error", str(e))

        threading.Thread(target=_run, daemon=True).start()
        print_log("批量工作流已后台启动", "Batch workflow started in background")
        return {"ok": True, "message": "batch workflow started", "output_root": str(output_root)}

    def select_file(self):
        """打开文件选择对话框"""
        print_log("打开文件选择器", "Opening file picker")
        result = webview.windows[0].create_file_dialog(webview.OPEN_DIALOG)
        print_log("文件选择完成", "File picker completed", selected=bool(result))
        return {"path": result[0] if result else None}

    def select_directory(self):
        """打开目录选择对话框"""
        print_log("打开目录选择器", "Opening folder picker")
        result = webview.windows[0].create_file_dialog(webview.FOLDER_DIALOG)
        print_log("目录选择完成", "Folder picker completed", selected=bool(result))
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
