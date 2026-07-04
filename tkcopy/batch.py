"""Batch workflow helpers for directory-based TKCopy jobs."""
from __future__ import annotations

from copy import deepcopy
from pathlib import Path
import re
from typing import Any, Callable

from tkcopy.logging_utils import print_log
from tkcopy.workflow import WorkflowInputs, run_workflow


VIDEO_EXTENSIONS = {".mp4", ".mkv", ".mov", ".avi", ".m4v", ".webm"}
VIRAL_NAME_HINTS = ("对标", "爆款", "viral", "hot", "copy")
SOURCE_NAME_HINTS = ("原片", "source", "movie", "episode")


def scan_batch_cases(root_dir: str | Path, voice_split_count: int = 5) -> list[dict[str, Any]]:
    """Scan a root directory and pair each child folder's viral/source videos."""
    root = Path(root_dir).expanduser()
    if not root.exists():
        raise FileNotFoundError(f"批量目录不存在 / Batch root not found: {root}")

    case_dirs = _case_directories(root)
    cases: list[dict[str, Any]] = []
    ready_index = 0
    for case_dir in case_dirs:
        videos = sorted(
            [path for path in case_dir.iterdir() if path.is_file() and path.suffix.lower() in VIDEO_EXTENSIONS],
            key=_natural_sort_key,
        )
        viral_video, source_video = _choose_video_pair(videos)
        enabled = bool(viral_video and source_video)
        if enabled:
            ready_index += 1
        voice = "Natasha" if max(0, ready_index - 1) < voice_split_count else "Alex"
        cases.append(
            {
                "id": case_dir.name,
                "directory": str(case_dir),
                "viral_video": str(viral_video) if viral_video else "",
                "source_video": str(source_video) if source_video else "",
                "voice": voice,
                "enabled": enabled,
                "status": "ready" if enabled else "incomplete",
                "video_count": len(videos),
            }
        )

    print_log("批量目录扫描完成", "Batch directory scan completed", root=root, cases=len(cases))
    return cases


def run_batch_workflows(
    cases: list[dict[str, Any]],
    settings: dict[str, Any],
    output_root: str | Path,
    *,
    rewrite_style: str = "",
    target_language: str = "English",
    progress: Callable[[dict[str, Any]], None] | None = None,
) -> dict[str, Any]:
    """Run ready batch cases sequentially and keep going after per-case failures."""
    progress = progress or (lambda _: None)
    output_root = Path(output_root).expanduser()
    output_root.mkdir(parents=True, exist_ok=True)
    enabled_cases = [case for case in cases if case.get("enabled", True)]
    results: list[dict[str, Any]] = []

    print_log("批量工作流开始", "Batch workflow started", cases=len(enabled_cases), output_root=output_root)
    for index, case in enumerate(enabled_cases, 1):
        case_id = str(case.get("id") or index)
        voice = str(case.get("voice") or settings.get("voxcpm", {}).get("voice") or "Natasha")
        case_output_dir = output_root / f"case_{index:02d}_{_safe_name(voice)}_{_safe_name(case_id)}"
        case_settings = deepcopy(settings)
        case_settings.setdefault("tts_provider", "voxcpm")
        case_settings.setdefault("voxcpm", {})
        case_settings["voxcpm"]["voice"] = voice
        event_base = {"index": index, "total": len(enabled_cases), "case_id": case_id, "voice": voice}
        progress({"event": "case_started", **event_base, "output_dir": str(case_output_dir)})
        print_log("批量案例开始", "Batch case started", **event_base, output_dir=case_output_dir)

        try:
            workflow_result = run_workflow(
                WorkflowInputs(
                    viral_video=case["viral_video"],
                    source_video=case["source_video"],
                    output_dir=case_output_dir,
                    rewrite_style=rewrite_style,
                    target_language=target_language,
                ),
                case_settings,
                lambda step: progress({"event": "case_step", **event_base, "step": step}),
            )
            case_result = {
                "ok": True,
                **event_base,
                "output_dir": str(case_output_dir),
                "jianying_draft": workflow_result.get("jianying_draft", ""),
                "copy_text": workflow_result.get("copy_text", ""),
            }
            progress({"event": "case_completed", **case_result})
            print_log("批量案例完成", "Batch case completed", **event_base, draft=case_result["jianying_draft"])
        except Exception as exc:
            case_result = {
                "ok": False,
                **event_base,
                "output_dir": str(case_output_dir),
                "error": str(exc),
            }
            progress({"event": "case_failed", **case_result})
            print_log("批量案例失败", "Batch case failed", **event_base, error=exc)
        results.append(case_result)

    summary = {
        "ok": all(result["ok"] for result in results),
        "output_root": str(output_root),
        "cases": results,
    }
    progress({"event": "batch_finished", **summary})
    print_log("批量工作流结束", "Batch workflow finished", output_root=output_root, cases=len(results), ok=summary["ok"])
    return summary


def _case_directories(root: Path) -> list[Path]:
    videos = [path for path in root.iterdir() if path.is_file() and path.suffix.lower() in VIDEO_EXTENSIONS]
    if videos:
        return [root]
    return sorted([path for path in root.iterdir() if path.is_dir()], key=lambda path: _natural_sort_key(path.name))


def _choose_video_pair(videos: list[Path]) -> tuple[Path | None, Path | None]:
    if len(videos) < 2:
        return None, None

    viral = _first_by_name_hint(videos, VIRAL_NAME_HINTS)
    if not viral:
        viral = _first_by_extension(videos, {".mp4", ".mov", ".m4v"}) or videos[0]

    source_candidates = [video for video in videos if video != viral]
    source = _first_by_name_hint(source_candidates, SOURCE_NAME_HINTS)
    if not source:
        source = _first_by_extension(source_candidates, {".mkv"}) or source_candidates[0]
    return viral, source


def _first_by_name_hint(videos: list[Path], hints: tuple[str, ...]) -> Path | None:
    for video in videos:
        lowered = video.name.lower()
        if any(hint.lower() in lowered for hint in hints):
            return video
    return None


def _first_by_extension(videos: list[Path], extensions: set[str]) -> Path | None:
    for video in videos:
        if video.suffix.lower() in extensions:
            return video
    return None


def _natural_sort_key(value: str | Path) -> list[Any]:
    text = str(value)
    return [int(part) if part.isdigit() else part.lower() for part in re.split(r"(\d+)", text)]


def _safe_name(value: str) -> str:
    cleaned = re.sub(r"[^\w\u4e00-\u9fff.-]+", "_", value.strip())
    return cleaned.strip("._") or "case"
