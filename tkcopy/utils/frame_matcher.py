"""镜头匹配工具 - 匹配爆款视频与源电影镜头"""
from __future__ import annotations

import csv
import hashlib
import json
import subprocess
from dataclasses import asdict, dataclass
from fractions import Fraction
from pathlib import Path
from typing import Iterable

import numpy as np
from scipy.spatial import cKDTree

from tkcopy.logging_utils import print_log


CHUNK_SECONDS = 180
CROP_STEP = 40
FEATURE_SIZE = 18
SCORE_PERCENTILE = 99
MIN_FRAMES = 1
MIN_SEGMENT_FRAMES = 12
CANDIDATE_TOP_K = 20
MAX_CANDIDATES_PER_FRAME = 160
SHORT_SEGMENT_FRAMES = 30
TINY_SEGMENT_FRAMES = 3
BAD_SHORT_SEGMENT_SCORE = 13.0
BAD_SEGMENT_SCORE = 14.5
OFFSET_TOLERANCE = 10
CROP_TOLERANCE = 400
SHORT_OFFSET_TOLERANCE = 120
SOURCE_CACHE_DIR = "source_cache"


@dataclass(frozen=True)
class Match:
    viral_frame: int
    source_frame: int
    score: float
    crop_x: int
    flipped: bool


@dataclass(frozen=True)
class CandidateMatch:
    viral_frame: int
    source_frame: int
    score: float
    crop_x: int
    flipped: bool


@dataclass(frozen=True)
class Segment:
    viral_start: int
    viral_end: int
    source_start: int
    source_end: int
    crop_x: int
    flipped: bool
    avg_score: float
    max_score: float

    @property
    def frame_count(self) -> int:
        return self.viral_end - self.viral_start + 1


def _run(cmd: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)


def _ffprobe_stream(path: Path, entry: str) -> str:
    result = _run(
        [
            "ffprobe",
            "-v",
            "error",
            "-select_streams",
            "v:0",
            "-show_entries",
            f"stream={entry}",
            "-of",
            "default=nokey=1:noprint_wrappers=1",
            str(path),
        ]
    )
    return result.stdout.decode().strip()


def _ffprobe_format(path: Path, entry: str) -> str:
    result = _run(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            f"format={entry}",
            "-of",
            "default=nokey=1:noprint_wrappers=1",
            str(path),
        ]
    )
    return result.stdout.decode().strip()


def get_video_fps(video_path: str | Path) -> float:
    """获取视频帧率。"""
    path = Path(video_path).expanduser().resolve()
    value = _ffprobe_stream(path, "avg_frame_rate") or _ffprobe_stream(path, "r_frame_rate")
    fps = float(Fraction(value))
    print_log("读取视频帧率", "Read video FPS", video=path, fps=f"{fps:.3f}")
    return fps


def _duration(path: Path) -> float:
    value = _ffprobe_stream(path, "duration")
    if value and value != "N/A":
        return float(value)
    value = _ffprobe_format(path, "duration")
    return float(value) if value and value != "N/A" else 0.0


def _frame_count(path: Path, fallback_fps: float) -> int:
    value = _ffprobe_stream(path, "nb_frames")
    return int(value) if value and value != "N/A" else round(_duration(path) * fallback_fps)


def _dimensions(path: Path) -> tuple[int, int]:
    return int(_ffprobe_stream(path, "width")), int(_ffprobe_stream(path, "height"))


def _file_md5(path: Path) -> str:
    digest = hashlib.md5()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _source_cache_dir(source_path: Path, output_dir: Path) -> Path:
    return output_dir / SOURCE_CACHE_DIR / _file_md5(source_path)


def _read_scaled_gray(
    path: Path,
    width: int,
    height: int,
    start_sec: float | None = None,
    duration_sec: float | None = None,
    frames: int | None = None,
) -> np.ndarray:
    cmd = ["ffmpeg", "-hide_banner", "-loglevel", "error"]
    if start_sec is not None:
        cmd += ["-ss", f"{start_sec:.9f}"]
    cmd += ["-i", str(path)]
    if duration_sec is not None:
        cmd += ["-t", f"{duration_sec:.9f}"]
    if frames is not None:
        cmd += ["-frames:v", str(frames)]
    cmd += [
        "-vf",
        f"scale={width}:{height}:flags=bicubic,format=gray",
        "-f",
        "rawvideo",
        "-pix_fmt",
        "gray",
        "-",
    ]
    result = _run(cmd)
    raw = np.frombuffer(result.stdout, dtype=np.uint8)
    frame_size = width * height
    usable = (raw.size // frame_size) * frame_size
    return raw[:usable].reshape((-1, height, width))


def _block_mean(frames: np.ndarray, out_size: int) -> np.ndarray:
    frame_count, height, width = frames.shape
    block_y = height // out_size
    block_x = width // out_size
    return frames[:, : block_y * out_size, : block_x * out_size].reshape(
        frame_count,
        out_size,
        block_y,
        out_size,
        block_x,
    ).mean(axis=(2, 4))


def _normalize(features: np.ndarray) -> np.ndarray:
    features = features.astype(np.float32, copy=False)
    features -= features.mean(axis=1, keepdims=True)
    features /= np.maximum(features.std(axis=1, keepdims=True), 1.0)
    return features


def _viral_features(path: Path) -> np.ndarray:
    frames = _read_scaled_gray(path, 108, 108)
    if len(frames) == 0:
        raise RuntimeError(f"无法读取爆款视频帧 / Could not read viral frames: {path}")
    small = _block_mean(frames, FEATURE_SIZE)
    return _normalize(small.reshape((small.shape[0], -1)))


def _source_features(
    path: Path,
    start_sec: float,
    duration_sec: float,
    source_fps: float,
    source_width: int,
) -> tuple[np.ndarray, list[tuple[int, int, bool]]]:
    scaled_width = 192
    scaled_height = 108
    frames = _read_scaled_gray(path, scaled_width, scaled_height, start_sec, duration_sec)
    if len(frames) == 0:
        return np.empty((0, FEATURE_SIZE * FEATURE_SIZE), dtype=np.float32), []

    scaled_crop_width = scaled_height
    max_scaled_x = scaled_width - scaled_crop_width
    scale_ratio = source_width / scaled_width
    scaled_step = max(1, round(CROP_STEP / scale_ratio))
    scaled_xs = list(range(0, max_scaled_x + 1, scaled_step))
    if scaled_xs[-1] != max_scaled_x:
        scaled_xs.append(max_scaled_x)

    chunks: list[np.ndarray] = []
    meta: list[tuple[int, int, bool]] = []
    source_start_frame = round(start_sec * source_fps)
    for scaled_x in scaled_xs:
        original_x = max(0, round(scaled_x * scale_ratio))
        crop = frames[:, :, scaled_x : scaled_x + scaled_crop_width]
        for flipped in (False, True):
            work = crop[:, :, ::-1] if flipped else crop
            small = _block_mean(work, FEATURE_SIZE)
            chunks.append(small.reshape((small.shape[0], -1)))
            meta.extend((source_start_frame + index, original_x, flipped) for index in range(frames.shape[0]))
    return _normalize(np.vstack(chunks)), meta


def _cached_source_features(
    path: Path,
    start_sec: float,
    duration_sec: float,
    source_fps: float,
    source_width: int,
    cache_dir: Path,
    window: int,
    windows: int,
) -> tuple[np.ndarray, tuple[np.ndarray, np.ndarray, np.ndarray]]:
    cache_dir.mkdir(parents=True, exist_ok=True)
    meta_path = cache_dir / "meta.json"
    expected_meta = {
        "fps": source_fps,
        "chunk_seconds": CHUNK_SECONDS,
        "crop_step": CROP_STEP,
        "feature_size": FEATURE_SIZE,
        "source_width": source_width,
        "windows": windows,
    }
    if meta_path.exists() and json.loads(meta_path.read_text(encoding="utf-8")) != expected_meta:
        for old_window in cache_dir.glob("window_*.npz"):
            old_window.unlink()
    if not meta_path.exists() or json.loads(meta_path.read_text(encoding="utf-8")) != expected_meta:
        meta_path.write_text(json.dumps(expected_meta, indent=2, ensure_ascii=False), encoding="utf-8")

    feature_path = cache_dir / f"window_{window:04d}.npz"
    if feature_path.exists():
        print_log("读取源片特征缓存", "Loading source feature cache", window=f"{window + 1}/{windows}", path=feature_path)
        data = np.load(feature_path)
        return data["features"], (data["source_frames"], data["crop_xs"], data["flipped"])

    print_log(
        "构建源片特征缓存",
        "Building source feature cache",
        window=f"{window + 1}/{windows}",
        start=f"{start_sec:.1f}s",
        duration=f"{duration_sec:.1f}s",
    )
    features, meta = _source_features(path, start_sec, duration_sec, source_fps, source_width)
    source_frames = np.array([item[0] for item in meta], dtype=np.int32)
    crop_xs = np.array([item[1] for item in meta], dtype=np.int16)
    flipped = np.array([item[2] for item in meta], dtype=np.bool_)
    np.savez(feature_path, features=features, source_frames=source_frames, crop_xs=crop_xs, flipped=flipped)
    return features, (source_frames, crop_xs, flipped)


def choose_temporal_matches(candidates_by_frame: dict[int, list[CandidateMatch]]) -> list[Match]:
    """Choose per-frame matches while preserving local timeline continuity."""
    frames = sorted(candidates_by_frame)
    chosen: list[CandidateMatch] = []
    previous: CandidateMatch | None = None
    for frame in frames:
        candidates = sorted(candidates_by_frame[frame], key=lambda item: item.score)[:MAX_CANDIDATES_PER_FRAME]
        if not candidates:
            continue
        best = candidates[0]
        if previous is None:
            chosen.append(best)
            previous = best
            continue

        viral_step = frame - previous.viral_frame
        continuous = [
            candidate
            for candidate in candidates
            if abs((candidate.source_frame - previous.source_frame) - viral_step) <= OFFSET_TOLERANCE
            and abs(candidate.crop_x - previous.crop_x) <= CROP_TOLERANCE
            and candidate.flipped == previous.flipped
        ]
        if continuous and continuous[0].score <= best.score + 2.5:
            best = continuous[0]
        chosen.append(best)
        previous = best
    return [Match(item.viral_frame, item.source_frame, item.score, item.crop_x, item.flipped) for item in chosen]


def find_matches(viral_path: Path, source_path: Path, source_fps: float, source_width: int, cache_dir: Path) -> list[Match]:
    print_log("提取爆款帧特征", "Extracting viral frame features", video=viral_path)
    viral_feature_rows = _viral_features(viral_path)
    candidates_by_frame: dict[int, list[CandidateMatch]] = {index: [] for index in range(len(viral_feature_rows))}
    total = _duration(source_path)
    windows = max(1, int(np.ceil(total / CHUNK_SECONDS)))

    for window in range(windows):
        start = window * CHUNK_SECONDS
        length = min(CHUNK_SECONDS, total - start) if total else CHUNK_SECONDS
        source_features, meta = _cached_source_features(
            source_path,
            start,
            length,
            source_fps,
            source_width,
            cache_dir,
            window,
            windows,
        )
        if len(source_features) == 0:
            continue
        source_frames, crop_xs, flipped = meta
        top_k = min(CANDIDATE_TOP_K, len(source_features))
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
        raise RuntimeError("没有找到镜头匹配 / No frame matches found")
    return matches


def build_segments(matches: Iterable[Match]) -> list[Segment]:
    matches = list(matches)
    if not matches:
        return []

    threshold = float(np.percentile([match.score for match in matches], SCORE_PERCENTILE))
    print_log("镜头匹配分数阈值", "Frame match score threshold", threshold=f"{threshold:.3f}")
    segments: list[Segment] = []
    current: list[Match] = []

    def median_offset(items: list[Match]) -> int:
        return int(round(float(np.median([match.source_frame - match.viral_frame for match in items]))))

    def flush() -> None:
        if len(current) < MIN_FRAMES:
            return
        offset = median_offset(current)
        scores = [match.score for match in current]
        crop_x = int(round(float(np.median([match.crop_x for match in current]))))
        segments.append(
            Segment(
                current[0].viral_frame,
                current[-1].viral_frame,
                current[0].viral_frame + offset,
                current[-1].viral_frame + offset,
                crop_x,
                current[0].flipped,
                float(np.mean(scores)),
                float(np.max(scores)),
            )
        )

    for match in matches:
        if match.score > threshold:
            flush()
            current = []
            continue
        if not current:
            current = [match]
            continue
        expected_offset = median_offset(current[-12:])
        same_run = (
            match.viral_frame == current[-1].viral_frame + 1
            and abs((match.source_frame - match.viral_frame) - expected_offset) <= OFFSET_TOLERANCE
            and abs(match.crop_x - current[-1].crop_x) <= CROP_TOLERANCE
            and match.flipped == current[-1].flipped
        )
        if same_run:
            current.append(match)
        else:
            flush()
            current = [match]
    flush()

    segments = smooth_short_segments(segments)
    segments = drop_bad_segments(segments)
    segments = optimize_segment_boundaries(segments)
    return [segment for segment in segments if segment.frame_count >= MIN_SEGMENT_FRAMES]


def merge_segments(left: Segment, right: Segment) -> Segment:
    frames = left.frame_count + right.frame_count
    return Segment(
        left.viral_start,
        right.viral_end,
        left.source_start,
        right.source_end,
        int(round((left.crop_x * left.frame_count + right.crop_x * right.frame_count) / frames)),
        left.flipped,
        (left.avg_score * left.frame_count + right.avg_score * right.frame_count) / frames,
        max(left.max_score, right.max_score),
    )


def can_coalesce(left: Segment, right: Segment) -> bool:
    viral_gap = right.viral_start - left.viral_end
    source_gap = right.source_start - left.source_end
    return (
        viral_gap == 1
        and source_gap == 1
        and left.flipped == right.flipped
        and abs(left.crop_x - right.crop_x) <= CROP_TOLERANCE
    )


def extend_segment(segment: Segment, viral_start: int, viral_end: int) -> Segment:
    offset = segment.source_start - segment.viral_start
    return Segment(
        viral_start,
        viral_end,
        viral_start + offset,
        viral_end + offset,
        segment.crop_x,
        segment.flipped,
        segment.avg_score,
        segment.max_score,
    )


def segment_offset(segment: Segment) -> int:
    return segment.source_start - segment.viral_start


def offset_delta(left: Segment | None, right: Segment | None) -> int:
    if left is None or right is None:
        return 10**9
    return abs(segment_offset(left) - segment_offset(right))


def smooth_short_segments(segments: list[Segment]) -> list[Segment]:
    if len(segments) < 2:
        return segments

    segments = bridge_short_timeline_jumps(segments)
    smoothed: list[Segment] = []
    index = 0
    while index < len(segments):
        segment = segments[index]
        if segment.frame_count > SHORT_SEGMENT_FRAMES:
            smoothed.append(segment)
            index += 1
            continue

        previous = smoothed[-1] if smoothed else None
        next_segment = segments[index + 1] if index + 1 < len(segments) else None
        previous_delta = offset_delta(previous, segment)
        next_delta = offset_delta(segment, next_segment)
        if previous is None and next_segment is None:
            smoothed.append(segment)
        elif segment.frame_count <= TINY_SEGMENT_FRAMES and (
            previous is None or (next_segment is not None and next_segment.frame_count > previous.frame_count)
        ):
            segments[index + 1] = extend_segment(next_segment, segment.viral_start, next_segment.viral_end)
        elif segment.frame_count <= TINY_SEGMENT_FRAMES and previous is not None:
            smoothed[-1] = extend_segment(previous, previous.viral_start, segment.viral_end)
        elif (
            previous is not None
            and next_segment is not None
            and offset_delta(previous, next_segment) <= SHORT_OFFSET_TOLERANCE
        ):
            smoothed[-1] = extend_segment(previous, previous.viral_start, segment.viral_end)
        elif previous is None and next_delta <= SHORT_OFFSET_TOLERANCE:
            segments[index + 1] = extend_segment(next_segment, segment.viral_start, next_segment.viral_end)
        elif next_segment is None and previous_delta <= SHORT_OFFSET_TOLERANCE:
            smoothed[-1] = extend_segment(previous, previous.viral_start, segment.viral_end)
        elif previous_delta <= SHORT_OFFSET_TOLERANCE and (
            next_delta > SHORT_OFFSET_TOLERANCE or previous.frame_count >= next_segment.frame_count
        ):
            smoothed[-1] = extend_segment(previous, previous.viral_start, segment.viral_end)
        elif next_delta <= SHORT_OFFSET_TOLERANCE:
            segments[index + 1] = extend_segment(next_segment, segment.viral_start, next_segment.viral_end)
        else:
            smoothed.append(segment)
        index += 1

    coalesced: list[Segment] = []
    for segment in smoothed:
        if coalesced and can_coalesce(coalesced[-1], segment):
            coalesced[-1] = merge_segments(coalesced[-1], segment)
        else:
            coalesced.append(segment)
    return coalesced


def is_bad_segment(segment: Segment, previous: Segment | None, next_segment: Segment | None) -> bool:
    if segment.frame_count <= SHORT_SEGMENT_FRAMES and segment.avg_score >= BAD_SHORT_SEGMENT_SCORE:
        return True
    if segment.avg_score < BAD_SEGMENT_SCORE:
        return False
    previous_jump = previous is not None and offset_delta(previous, segment) > SHORT_OFFSET_TOLERANCE
    next_jump = next_segment is not None and offset_delta(segment, next_segment) > SHORT_OFFSET_TOLERANCE
    return previous_jump or next_jump


def drop_bad_segments(segments: list[Segment]) -> list[Segment]:
    clean: list[Segment] = []
    for index, segment in enumerate(segments):
        previous = clean[-1] if clean else None
        next_segment = segments[index + 1] if index + 1 < len(segments) else None
        if not is_bad_segment(segment, previous, next_segment):
            clean.append(segment)
    return clean


def optimize_segment_boundaries(segments: list[Segment]) -> list[Segment]:
    if not segments:
        return []

    optimized = [segments[0]]
    for segment in segments[1:]:
        previous = optimized[-1]
        gap = segment.viral_start - previous.viral_end - 1
        if 0 < gap <= SHORT_SEGMENT_FRAMES and offset_delta(previous, segment) <= SHORT_OFFSET_TOLERANCE:
            optimized[-1] = extend_segment(previous, previous.viral_start, segment.viral_start - 1)
        if optimized and can_coalesce(optimized[-1], segment):
            optimized[-1] = merge_segments(optimized[-1], segment)
        else:
            optimized.append(segment)
    return optimized


def bridge_short_timeline_jumps(segments: list[Segment]) -> list[Segment]:
    bridged: list[Segment] = []
    index = 0
    while index < len(segments):
        previous = bridged[-1] if bridged else None
        segment = segments[index]
        if previous is None or segment.frame_count > SHORT_SEGMENT_FRAMES or offset_delta(previous, segment) <= SHORT_OFFSET_TOLERANCE:
            bridged.append(segment)
            index += 1
            continue

        start = index
        while (
            index < len(segments)
            and segments[index].frame_count <= SHORT_SEGMENT_FRAMES
            and offset_delta(previous, segments[index]) > SHORT_OFFSET_TOLERANCE
        ):
            index += 1
        next_segment = segments[index] if index < len(segments) else None
        if next_segment is not None and offset_delta(previous, next_segment) <= SHORT_OFFSET_TOLERANCE:
            bridged[-1] = extend_segment(previous, previous.viral_start, segments[index - 1].viral_end)
        else:
            bridged.extend(segments[start:index])
    return bridged


def fill_gaps_by_extending_previous(segments: list[Segment]) -> list[Segment]:
    if not segments:
        return []
    filled = [segments[0]]
    for segment in segments[1:]:
        previous = filled[-1]
        gap = segment.viral_start - previous.viral_end - 1
        if gap > 0:
            filled.append(
                Segment(
                    previous.viral_end + 1,
                    segment.viral_start - 1,
                    previous.source_end + 1,
                    previous.source_end + gap,
                    previous.crop_x,
                    previous.flipped,
                    previous.avg_score,
                    previous.max_score,
                )
            )
        filled.append(segment)
    return filled


def _write_csv(matches: list[Match], path: Path) -> None:
    if not matches:
        return
    with path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=list(asdict(matches[0]).keys()))
        writer.writeheader()
        for match in matches:
            writer.writerow(asdict(match))


def _segments_to_clip_matches(segments: list[Segment], viral_fps: float, source_fps: float) -> list[dict[str, float]]:
    clip_matches: list[dict[str, float]] = []
    for segment in segments:
        viral_frame_count = segment.viral_end - segment.viral_start + 1
        source_frame_count = segment.source_end - segment.source_start + 1
        clip_matches.append(
            {
                "target_start": round(segment.viral_start / viral_fps, 3),
                "duration": round(viral_frame_count / viral_fps, 3),
                "source_start": round(segment.source_start / source_fps, 3),
                "source_duration": round(source_frame_count / source_fps, 3),
                "score": round(segment.avg_score, 3),
                "max_score": round(segment.max_score, 3),
                "crop_x": float(segment.crop_x),
                "flipped": float(1 if segment.flipped else 0),
            }
        )
    return clip_matches


def run_frame_match(viral_video: str | Path, source_video: str | Path, output_dir: str | Path) -> dict:
    """执行完整帧匹配流程，输出剪映可直接使用的秒级片段。"""
    viral_path = Path(viral_video).expanduser().resolve()
    source_path = Path(source_video).expanduser().resolve()
    output_dir = Path(output_dir).expanduser().resolve()
    work_dir = output_dir / "work"
    work_dir.mkdir(parents=True, exist_ok=True)

    print_log("镜头匹配开始", "Frame match started", viral_video=viral_path, source_video=source_path, output_dir=output_dir)
    viral_fps = get_video_fps(viral_path)
    source_fps = get_video_fps(source_path)
    viral_frames = _frame_count(viral_path, viral_fps)
    source_frames = _frame_count(source_path, source_fps)
    viral_width, viral_height = _dimensions(viral_path)
    source_width, source_height = _dimensions(source_path)
    cache_dir = _source_cache_dir(source_path, output_dir)
    print_log(
        "镜头匹配视频信息",
        "Frame match video metadata",
        viral_fps=f"{viral_fps:.3f}",
        source_fps=f"{source_fps:.3f}",
        viral_frames=viral_frames,
        source_frames=source_frames,
        viral_size=f"{viral_width}x{viral_height}",
        source_size=f"{source_width}x{source_height}",
        cache=cache_dir,
    )

    frame_matches = find_matches(viral_path, source_path, source_fps, source_width, cache_dir)
    matches_csv = work_dir / "matches.csv"
    _write_csv(frame_matches, matches_csv)

    raw_segments = build_segments(frame_matches)
    if not raw_segments:
        raise RuntimeError("没有可用镜头片段 / No matched segments found")
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
        "segment_count": len(segments),
        "segment_frames": sum(segment.frame_count for segment in segments),
        "viral_frames": viral_frames,
        "output_dir": str(output_dir),
        "viral": str(viral_path),
        "source": str(source_path),
        "source_cache": str(cache_dir),
        "segments": str(segments_json),
        "raw_segments": str(raw_segments_json),
        "matches_csv": str(matches_csv),
    }
    (work_dir / "verify_summary.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    print_log(
        "镜头匹配结束",
        "Frame match finished",
        matches=len(clip_matches),
        segment_frames=summary["segment_frames"],
        coverage=f"{summary['segment_frames'] / max(1, viral_frames):.3f}",
    )
    return summary | {"matches": clip_matches}
