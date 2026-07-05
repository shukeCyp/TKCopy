"""VMF coarse matching plus local full-frame refinement."""
from __future__ import annotations

import csv
import hashlib
import json
import os
import time
from dataclasses import asdict
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import numpy as np
from scipy.spatial import cKDTree

from tkcopy.logging_utils import print_log
from tkcopy.utils.frame_matcher import (
    CANDIDATE_TOP_K,
    CHUNK_SECONDS,
    CandidateMatch,
    Match,
    _cached_source_features,
    _dimensions,
    _duration,
    _file_md5,
    _frame_count,
    _segments_to_clip_matches,
    _viral_features,
    _write_csv,
    build_segments,
    choose_temporal_matches,
    fill_gaps_by_extending_previous,
    get_video_fps,
)


DEFAULT_VMF_MODEL = "dinov2_vits14"
DEFAULT_VMF_FPS = 3.0
DEFAULT_SOURCE_PADDING_SECONDS = 90.0
REFINE_TOP_K = 60


def extract_coarse_source_windows(
    raw_results: list[dict[str, Any]],
    viral_path: str | Path,
    source_path: str | Path,
    *,
    source_duration: float,
    padding_seconds: float = DEFAULT_SOURCE_PADDING_SECONDS,
) -> list[tuple[float, float]]:
    """Extract source-video time windows from VMF results and merge overlaps."""
    viral = Path(viral_path).expanduser().resolve()
    source = Path(source_path).expanduser().resolve()
    windows: list[tuple[float, float]] = []
    for result in raw_results:
        a_path = Path(result.get("a", {}).get("path", "")).expanduser().resolve()
        b_path = Path(result.get("b", {}).get("path", "")).expanduser().resolve()
        if a_path == source and b_path == viral:
            source_key = "a_range"
        elif a_path == viral and b_path == source:
            source_key = "b_range"
        else:
            continue
        for segment in result.get("segments", []):
            source_range = segment.get(source_key) or []
            if len(source_range) != 2:
                continue
            start = max(0.0, float(source_range[0]) - padding_seconds)
            end = min(float(source_duration), float(source_range[1]) + padding_seconds)
            if end > start:
                windows.append((start, end))

    if not windows:
        return []
    windows.sort()
    merged = [windows[0]]
    for start, end in windows[1:]:
        previous_start, previous_end = merged[-1]
        if start <= previous_end:
            merged[-1] = (previous_start, max(previous_end, end))
        else:
            merged.append((start, end))
    return [(round(start, 6), round(end, 6)) for start, end in merged]


def run_vmf_frame_match(
    viral_video: str | Path,
    source_video: str | Path,
    output_dir: str | Path,
    *,
    vmf_fps: float = DEFAULT_VMF_FPS,
    model: str = DEFAULT_VMF_MODEL,
    device: str = "cpu",
    batch_size: int = 64,
    inflight: int = 1,
    padding_seconds: float = DEFAULT_SOURCE_PADDING_SECONDS,
) -> dict[str, Any]:
    """Run VMF at low FPS, then refine only the coarse source windows at full FPS."""
    started_at = time.monotonic()
    viral_path = Path(viral_video).expanduser().resolve()
    source_path = Path(source_video).expanduser().resolve()
    output_dir = Path(output_dir).expanduser().resolve()
    work_dir = output_dir / "work"
    coarse_dir = output_dir / "vmf_coarse"
    refine_dir = output_dir / "vmf_refine"
    work_dir.mkdir(parents=True, exist_ok=True)
    coarse_dir.mkdir(parents=True, exist_ok=True)
    refine_dir.mkdir(parents=True, exist_ok=True)

    print_log(
        "VMF 镜头匹配开始",
        "VMF frame match started",
        viral_video=viral_path,
        source_video=source_path,
        output_dir=output_dir,
        vmf_fps=vmf_fps,
    )
    viral_fps = get_video_fps(viral_path)
    source_fps = get_video_fps(source_path)
    viral_frames = _frame_count(viral_path, viral_fps)
    source_frames = _frame_count(source_path, source_fps)
    source_width, _ = _dimensions(source_path)
    source_duration = _duration(source_path)

    raw_results_path = coarse_dir / "vmf_results.json"
    raw_results = _run_vmf_scan(
        viral_path,
        source_path,
        coarse_dir,
        raw_results_path,
        vmf_fps=vmf_fps,
        model=model,
        device=device,
        batch_size=batch_size,
        inflight=inflight,
    )
    windows = extract_coarse_source_windows(
        raw_results,
        viral_path,
        source_path,
        source_duration=source_duration,
        padding_seconds=padding_seconds,
    )
    if not windows:
        raise RuntimeError("VMF 没有找到粗匹配窗口 / VMF found no coarse source windows")
    windows_path = coarse_dir / "source_windows.json"
    windows_path.write_text(json.dumps(windows, ensure_ascii=False, indent=2), encoding="utf-8")
    print_log("VMF 粗匹配窗口", "VMF coarse source windows", windows=len(windows), path=windows_path)

    cache_key = _windows_cache_key(source_path, windows)
    cache_dir = output_dir / "source_cache" / _file_md5(source_path) / cache_key
    frame_matches = _find_matches_in_windows(
        viral_path,
        source_path,
        source_fps,
        source_width,
        cache_dir,
        windows,
    )
    matches_csv = work_dir / "matches.csv"
    _write_csv(frame_matches, matches_csv)

    raw_segments = build_segments(frame_matches)
    if not raw_segments:
        raise RuntimeError("VMF 精修后没有可用镜头片段 / VMF refine found no matched segments")
    raw_segments_json = work_dir / "raw_segments.json"
    raw_segments_json.write_text(
        json.dumps([asdict(segment) | {"frame_count": segment.frame_count} for segment in raw_segments], indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    segments = fill_gaps_by_extending_previous(raw_segments)
    clip_matches = _segments_to_clip_matches(segments, viral_fps, source_fps)
    segments_json = work_dir / "segments.json"
    segments_json.write_text(json.dumps(clip_matches, indent=2, ensure_ascii=False), encoding="utf-8")

    summary = {
        "engine": "vmf_coarse_refine",
        "segment_count": len(segments),
        "segment_frames": sum(segment.frame_count for segment in segments),
        "viral_frames": viral_frames,
        "source_frames": source_frames,
        "output_dir": str(output_dir),
        "viral": str(viral_path),
        "source": str(source_path),
        "vmf_results": str(raw_results_path),
        "source_windows": str(windows_path),
        "source_cache": str(cache_dir),
        "segments": str(segments_json),
        "raw_segments": str(raw_segments_json),
        "matches_csv": str(matches_csv),
        "seconds": round(time.monotonic() - started_at, 3),
    }
    (work_dir / "verify_summary.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    print_log(
        "VMF 镜头匹配结束",
        "VMF frame match finished",
        matches=len(clip_matches),
        segment_frames=summary["segment_frames"],
        coverage=f"{summary['segment_frames'] / max(1, viral_frames):.3f}",
        seconds=summary["seconds"],
    )
    return summary | {"matches": clip_matches}


def _run_vmf_scan(
    viral_path: Path,
    source_path: Path,
    coarse_dir: Path,
    output_json: Path,
    *,
    vmf_fps: float,
    model: str,
    device: str,
    batch_size: int,
    inflight: int,
) -> list[dict[str, Any]]:
    data_dir = coarse_dir / "index"
    print_log(
        "执行内置 VMF 3fps 粗匹配",
        "Running embedded VMF coarse match",
        viral_video=viral_path,
        source_video=source_path,
        data_dir=data_dir,
        output_json=output_json,
        fps=vmf_fps,
        model=model,
        device=device,
        batch_size=batch_size,
        inflight=inflight,
    )
    try:
        _prepare_vmf_runtime_env()
        vmf = _load_embedded_vmf()
        cfg = vmf.Config()
        cfg.data_dir = data_dir
        cfg.fps = vmf_fps
        cfg.model = model
        cfg.device = device
        cfg.batch_size = batch_size
        cfg.encode_inflight = inflight
        cfg.cropdetect = False
        cfg.mirror = False
        cfg.use_smooth = False
        cfg.ensure_dirs()
        store = vmf.Store(cfg.data_dir)
        extractor = vmf.ensure_extractor(cfg)
        vmf.index_paths([viral_path, source_path], cfg, store, extractor)
        results = vmf.find_pairs(cfg, store)
        output_json.parent.mkdir(parents=True, exist_ok=True)
        output_json.write_text(vmf.to_json(results), encoding="utf-8")
    except Exception as exc:
        raise RuntimeError(f"VMF 粗匹配失败 / VMF coarse match failed: {exc}") from exc
    return json.loads(output_json.read_text(encoding="utf-8"))


def _find_matches_in_windows(
    viral_path: Path,
    source_path: Path,
    source_fps: float,
    source_width: int,
    cache_dir: Path,
    windows: list[tuple[float, float]],
) -> list[Match]:
    print_log("提取爆款逐帧特征", "Extracting full-FPS viral features", video=viral_path)
    viral_feature_rows = _viral_features(viral_path)
    candidates_by_frame: dict[int, list[CandidateMatch]] = {index: [] for index in range(len(viral_feature_rows))}
    chunks = _window_chunks(windows)
    for window_index, (start, length) in enumerate(chunks):
        source_features, meta = _cached_source_features(
            source_path,
            start,
            length,
            source_fps,
            source_width,
            cache_dir,
            window_index,
            len(chunks),
        )
        if len(source_features) == 0:
            continue
        source_frames, crop_xs, flipped = meta
        top_k = min(max(CANDIDATE_TOP_K, REFINE_TOP_K), len(source_features))
        print_log(
            "查询精修候选",
            "Querying refine candidates",
            chunk=f"{window_index + 1}/{len(chunks)}",
            source_features=len(source_features),
            top_k=top_k,
        )
        distances, indexes = cKDTree(source_features).query(viral_feature_rows, k=top_k, workers=-1)
        if top_k == 1:
            distances = distances[:, None]
            indexes = indexes[:, None]
        for viral_frame, (distance_row, index_row) in enumerate(zip(distances, indexes)):
            for distance, index in zip(distance_row, index_row):
                source_index = int(index)
                candidates_by_frame[viral_frame].append(
                    CandidateMatch(
                        viral_frame,
                        int(source_frames[source_index]),
                        float(distance),
                        int(crop_xs[source_index]),
                        bool(flipped[source_index]),
                    )
                )
    matches = choose_temporal_matches(candidates_by_frame)
    if not matches:
        raise RuntimeError("VMF 精修没有找到逐帧匹配 / VMF refine found no frame matches")
    return matches


def _window_chunks(windows: list[tuple[float, float]]) -> list[tuple[float, float]]:
    chunks: list[tuple[float, float]] = []
    for start, end in windows:
        cursor = start
        while cursor < end:
            length = min(float(CHUNK_SECONDS), end - cursor)
            if length > 0:
                chunks.append((cursor, length))
            cursor += length
    return chunks


def _prepare_vmf_runtime_env() -> None:
    os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"
    os.environ["OMP_NUM_THREADS"] = "1"
    os.environ["MKL_NUM_THREADS"] = "1"
    os.environ["VECLIB_MAXIMUM_THREADS"] = "1"
    os.environ["OPENBLAS_NUM_THREADS"] = "1"
    os.environ["NUMEXPR_NUM_THREADS"] = "1"


def _load_embedded_vmf() -> SimpleNamespace:
    try:
        from vmf.config import Config
        from vmf.index import Store
        from vmf.pipeline import ensure_extractor, find_pairs, index_paths
        from vmf.ui import to_json
    except Exception as exc:
        raise RuntimeError("内置 VMF 依赖不可用 / embedded VMF dependency is unavailable") from exc
    return SimpleNamespace(
        Config=Config,
        Store=Store,
        ensure_extractor=ensure_extractor,
        index_paths=index_paths,
        find_pairs=find_pairs,
        to_json=to_json,
    )


def _windows_cache_key(source_path: Path, windows: list[tuple[float, float]]) -> str:
    payload = json.dumps({"source": str(source_path), "windows": windows}, sort_keys=True)
    return hashlib.md5(payload.encode("utf-8")).hexdigest()
