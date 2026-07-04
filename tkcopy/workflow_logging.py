"""Structured bilingual logging for the fixed TKCopy workflow."""
from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

from tkcopy.logging_utils import print_log
from tkcopy.workflow_context import WorkflowInputs, WorkflowStage


PrintLog = Callable[[str, str], None]


def setting_status(value: Any) -> str:
    return "SET" if str(value or "").strip() else "EMPTY"


class WorkflowLogger:
    def __init__(self, print_fn: Callable[..., None] = print_log):
        self.print_fn = print_fn

    def workflow_started(self, inputs: WorkflowInputs, output_dir: str | Path) -> None:
        self.print_fn(
            "工作流开始",
            "Workflow started",
            viral_video=inputs.viral_video,
            source_video=inputs.source_video,
            output_dir=output_dir,
            target_language=inputs.target_language,
        )

    def settings_status(self, settings: dict[str, Any], *, vad_model: str) -> None:
        self.print_fn(
            "配置状态",
            "Settings status",
            whisper_model=settings.get("whisper_model", ""),
            llm_api_key=setting_status(settings.get("llm", {}).get("api_key")),
            llm_model=settings.get("llm", {}).get("model", ""),
            tts_provider=settings.get("tts_provider", "minimax"),
            minimax_api_key=setting_status(settings.get("minimax", {}).get("api_key")),
            minimax_group_id=setting_status(settings.get("minimax", {}).get("group_id")),
            minimax_voice_id=setting_status(settings.get("minimax", {}).get("voice_id")),
            voxcpm_base_url=setting_status(settings.get("voxcpm", {}).get("base_url")),
            voxcpm_voice=settings.get("voxcpm", {}).get("voice", ""),
            vad_model=vad_model,
        )

    def stage_started(self, stage: WorkflowStage, **details: Any) -> None:
        self.print_fn(
            f"步骤开始: {stage.zh}",
            f"Step started: {stage.en}",
            stage=stage.key,
            **details,
        )

    def stage_parameters(self, stage: WorkflowStage, **details: Any) -> None:
        self.print_fn(
            f"步骤参数: {stage.zh}",
            f"Step parameters: {stage.en}",
            stage=stage.key,
            **details,
        )

    def stage_artifact(self, stage: WorkflowStage, **details: Any) -> None:
        self.print_fn(
            f"步骤产物: {stage.zh}",
            f"Step artifact: {stage.en}",
            stage=stage.key,
            **details,
        )

    def stage_completed(self, stage: WorkflowStage, **details: Any) -> None:
        self.print_fn(
            f"步骤完成: {stage.zh}",
            f"Step completed: {stage.en}",
            stage=stage.key,
            **details,
        )

    def stage_failed(self, stage: WorkflowStage, error: Exception, **details: Any) -> None:
        self.print_fn(
            f"步骤失败: {stage.zh}",
            f"Step failed: {stage.en}",
            stage=stage.key,
            error=error,
            **details,
        )

    def workflow_finished(self, seconds: str | float) -> None:
        self.print_fn("工作流结束", "Workflow finished", seconds=seconds)
