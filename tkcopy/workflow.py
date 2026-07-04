"""工作流编排 - 固定步骤执行完整复刻流程"""
from __future__ import annotations

from pathlib import Path
import time
from typing import Any, Callable

from tkcopy.workflow_context import WorkflowContext, WorkflowInputs, WorkflowPaths
from tkcopy.workflow_logging import WorkflowLogger, setting_status as _setting_status
from tkcopy.workflow_steps import (
    STEP_RUNNERS,
    WorkflowArtifacts,
    WorkflowDependencies,
    build_workflow_result,
)
from tkcopy.utils.tts_extractor import run_tts_extraction
from tkcopy.utils.script_planner import plan_narration_beats
from tkcopy.utils.frame_matcher import run_frame_match
from tkcopy.utils.vmf_frame_matcher import run_vmf_frame_match
from tkcopy.utils.tts_provider import MiniMaxTTSProvider, VoxCPMTTSProvider, synthesize_narration_audio
from tkcopy.utils.copy_text import write_copy_text
from tkcopy.utils.video_composer import compose_video
from tkcopy.utils.jianying_export import DEFAULT_DRAFT_FOLDER, create_jianying_clip_draft


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


def _build_dependencies() -> WorkflowDependencies:
    return WorkflowDependencies(
        run_tts_extraction=run_tts_extraction,
        plan_narration_beats=plan_narration_beats,
        run_frame_match=run_frame_match,
        run_vmf_frame_match=run_vmf_frame_match,
        build_tts_provider=build_tts_provider,
        synthesize_narration_audio=synthesize_narration_audio,
        write_copy_text=write_copy_text,
        create_jianying_clip_draft=create_jianying_clip_draft,
        default_vad_model=default_vad_model,
        default_draft_folder=DEFAULT_DRAFT_FOLDER,
    )


def run_workflow(
    inputs: WorkflowInputs,
    settings: dict[str, Any],
    progress: Callable[[str], None] | None = None,
) -> dict[str, str]:
    """执行完整工作流。"""
    started_at = time.monotonic()
    progress = progress or (lambda _: None)
    paths = WorkflowPaths.from_output_dir(inputs.output_dir)
    paths.output_dir.mkdir(parents=True, exist_ok=True)
    context = WorkflowContext(inputs=inputs, settings=settings, paths=paths)
    artifacts = WorkflowArtifacts()
    deps = _build_dependencies()
    logger = WorkflowLogger()

    logger.workflow_started(inputs, paths.output_dir)
    logger.settings_status(settings, vad_model=settings.get("vad_model") or default_vad_model())

    for stage, runner in STEP_RUNNERS:
        logger.stage_started(stage)
        progress(stage.zh)
        try:
            runner(context, artifacts, deps, logger)
        except Exception as exc:
            logger.stage_failed(stage, exc, output_dir=paths.output_dir)
            raise
        logger.stage_completed(stage, **_stage_completion_details(stage.key, artifacts, paths))

    result = build_workflow_result(context, artifacts)
    logger.workflow_finished(seconds=f"{time.monotonic() - started_at:.1f}")
    return result


def _stage_completion_details(
    stage_key: str,
    artifacts: WorkflowArtifacts,
    paths: WorkflowPaths,
) -> dict[str, Any]:
    if stage_key == "tts_extraction":
        return {
            "srt": artifacts.tts_result.get("srt_path", ""),
            "entries": len(artifacts.tts_result.get("entries", [])),
        }
    if stage_key == "narration_planning":
        return {
            "beats": len(artifacts.narration_beats),
            "output": paths.narration_beats_path,
        }
    if stage_key == "frame_matching":
        return {
            "matches": len(artifacts.match_result.get("matches", [])),
        }
    if stage_key == "audio_generation":
        return {
            "segments": len(artifacts.audio_result.get("voice_segments", [])),
            "copy_text": artifacts.copy_text_path or "",
        }
    if stage_key == "jianying_export":
        return {
            "draft": artifacts.draft_path or "",
        }
    return {}
