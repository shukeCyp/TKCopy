"""工作流编排 - 按步骤执行完整复刻流程"""
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
import shutil
import time
from typing import Any, Callable

from tkcopy.logging_utils import print_log
from tkcopy.utils.tts_extractor import run_tts_extraction
from tkcopy.utils.script_planner import plan_narration_beats
from tkcopy.utils.frame_matcher import run_frame_match
from tkcopy.utils.vmf_frame_matcher import run_vmf_frame_match
from tkcopy.utils.tts_provider import MiniMaxTTSProvider, VoxCPMTTSProvider, synthesize_narration_audio
from tkcopy.utils.copy_text import write_copy_text
from tkcopy.utils.video_composer import compose_video
from tkcopy.utils.jianying_export import create_jianying_clip_draft


@dataclass(frozen=True)
class WorkflowInputs:
    viral_video: str | Path
    source_video: str | Path
    output_dir: str | Path
    rewrite_style: str = ""
    target_language: str = "English"


def _setting_status(value: Any) -> str:
    return "SET" if str(value or "").strip() else "EMPTY"


def default_vad_model() -> str:
    """Prefer the local Silero VAD model used by the autocopy workflow."""
    candidates = [
        Path.cwd() / ".models" / "ggml-silero-v6.2.0.bin",
        Path.cwd() / "model" / "ggml-silero-v6.2.0.bin",
        Path.home() / "Documents" / "autocopy" / "model" / "ggml-silero-v6.2.0.bin",
    ]
    for candidate in candidates:
        if candidate.exists():
            return str(candidate)
    return ""


def build_tts_provider(settings: dict[str, Any]):
    provider_name = str(settings.get("tts_provider", "minimax") or "minimax").strip().lower()
    if provider_name == "voxcpm":
        voxcpm_settings = settings.get("voxcpm") or {}
        return VoxCPMTTSProvider(
            base_url=voxcpm_settings.get("base_url", ""),
            api_type=voxcpm_settings.get("api_type", "synthesize"),
            voice=voxcpm_settings.get("voice", "Natasha"),
            voice_refs=voxcpm_settings.get("voice_refs", {}),
            control=voxcpm_settings.get("control", ""),
            seed=voxcpm_settings.get("seed", 42),
            cfg_value=float(voxcpm_settings.get("cfg_value", 2.0)),
            inference_timesteps=int(voxcpm_settings.get("inference_timesteps", 10)),
            do_normalize=bool(voxcpm_settings.get("do_normalize", False)),
            denoise=bool(voxcpm_settings.get("denoise", False)),
            audio_format=voxcpm_settings.get("audio_format", "wav"),
            timeout=int(voxcpm_settings.get("timeout", 900)),
        )

    minimax_settings = settings["minimax"]
    return MiniMaxTTSProvider(
        api_key=minimax_settings["api_key"],
        group_id=minimax_settings["group_id"],
        voice_id=minimax_settings["voice_id"],
        base_url=minimax_settings.get("base_url", "https://api.minimax.chat"),
        model=minimax_settings.get("model", "speech-02-hd"),
        speed=float(minimax_settings.get("speed", 1.2)),
        volume=float(minimax_settings.get("volume", 1.0)),
        pitch=int(minimax_settings.get("pitch", 0)),
        audio_format=minimax_settings.get("audio_format", "mp3"),
    )


def run_workflow(
    inputs: WorkflowInputs,
    settings: dict[str, Any],
    progress: Callable[[str], None] | None = None,
) -> dict[str, str]:
    """执行完整工作流"""
    started_at = time.monotonic()
    progress = progress or (lambda _: None)
    output_dir = Path(inputs.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    print_log(
        "工作流开始",
        "Workflow started",
        viral_video=inputs.viral_video,
        source_video=inputs.source_video,
        output_dir=output_dir,
    )
    print_log(
        "配置状态",
        "Settings status",
        whisper_model=settings.get("whisper_model", ""),
        llm_api_key=_setting_status(settings.get("llm", {}).get("api_key")),
        llm_model=settings.get("llm", {}).get("model", ""),
        tts_provider=settings.get("tts_provider", "minimax"),
        minimax_api_key=_setting_status(settings.get("minimax", {}).get("api_key")),
        minimax_group_id=_setting_status(settings.get("minimax", {}).get("group_id")),
        minimax_voice_id=_setting_status(settings.get("minimax", {}).get("voice_id")),
        voxcpm_base_url=_setting_status(settings.get("voxcpm", {}).get("base_url")),
        voxcpm_voice=settings.get("voxcpm", {}).get("voice", ""),
        vad_model=settings.get("vad_model", default_vad_model()),
    )

    def step(zh: str, en: str):
        print_log(f"步骤开始: {zh}", f"Step started: {en}")
        progress(zh)

    def step_done(zh: str, en: str, **details):
        print_log(f"步骤完成: {zh}", f"Step completed: {en}", **details)

    # 步骤1: TTS分离
    step("TTS分离", "TTS extraction")
    vad_settings = settings.get("vad") or {}
    speaker_settings = settings.get("speaker") or {}
    asr_settings = settings.get("asr") or {}
    tts_result = run_tts_extraction(
        inputs.viral_video,
        settings["whisper_model"],
        output_dir / "tts",
        vad_model=settings.get("vad_model") or default_vad_model(),
        vad_threshold=float(vad_settings.get("threshold", 0.25)),
        min_speech_ms=int(vad_settings.get("min_speech_ms", 10)),
        min_silence_ms=int(vad_settings.get("min_silence_ms", 50)),
        demucs_model=settings.get("demucs_model", "htdemucs"),
        speaker_filter=bool(speaker_settings.get("enabled", True)),
        speaker_similarity_threshold=float(speaker_settings.get("similarity_threshold", 0.82)),
        speaker_threshold=float(asr_settings.get("speaker_threshold", 0.3)),
        hf_token=speaker_settings.get("hf_token", ""),
        pyannote_model=speaker_settings.get("pyannote_model", "pyannote/wespeaker-voxceleb-resnet34-LM"),
        asr_language=asr_settings.get("language", "en"),
        asr_prompt=asr_settings.get("prompt", ""),
        asr_max_len=int(asr_settings.get("max_len", 50)),
        asr_split_on_word=bool(asr_settings.get("split_on_word", True)),
        timing_offset_ms=int(asr_settings.get("timing_offset_ms", 820)),
    )
    step_done("TTS分离", "TTS extraction", srt=tts_result["srt_path"], entries=len(tts_result["entries"]))

    # 步骤2: 解说规划
    step("解说规划", "Narration planning")
    narration_beats_path = output_dir / "narration_beats.json"
    narration_beats = plan_narration_beats(
        tts_result["srt_path"],
        narration_beats_path,
        api_key=settings["llm"]["api_key"],
        model=settings["llm"]["model"],
        base_url=settings["llm"]["base_url"],
        target_language=inputs.target_language,
        style=inputs.rewrite_style or settings.get("rewrite_style", ""),
    )
    step_done("解说规划", "Narration planning", beats=len(narration_beats), output=narration_beats_path)

    # 步骤3: 镜头匹配
    step("镜头匹配", "Frame matching")
    frame_match_settings = settings.get("frame_match") or {}
    frame_match_engine = str(frame_match_settings.get("engine", "internal") or "internal").strip().lower()
    if frame_match_engine == "vmf":
        match_result = run_vmf_frame_match(
            inputs.viral_video,
            inputs.source_video,
            output_dir / "match",
            vmf_bin=frame_match_settings.get("vmf_bin", "/Users/chaiyapeng/Documents/autocopy/.venv/bin/vmf"),
            vmf_fps=float(frame_match_settings.get("fps", 3.0)),
            model=frame_match_settings.get("model", "dinov2_vits14"),
            device=frame_match_settings.get("device", "cpu"),
            batch_size=int(frame_match_settings.get("batch_size", 64)),
            inflight=int(frame_match_settings.get("inflight", 1)),
            padding_seconds=float(frame_match_settings.get("padding_seconds", 90.0)),
        )
    else:
        match_result = run_frame_match(
            inputs.viral_video,
            inputs.source_video,
            output_dir / "match",
        )
    step_done("镜头匹配", "Frame matching", matches=len(match_result["matches"]))

    # 步骤4: beat 级音频生成
    step("音频生成", "Audio generation")
    copy_text_path = write_copy_text(narration_beats, output_dir / "文案.txt")
    tts_provider = build_tts_provider(settings)
    audio_result = synthesize_narration_audio(
        narration_beats,
        output_dir / "audio",
        tts_provider,
    )
    step_done("音频生成", "Audio generation", segments=len(audio_result["voice_segments"]), copy_text=copy_text_path)

    # 步骤5: 导出剪映片段草稿
    step("导出剪映", "Jianying export")
    draft_path = create_jianying_clip_draft(
        inputs.viral_video,
        inputs.source_video,
        match_result["matches"],
        None,
        draft_name=f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{Path(inputs.viral_video).stem}_解说优先草稿",
        voice_segments=audio_result["voice_segments"],
        import_subtitles=False,
        source_volume=0.3,
        trim_voice_silence=False,
    )
    draft_copy_text = Path(draft_path) / "文案.txt"
    draft_copy_text.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(copy_text_path, draft_copy_text)
    print_log("复制文案到草稿", "Copied copy text into draft", output=draft_copy_text)
    step_done("导出剪映", "Jianying export", draft=draft_path)

    result = {
        "tts_srt": tts_result["srt_path"],
        "narration_beats": str(narration_beats_path),
        "copy_text": str(copy_text_path),
        "draft_copy_text": str(draft_copy_text),
        "match_result": str(output_dir / "match"),
        "audio": audio_result["timeline"],
        "audio_segments": str(output_dir / "audio"),
        "tts_result_manifest": audio_result.get("manifest", ""),
        "jianying_draft": str(draft_path),
    }
    print_log("工作流结束", "Workflow finished", seconds=f"{time.monotonic() - started_at:.1f}")
    return result
