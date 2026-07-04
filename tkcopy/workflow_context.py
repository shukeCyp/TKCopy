"""Workflow data structures shared by the TKCopy orchestration layer."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class WorkflowInputs:
    viral_video: str | Path
    source_video: str | Path
    output_dir: str | Path
    rewrite_style: str = ""
    target_language: str = "English"


@dataclass(frozen=True)
class WorkflowStage:
    key: str
    zh: str
    en: str


@dataclass(frozen=True)
class WorkflowPaths:
    output_dir: Path
    tts_dir: Path
    narration_beats_path: Path
    match_dir: Path
    audio_dir: Path
    copy_text_path: Path

    @classmethod
    def from_output_dir(cls, output_dir: str | Path) -> "WorkflowPaths":
        root = Path(output_dir)
        return cls(
            output_dir=root,
            tts_dir=root / "tts",
            narration_beats_path=root / "narration_beats.json",
            match_dir=root / "match",
            audio_dir=root / "audio",
            copy_text_path=root / "文案.txt",
        )


@dataclass(frozen=True)
class WorkflowContext:
    inputs: WorkflowInputs
    settings: dict[str, Any]
    paths: WorkflowPaths
