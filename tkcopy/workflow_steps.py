"""Fixed TKCopy workflow stages.

This module owns the step order and the per-stage implementation. The public
entrypoint remains ``tkcopy.workflow.run_workflow``.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
import shutil
from typing import Any, Callable

from tkcopy.workflow_context import WorkflowContext, WorkflowStage
from tkcopy.workflow_logging import WorkflowLogger


TTS_EXTRACTION = WorkflowStage("tts_extraction", "TTS分离", "TTS extraction")
NARRATION_PLANNING = WorkflowStage("narration_planning", "解说规划", "Narration planning")
FRAME_MATCHING = WorkflowStage("frame_matching", "镜头匹配", "Frame matching")
AUDIO_GENERATION = WorkflowStage("audio_generation", "音频生成", "Audio generation")
JIANYING_EXPORT = WorkflowStage("jianying_export", "导出剪映", "Jianying export")

WORKFLOW_STAGES = (
    TTS_EXTRACTION,
    NARRATION_PLANNING,
    FRAME_MATCHING,
    AUDIO_GENERATION,
    JIANYING_EXPORT,
)


@dataclass
class WorkflowArtifacts:
    tts_result: dict[str, Any] = field(default_factory=dict)
    narration_beats: list[dict[str, Any]] = field(default_factory=list)
    match_result: dict[str, Any] = field(default_factory=dict)
    audio_result: dict[str, Any] = field(default_factory=dict)
    copy_text_path: Path | None = None
    draft_path: Path | None = None
    draft_copy_text: Path | None = None


@dataclass(frozen=True)
class WorkflowDependencies:
    run_tts_extraction: Callable[..., dict[str, Any]]
    plan_narration_beats: Callable[..., list[dict[str, Any]]]
    run_frame_match: Callable[..., dict[str, Any]]
    run_vmf_frame_match: Callable[..., dict[str, Any]]
    build_tts_provider: Callable[[dict[str, Any]], Any]
    synthesize_narration_audio: Callable[..., dict[str, Any]]
    write_copy_text: Callable[..., Path]
    create_jianying_clip_draft: Callable[..., Path]
    default_vad_model: Callable[[], str]
    default_draft_folder: Path
    copy_file: Callable[[str | Path, str | Path], Any] = shutil.copy2


def run_tts_extraction_step(
    context: WorkflowContext,
    artifacts: WorkflowArtifacts,
    deps: WorkflowDependencies,
    logger: WorkflowLogger,
) -> None:
    settings = context.settings
    vad_settings = settings.get("vad") or {}
    speaker_settings = settings.get("speaker") or {}
    asr_settings = settings.get("asr") or {}
    vad_model = settings.get("vad_model") or deps.default_vad_model()

    logger.stage_parameters(
        TTS_EXTRACTION,
        video=context.inputs.viral_video,
        output_dir=context.paths.tts_dir,
        whisper_model=settings["whisper_model"],
        vad_model=vad_model,
        vad_threshold=float(vad_settings.get("threshold", 0.25)),
        min_speech_ms=int(vad_settings.get("min_speech_ms", 10)),
        min_silence_ms=int(vad_settings.get("min_silence_ms", 50)),
        demucs_model=settings.get("demucs_model", "htdemucs"),
        speaker_filter=bool(speaker_settings.get("enabled", True)),
        speaker_similarity_threshold=float(speaker_settings.get("similarity_threshold", 0.82)),
        speaker_threshold=float(asr_settings.get("speaker_threshold", 0.3)),
        asr_language=asr_settings.get("language", "en"),
        asr_max_len=int(asr_settings.get("max_len", 50)),
        timing_offset_ms=int(asr_settings.get("timing_offset_ms", 820)),
    )

    artifacts.tts_result = deps.run_tts_extraction(
        context.inputs.viral_video,
        settings["whisper_model"],
        context.paths.tts_dir,
        vad_model=vad_model,
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
    logger.stage_artifact(
        TTS_EXTRACTION,
        srt=artifacts.tts_result["srt_path"],
        entries=len(artifacts.tts_result["entries"]),
    )


def run_narration_planning_step(
    context: WorkflowContext,
    artifacts: WorkflowArtifacts,
    deps: WorkflowDependencies,
    logger: WorkflowLogger,
) -> None:
    settings = context.settings
    style = context.inputs.rewrite_style or settings.get("rewrite_style", "")

    logger.stage_parameters(
        NARRATION_PLANNING,
        input_srt=artifacts.tts_result["srt_path"],
        output=context.paths.narration_beats_path,
        llm_model=settings["llm"]["model"],
        llm_base_url=settings["llm"]["base_url"],
        target_language=context.inputs.target_language,
        style_chars=len(style),
    )
    artifacts.narration_beats = deps.plan_narration_beats(
        artifacts.tts_result["srt_path"],
        context.paths.narration_beats_path,
        api_key=settings["llm"]["api_key"],
        model=settings["llm"]["model"],
        base_url=settings["llm"]["base_url"],
        target_language=context.inputs.target_language,
        style=style,
    )
    logger.stage_artifact(
        NARRATION_PLANNING,
        output=context.paths.narration_beats_path,
        beats=len(artifacts.narration_beats),
    )


def run_frame_matching_step(
    context: WorkflowContext,
    artifacts: WorkflowArtifacts,
    deps: WorkflowDependencies,
    logger: WorkflowLogger,
) -> None:
    settings = context.settings
    frame_match_settings = settings.get("frame_match") or {}
    engine = str(frame_match_settings.get("engine", "internal") or "internal").strip().lower()

    logger.stage_parameters(
        FRAME_MATCHING,
        engine=engine,
        viral_video=context.inputs.viral_video,
        source_video=context.inputs.source_video,
        output_dir=context.paths.match_dir,
        vmf_fps=float(frame_match_settings.get("fps", 3.0)),
        vmf_model=frame_match_settings.get("model", "dinov2_vits14"),
        vmf_device=frame_match_settings.get("device", "cpu"),
        vmf_batch_size=int(frame_match_settings.get("batch_size", 64)),
        vmf_inflight=int(frame_match_settings.get("inflight", 1)),
    )
    if engine == "vmf":
        artifacts.match_result = deps.run_vmf_frame_match(
            context.inputs.viral_video,
            context.inputs.source_video,
            context.paths.match_dir,
            vmf_fps=float(frame_match_settings.get("fps", 3.0)),
            model=frame_match_settings.get("model", "dinov2_vits14"),
            device=frame_match_settings.get("device", "cpu"),
            batch_size=int(frame_match_settings.get("batch_size", 64)),
            inflight=int(frame_match_settings.get("inflight", 1)),
            padding_seconds=float(frame_match_settings.get("padding_seconds", 90.0)),
        )
    else:
        artifacts.match_result = deps.run_frame_match(
            context.inputs.viral_video,
            context.inputs.source_video,
            context.paths.match_dir,
        )
    logger.stage_artifact(
        FRAME_MATCHING,
        output_dir=context.paths.match_dir,
        matches=len(artifacts.match_result["matches"]),
    )


def run_audio_generation_step(
    context: WorkflowContext,
    artifacts: WorkflowArtifacts,
    deps: WorkflowDependencies,
    logger: WorkflowLogger,
) -> None:
    provider_name = str(context.settings.get("tts_provider", "minimax") or "minimax")
    logger.stage_parameters(
        AUDIO_GENERATION,
        provider=provider_name,
        beats=len(artifacts.narration_beats),
        copy_text=context.paths.copy_text_path,
        audio_dir=context.paths.audio_dir,
    )
    artifacts.copy_text_path = deps.write_copy_text(
        artifacts.narration_beats,
        context.paths.copy_text_path,
    )
    tts_provider = deps.build_tts_provider(context.settings)
    artifacts.audio_result = deps.synthesize_narration_audio(
        artifacts.narration_beats,
        context.paths.audio_dir,
        tts_provider,
    )
    logger.stage_artifact(
        AUDIO_GENERATION,
        copy_text=artifacts.copy_text_path,
        segments=len(artifacts.audio_result["voice_segments"]),
        timeline=artifacts.audio_result.get("timeline", ""),
        manifest=artifacts.audio_result.get("manifest", ""),
    )


def run_jianying_export_step(
    context: WorkflowContext,
    artifacts: WorkflowArtifacts,
    deps: WorkflowDependencies,
    logger: WorkflowLogger,
) -> None:
    jianying_settings = context.settings.get("jianying") or {}
    draft_folder = jianying_settings.get("draft_folder") or deps.default_draft_folder
    draft_name = f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{Path(context.inputs.viral_video).stem}_解说优先草稿"

    logger.stage_parameters(
        JIANYING_EXPORT,
        draft_name=draft_name,
        draft_folder=draft_folder,
        matches=len(artifacts.match_result["matches"]),
        voice_segments=len(artifacts.audio_result["voice_segments"]),
        source_volume=0.3,
        trim_voice_silence=False,
        import_subtitles=False,
    )
    artifacts.draft_path = deps.create_jianying_clip_draft(
        context.inputs.viral_video,
        context.inputs.source_video,
        artifacts.match_result["matches"],
        None,
        draft_name=draft_name,
        draft_folder=draft_folder,
        voice_segments=artifacts.audio_result["voice_segments"],
        import_subtitles=False,
        source_volume=0.3,
        trim_voice_silence=False,
    )
    if artifacts.copy_text_path is None:
        raise ValueError("文案文件未生成 / Copy text was not generated")
    artifacts.draft_copy_text = Path(artifacts.draft_path) / "文案.txt"
    artifacts.draft_copy_text.parent.mkdir(parents=True, exist_ok=True)
    deps.copy_file(artifacts.copy_text_path, artifacts.draft_copy_text)
    logger.stage_artifact(
        JIANYING_EXPORT,
        draft=artifacts.draft_path,
        draft_copy_text=artifacts.draft_copy_text,
    )


STEP_RUNNERS: tuple[
    tuple[WorkflowStage, Callable[[WorkflowContext, WorkflowArtifacts, WorkflowDependencies, WorkflowLogger], None]],
    ...,
] = (
    (TTS_EXTRACTION, run_tts_extraction_step),
    (NARRATION_PLANNING, run_narration_planning_step),
    (FRAME_MATCHING, run_frame_matching_step),
    (AUDIO_GENERATION, run_audio_generation_step),
    (JIANYING_EXPORT, run_jianying_export_step),
)


def build_workflow_result(context: WorkflowContext, artifacts: WorkflowArtifacts) -> dict[str, str]:
    if artifacts.copy_text_path is None or artifacts.draft_copy_text is None or artifacts.draft_path is None:
        raise ValueError("工作流产物不完整 / Workflow artifacts are incomplete")
    return {
        "tts_srt": artifacts.tts_result["srt_path"],
        "narration_beats": str(context.paths.narration_beats_path),
        "copy_text": str(artifacts.copy_text_path),
        "draft_copy_text": str(artifacts.draft_copy_text),
        "match_result": str(context.paths.match_dir),
        "audio": artifacts.audio_result["timeline"],
        "audio_segments": str(context.paths.audio_dir),
        "tts_result_manifest": artifacts.audio_result.get("manifest", ""),
        "jianying_draft": str(artifacts.draft_path),
    }
