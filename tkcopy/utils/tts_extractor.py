"""TTS分离工具 - 从视频中提取TTS旁白和字幕"""
import json
import os
import re
import shutil
import subprocess
import sys
import urllib.error
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

import numpy as np

from tkcopy.logging_utils import print_log


SUPPORTED_WHISPER_MODELS = {"tiny.en", "tiny", "base.en", "base", "small.en", "small", "medium.en", "medium", "large-v1", "large"}
PYANNOTE_EMBEDDING_MODEL = "pyannote/wespeaker-voxceleb-resnet34-LM"


@dataclass(frozen=True)
class VocalSeparationResult:
    output_dir: Path
    vocals_path: Path
    accompaniment_path: Path


@dataclass(frozen=True)
class SpeechSegmentsResult:
    segments_dir: Path
    segments_json: Path
    segments: list[dict[str, Any]]


@dataclass(frozen=True)
class DominantSpeakerResult:
    segments_json: Path
    report_json: Path
    speaker_id: int
    segments: list[dict[str, Any]]


@dataclass(frozen=True)
class SegmentAsrResult:
    srt_path: Path
    entries: list[tuple[int, int, str]]


def _format_srt_time(ms: int) -> str:
    s, ms = divmod(ms, 1000)
    m, s = divmod(s, 60)
    h, m = divmod(m, 60)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def resolve_whisper_model_name(model_path: str | Path) -> str:
    """Resolve a configured model path/name to whispercpp's supported model name."""
    value = str(model_path).strip()
    name = Path(value).stem
    if name.startswith("ggml-"):
        name = name[5:]
    if name in SUPPORTED_WHISPER_MODELS:
        return name
    raise ValueError(
        f"不支持的 whispercpp 模型 / Unsupported whispercpp model: {value}. "
        f"请选择 / choose one of: {', '.join(sorted(SUPPORTED_WHISPER_MODELS))}"
    )


def load_whisper_model(model_path: str | Path):
    """Load a Whisper model from a local ggml file or a whispercpp model name."""
    import whispercpp as wp

    model_value = str(model_path).strip()
    local_path = Path(model_value).expanduser()
    if local_path.exists():
        print_log("加载本地 Whisper 模型", "Loading local Whisper model", path=local_path)
        ref = object.__new__(wp.Whisper)
        context = wp.api.Context.from_file(str(local_path), no_state=False)
        params = (
            wp.api.Params.from_enum(wp.api.SAMPLING_GREEDY)
            .with_print_progress(False)
            .with_print_realtime(False)
            .build()
        )
        context.reset_timings()
        ref.__dict__.update(
            {
                "context": context,
                "params": params,
                "no_state": False,
                "basedir": None,
                "_context_initialized": True,
                "_transcript": [],
            }
        )
        print_log("本地 Whisper 模型加载完成", "Local Whisper model loaded", path=local_path)
        return ref

    model_name = resolve_whisper_model_name(model_value)
    print_log("加载在线 Whisper 模型", "Loading bundled Whisper model", model=model_name)
    try:
        model = wp.Whisper.from_pretrained(model_name)
    except urllib.error.HTTPError as exc:
        raise RuntimeError(
            "Whisper 模型下载失败 / Whisper model download failed. "
            "请在设置里填写本地 ggml 模型文件路径，或确认网络可以访问模型下载源。"
        ) from exc
    print_log("在线 Whisper 模型加载完成", "Bundled Whisper model loaded", model=model_name)
    return model


def run_ffprobe(args: list[str], input_path: str | Path) -> dict:
    """执行ffprobe命令返回JSON结果"""
    cmd = ["ffprobe", "-v", "error", "-of", "json"] + args + [str(input_path)]
    print_log("执行 ffprobe", "Running ffprobe", input=input_path)
    result = subprocess.run(cmd, check=True, stdout=subprocess.PIPE)
    return json.loads(result.stdout)


def get_audio_duration(video_path: str | Path) -> float:
    """获取视频音频时长(秒)"""
    data = run_ffprobe(
        ["-select_streams", "a:0", "-show_entries", "stream=duration"],
        video_path,
    )
    return float(data["streams"][0]["duration"])


def extract_audio(video_path: str | Path, output_path: str | Path) -> Path:
    """从视频提取音频"""
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    print_log("提取音频", "Extracting audio", input=video_path, output=output_path)
    subprocess.run(
        ["ffmpeg", "-y", "-i", str(video_path), "-vn", "-ac", "1", "-ar", "16000", str(output_path)],
        check=True,
        capture_output=True,
    )
    print_log("音频提取完成", "Audio extracted", output=output_path)
    return output_path


def _model_cache_env() -> dict[str, str]:
    env = os.environ.copy()
    model_dir = Path("model").resolve()
    env.setdefault("TORCH_HOME", str(model_dir / "torch"))
    env.setdefault("HF_HOME", str(model_dir / "huggingface"))
    return env


def _demucs_command() -> list[str]:
    executable = shutil.which("demucs")
    if executable:
        return [executable]
    autocopy_demucs = Path.home() / "Documents" / "autocopy" / ".venv" / "bin" / "demucs"
    if autocopy_demucs.exists():
        return [str(autocopy_demucs)]
    return [sys.executable, "-m", "demucs.separate"]


def separate_vocals(
    audio_path: str | Path,
    *,
    output_dir: str | Path,
    model: str = "htdemucs",
) -> VocalSeparationResult:
    """用 Demucs 分离人声和伴奏。"""
    audio = Path(audio_path)
    if not audio.is_file():
        raise FileNotFoundError(audio)

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    model_name = model or "htdemucs"
    cmd = _demucs_command() + [
        "--two-stems",
        "vocals",
        "-n",
        model_name,
        "-o",
        str(output_dir),
        str(audio),
    ]
    print_log("开始人声分离", "Starting vocal separation", audio=audio, model=model_name)
    subprocess.run(
        cmd,
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=_model_cache_env(),
    )
    stem_dir = output_dir / model_name / audio.stem
    result = VocalSeparationResult(
        output_dir=output_dir,
        vocals_path=stem_dir / "vocals.wav",
        accompaniment_path=stem_dir / "no_vocals.wav",
    )
    for path in (result.vocals_path, result.accompaniment_path):
        if not path.is_file():
            raise FileNotFoundError(path)
    print_log("人声分离完成", "Vocal separation completed", vocals=result.vocals_path)
    return result


def transcribe_with_whisper_cli(audio_path: str | Path, model_path: str | Path, output_dir: str | Path) -> Path:
    """Transcribe audio with the system whisper-cli and a local ggml model."""
    cli_path = shutil.which("whisper-cli")
    if not cli_path:
        raise RuntimeError(
            "未找到 whisper-cli / whisper-cli was not found. "
            "本地 ggml 模型需要安装 whisper.cpp 命令行工具。"
        )

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    output_stem = output_dir / "transcript"
    srt_path = output_stem.with_suffix(".srt")
    if srt_path.exists():
        srt_path.unlink()

    cmd = [
        cli_path,
        "-m",
        str(Path(model_path).expanduser()),
        "-f",
        str(audio_path),
        "-l",
        "auto",
        "-osrt",
        "-of",
        str(output_stem),
        "-pp",
    ]
    print_log("调用 whisper-cli 转录", "Running whisper-cli transcription", cmd=" ".join(cmd))
    subprocess.run(cmd, check=True)
    if not srt_path.exists() or srt_path.stat().st_size == 0:
        raise RuntimeError("whisper-cli 未生成字幕文件 / whisper-cli did not create an SRT file")
    print_log("whisper-cli 转录完成", "whisper-cli transcription completed", srt=srt_path)
    return srt_path


def vad_segments(
    audio_path: str | Path,
    vad_model: str | Path,
    threshold: float = 0.25,
    min_speech_ms: int = 10,
    min_silence_ms: int = 50,
) -> list[tuple[float, float]]:
    """用 whisper.cpp VAD 找出语音片段，返回秒级 start/end。"""
    cli_path = shutil.which("whisper-vad-speech-segments")
    if not cli_path:
        raise RuntimeError(
            "未找到 whisper-vad-speech-segments / whisper-vad-speech-segments was not found."
        )
    cmd = [
        cli_path,
        "-np",
        "-vm",
        str(vad_model),
        "-vt",
        str(threshold),
        "--vad-min-speech-duration-ms",
        str(min_speech_ms),
        "-vsd",
        str(min_silence_ms),
        "-f",
        str(audio_path),
    ]
    print_log("执行 VAD 语音切分", "Running VAD speech segmentation", audio=audio_path, model=vad_model)
    result = subprocess.run(cmd, check=True, capture_output=True, text=True)
    segments = []
    for line in result.stdout.splitlines():
        match = re.search(r"start = ([0-9.]+), end = ([0-9.]+)", line)
        if match:
            # whisper.cpp VAD prints 10 ms ticks.
            segments.append((float(match.group(1)) / 100, float(match.group(2)) / 100))
    print_log("VAD 切分完成", "VAD segmentation completed", segments=len(segments))
    return segments


def split_speech_segments(
    audio_path: str | Path,
    *,
    vad_model: str | Path,
    output_dir: str | Path,
    threshold: float = 0.25,
    min_speech_ms: int = 10,
    min_silence_ms: int = 50,
) -> SpeechSegmentsResult:
    """把人声音频切成 VAD 语音片段，并写出 segments.json。"""
    audio = Path(audio_path)
    if not audio.is_file():
        raise FileNotFoundError(audio)

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    segments = []
    for index, (start, end) in enumerate(
        vad_segments(audio, vad_model, threshold, min_speech_ms, min_silence_ms),
        1,
    ):
        segment_path = output_dir / f"segment_{index:04d}.wav"
        subprocess.run(
            [
                "ffmpeg",
                "-hide_banner",
                "-loglevel",
                "error",
                "-y",
                "-ss",
                f"{start:.3f}",
                "-to",
                f"{end:.3f}",
                "-i",
                str(audio),
                "-ar",
                "16000",
                "-ac",
                "1",
                str(segment_path),
            ],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        start_ms = int(round(start * 1000))
        end_ms = int(round(end * 1000))
        if end_ms - start_ms < 300:
            continue
        segments.append(
            {
                "index": index,
                "start_ms": start_ms,
                "end_ms": end_ms,
                "duration_ms": end_ms - start_ms,
                "audio_path": str(segment_path),
            }
        )

    segments_json = output_dir / "segments.json"
    segments_json.write_text(json.dumps(segments, ensure_ascii=False, indent=2), encoding="utf-8")
    print_log("语音片段切分完成", "Speech segments split", segments=len(segments), json=segments_json)
    return SpeechSegmentsResult(output_dir, segments_json, segments)


def voice_embedding(
    audio_path: str | Path,
    *,
    hf_token: str | None = None,
    model_source: str = PYANNOTE_EMBEDDING_MODEL,
) -> np.ndarray:
    inference = _get_pyannote_inference(model_source, _resolve_hf_token(hf_token))
    embedding = _to_numpy_vector(inference(str(audio_path)))
    if embedding.size == 0:
        raise ValueError(f"empty speaker embedding: {audio_path}")
    return _normalize(embedding)


def select_dominant_speaker(
    segments_json: str | Path,
    *,
    output_json: str | Path,
    report_json: str | Path,
    similarity_threshold: float = 0.82,
    hf_token: str | None = None,
    model_source: str = PYANNOTE_EMBEDDING_MODEL,
) -> DominantSpeakerResult:
    """按说话人嵌入聚类，保留总时长最长的主讲人。"""
    segments = json.loads(Path(segments_json).read_text(encoding="utf-8"))
    clusters: list[dict[str, Any]] = []

    for segment in segments:
        embedding = voice_embedding(
            segment["audio_path"],
            hf_token=hf_token,
            model_source=model_source,
        )
        match_index = _best_cluster_index(clusters, embedding, similarity_threshold)
        if match_index is None:
            clusters.append(
                {
                    "speaker_id": len(clusters),
                    "embedding": embedding,
                    "segments": [segment],
                    "total_duration_ms": int(segment.get("duration_ms", 0)),
                }
            )
            continue

        cluster = clusters[match_index]
        cluster["segments"].append(segment)
        cluster["total_duration_ms"] += int(segment.get("duration_ms", 0))
        cluster["embedding"] = _normalize(
            (cluster["embedding"] * (len(cluster["segments"]) - 1) + embedding)
            / len(cluster["segments"])
        )

    if not clusters:
        raise ValueError("没有可筛选的语音片段 / no speech segments found")

    dominant = max(clusters, key=lambda cluster: cluster["total_duration_ms"])
    selected = sorted(dominant["segments"], key=lambda segment: segment["start_ms"])
    output_json = Path(output_json)
    report_json = Path(report_json)
    output_json.parent.mkdir(parents=True, exist_ok=True)
    report_json.parent.mkdir(parents=True, exist_ok=True)
    output_json.write_text(json.dumps(selected, ensure_ascii=False, indent=2), encoding="utf-8")
    report = {
        "dominant_speaker_id": dominant["speaker_id"],
        "speakers": [
            {
                "speaker_id": cluster["speaker_id"],
                "segment_count": len(cluster["segments"]),
                "total_duration_ms": cluster["total_duration_ms"],
                "segments": [segment["index"] for segment in cluster["segments"]],
            }
            for cluster in clusters
        ],
    }
    report_json.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print_log("主讲人筛选完成", "Dominant speaker selected", speaker=dominant["speaker_id"], segments=len(selected))
    return DominantSpeakerResult(output_json, report_json, dominant["speaker_id"], selected)


def _parse_tuple_srt(path: str | Path) -> list[tuple[int, int, str]]:
    return [
        (entry["start_ms"], entry["end_ms"], entry["text"])
        for entry in srt_entries(path)
    ]


def transcribe_vad_entries(
    audio_path: str | Path,
    model_path: str | Path,
    vad_model: str | Path,
    prompt: str,
    work_dir: str | Path,
    threshold: float = 0.25,
    min_speech_ms: int = 10,
    min_silence_ms: int = 50,
) -> list[tuple[int, int, str]]:
    """先 VAD 切段，再对每段单独 ASR，降低角色对白混入概率。"""
    cli_path = shutil.which("whisper-cli")
    if not cli_path:
        raise RuntimeError("未找到 whisper-cli / whisper-cli was not found.")

    work_dir = Path(work_dir)
    entries = []
    for index, (start, end) in enumerate(
        vad_segments(audio_path, vad_model, threshold, min_speech_ms, min_silence_ms),
        1,
    ):
        piece = work_dir / f"vad_{index:04d}.wav"
        output_stem = work_dir / f"vad_{index:04d}"
        subprocess.run(
            [
                "ffmpeg",
                "-hide_banner",
                "-loglevel",
                "error",
                "-y",
                "-ss",
                f"{start:.3f}",
                "-to",
                f"{end:.3f}",
                "-i",
                str(audio_path),
                "-ar",
                "16000",
                "-ac",
                "1",
                str(piece),
            ],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        cmd = [
            cli_path,
            "-m",
            str(Path(model_path).expanduser()),
            "-l",
            "en",
            "-np",
            "-ml",
            "30",
            "-sow",
            "-osrt",
            "-of",
            str(output_stem),
            "--prompt",
            prompt[:800],
            str(piece),
        ]
        print_log("转录 VAD 片段", "Transcribing VAD segment", index=index, start=f"{start:.2f}", end=f"{end:.2f}")
        subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        offset = int(start * 1000)
        entries.extend(
            (s + offset, e + offset, text)
            for s, e, text in _parse_tuple_srt(output_stem.with_suffix(".srt"))
        )
    print_log("VAD 片段转录完成", "VAD segment transcription completed", entries=len(entries))
    return entries


def transcribe_segments_to_srt(
    segments_json: str | Path,
    *,
    whisper_model: str | Path,
    output_srt: str | Path,
    work_dir: str | Path,
    language: str = "en",
    prompt: str = "",
    max_len: int = 50,
    split_on_word: bool = True,
    speaker_filter: bool = False,
    speaker_threshold: float = 0.3,
    timing_offset_ms: int = 820,
    hf_token: str | None = None,
    model_source: str = PYANNOTE_EMBEDDING_MODEL,
) -> SegmentAsrResult:
    """对主讲人语音片段逐段 ASR，并按原时间轴合成 SRT。"""
    cli_path = shutil.which("whisper-cli")
    if not cli_path:
        raise RuntimeError("未找到 whisper-cli / whisper-cli was not found.")

    segments = json.loads(Path(segments_json).read_text(encoding="utf-8"))
    work_dir = Path(work_dir)
    work_dir.mkdir(parents=True, exist_ok=True)
    entries: list[tuple[int, int, str]] = []
    entry_records: list[dict[str, Any]] = []

    for segment in segments:
        audio_path = Path(segment["audio_path"])
        output_stem = work_dir / f"asr_{int(segment['index']):04d}"
        cmd = [
            cli_path,
            "-m",
            str(Path(whisper_model).expanduser()),
            "-l",
            language,
            "-np",
            "-osrt",
            "-of",
            str(output_stem),
        ]
        if max_len > 0:
            cmd += ["-ml", str(max_len)]
        if split_on_word:
            cmd.append("-sow")
        if prompt:
            cmd += ["--prompt", prompt[:800]]
        cmd.append(str(audio_path))
        print_log("转录主讲人片段", "Transcribing speaker segment", index=segment["index"])
        subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        offset = int(segment["start_ms"])
        for start, end, text in _parse_tuple_srt(output_stem.with_suffix(".srt")):
            if end - start < 300:
                continue
            absolute = (start + offset, end + offset, text)
            entries.append(absolute)
            entry_records.append(
                {
                    "entry": absolute,
                    "audio_path": audio_path,
                    "local_start_ms": start,
                    "local_end_ms": end,
                }
            )

    if speaker_filter:
        entries = _filter_asr_entries_by_dominant_speaker(
            entry_records,
            output_dir=work_dir / "speaker_filter",
            similarity_threshold=speaker_threshold,
            hf_token=hf_token,
            model_source=model_source,
        )

    if timing_offset_ms:
        entries = [
            (max(0, start + timing_offset_ms), max(0, end + timing_offset_ms), text)
            for start, end, text in entries
        ]

    output_srt = _write_srt(entries, output_srt)
    print_log("分段 ASR 完成", "Segment ASR completed", entries=len(entries), srt=output_srt)
    return SegmentAsrResult(output_srt, entries)


def _filter_asr_entries_by_dominant_speaker(
    records: list[dict[str, Any]],
    *,
    output_dir: str | Path,
    similarity_threshold: float,
    hf_token: str | None,
    model_source: str,
) -> list[tuple[int, int, str]]:
    """对 ASR 结果再次按主讲人筛选，减少片段内角色对白混入。"""
    if len(records) <= 1:
        return [record["entry"] for record in records]

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    clusters: list[dict[str, Any]] = []
    clustered_records: list[dict[str, Any]] = []

    for index, record in enumerate(records, 1):
        start = int(record["local_start_ms"])
        end = int(record["local_end_ms"])
        duration = max(0, end - start)
        if duration < 300:
            continue

        line_audio = output_dir / f"line_{index:04d}.wav"
        subprocess.run(
            [
                "ffmpeg",
                "-hide_banner",
                "-loglevel",
                "error",
                "-y",
                "-ss",
                f"{start / 1000:.3f}",
                "-to",
                f"{end / 1000:.3f}",
                "-i",
                str(record["audio_path"]),
                "-ar",
                "16000",
                "-ac",
                "1",
                str(line_audio),
            ],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

        embedding = voice_embedding(
            line_audio,
            hf_token=hf_token,
            model_source=model_source,
        )
        match_index = _best_cluster_index(clusters, embedding, similarity_threshold)
        cluster_record = {**record, "duration_ms": duration}
        if match_index is None:
            clusters.append(
                {
                    "speaker_id": len(clusters),
                    "embedding": embedding,
                    "records": [cluster_record],
                    "total_duration_ms": duration,
                }
            )
        else:
            cluster = clusters[match_index]
            cluster["records"].append(cluster_record)
            cluster["total_duration_ms"] += duration
            cluster["embedding"] = _normalize(
                (cluster["embedding"] * (len(cluster["records"]) - 1) + embedding)
                / len(cluster["records"])
            )
        clustered_records.append(cluster_record)

    if not clusters:
        return [record["entry"] for record in records]

    dominant = max(clusters, key=lambda cluster: cluster["total_duration_ms"])
    selected_ids = {id(record) for record in dominant["records"]}
    selected = _attach_short_rejected_continuations(
        clustered_records,
        selected_ids,
        max_gap_ms=250,
        max_words=3,
    )
    print_log(
        "ASR 行级主讲人筛选完成",
        "ASR line-level speaker filter completed",
        kept=len(selected),
        total=len(records),
    )
    return selected


def _attach_short_rejected_continuations(
    records: list[dict[str, Any]],
    selected_ids: set[int],
    *,
    max_gap_ms: int,
    max_words: int,
) -> list[tuple[int, int, str]]:
    selected: list[tuple[int, int, str]] = []
    for record in records:
        entry = record["entry"]
        if id(record) in selected_ids:
            selected.append(entry)
            continue
        if _is_short_continuation(entry, selected, max_gap_ms=max_gap_ms, max_words=max_words):
            start, _end, text = selected[-1]
            rejected_start, rejected_end, rejected_text = entry
            selected[-1] = (
                start,
                max(_end, rejected_end),
                _join_subtitle_text(text, rejected_text),
            )
    return selected


def _is_short_continuation(
    entry: tuple[int, int, str],
    selected: list[tuple[int, int, str]],
    *,
    max_gap_ms: int,
    max_words: int,
) -> bool:
    if not selected:
        return False
    start, _end, text = entry
    _prev_start, prev_end, _prev_text = selected[-1]
    if max(0, start - prev_end) > max_gap_ms:
        return False
    words = re.findall(r"[A-Za-z0-9']+", text)
    return 0 < len(words) <= max_words


def _join_subtitle_text(left: str, right: str) -> str:
    left = left.strip()
    right = right.strip()
    if not left:
        return right
    if not right:
        return left
    return f"{left} {right}"


def _resolve_hf_token(hf_token: str | None) -> str | None:
    token = (hf_token or "").strip()
    return token or os.environ.get("HF_TOKEN") or os.environ.get("HUGGINGFACE_TOKEN")


@lru_cache(maxsize=4)
def _get_pyannote_inference(
    model_source: str = PYANNOTE_EMBEDDING_MODEL,
    hf_token: str | None = None,
):
    try:
        from pyannote.audio import Inference, Model
    except ImportError as exc:
        raise RuntimeError("pyannote.audio is required for speaker embedding") from exc

    model = Model.from_pretrained(
        model_source,
        token=hf_token,
        cache_dir=str((Path("model") / "pyannote").resolve()),
    )
    if model is None:
        raise RuntimeError(f"Pyannote returned no model: {model_source}")
    return Inference(model, window="whole")


def _to_numpy_vector(value: Any) -> np.ndarray:
    if hasattr(value, "data"):
        value = value.data
    if hasattr(value, "detach"):
        value = value.detach().cpu().numpy()
    vector = np.asarray(value, dtype=np.float32)
    while vector.ndim > 1:
        vector = vector.mean(axis=0)
    return vector


def _best_cluster_index(
    clusters: list[dict[str, Any]],
    embedding: np.ndarray,
    threshold: float,
) -> int | None:
    if not clusters:
        return None
    similarities = [
        float(np.dot(cluster["embedding"], embedding))
        for cluster in clusters
    ]
    best_index = int(np.argmax(similarities))
    return best_index if similarities[best_index] >= threshold else None


def _normalize(vector: np.ndarray) -> np.ndarray:
    norm = np.linalg.norm(vector)
    return vector if norm == 0 else vector / norm


def transcribe_with_whisper(audio_path: str | Path, model_path: str | Path, output_dir: str | Path) -> Path:
    """使用whisper.cpp转录音频生成SRT"""
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    srt_path = output_dir / "transcript.srt"

    local_model_path = Path(str(model_path).strip()).expanduser()
    if local_model_path.exists():
        return transcribe_with_whisper_cli(audio_path, local_model_path, output_dir)

    print_log("准备加载 Whisper 模型", "Preparing to load Whisper model", model=model_path)
    w = load_whisper_model(model_path)
    print_log("开始转录音频", "Starting transcription", audio=audio_path)
    transcript = w.transcribe_from_file(str(audio_path)).strip()
    duration_ms = int(get_audio_duration(audio_path) * 1000)
    if not transcript:
        raise RuntimeError("Whisper 未返回转录文本 / Whisper returned an empty transcript")

    srt_path.write_text(
        f"1\n00:00:00,000 --> {_format_srt_time(duration_ms)}\n{transcript}\n\n",
        encoding="utf-8",
    )
    print_log("转录完成", "Transcription completed", srt=srt_path, chars=len(transcript))
    return srt_path


def parse_srt_time(value: str) -> int:
    """解析SRT时间戳为毫秒"""
    h, m, rest = value.split(":")
    s, ms = rest.split(",")
    return ((int(h) * 60 + int(m)) * 60 + int(s)) * 1000 + int(ms)


def srt_entries(path: str | Path) -> list[dict[str, Any]]:
    """解析SRT文件返回条目列表"""
    entries = []
    text = Path(path).read_text("utf-8").strip()
    if not text:
        return entries
    for block in re.split(r"\n\s*\n", text):
        lines = [line.strip() for line in block.splitlines() if line.strip()]
        if len(lines) < 3 or "-->" not in lines[1]:
            continue
        start, end = [part.strip() for part in lines[1].split("-->")]
        entries.append({
            "index": int(lines[0]),
            "start_ms": parse_srt_time(start),
            "end_ms": parse_srt_time(end),
            "text": " ".join(lines[2:]),
        })
    return entries


def _write_srt(entries: list[tuple[int, int, str]], path: str | Path) -> Path:
    blocks = []
    for index, (start, end, text) in enumerate(entries, 1):
        blocks.append(f"{index}\n{_format_srt_time(start)} --> {_format_srt_time(end)}\n{text.strip()}\n")
    path = Path(path)
    path.write_text("\n".join(blocks), encoding="utf-8")
    return path


def run_tts_extraction(
    video_path: str | Path,
    model_path: str | Path,
    output_dir: str | Path,
    *,
    vad_model: str | Path | None = None,
    vad_threshold: float = 0.25,
    min_speech_ms: int = 10,
    min_silence_ms: int = 50,
    demucs_model: str = "htdemucs",
    speaker_filter: bool = True,
    speaker_similarity_threshold: float = 0.82,
    speaker_threshold: float = 0.3,
    hf_token: str | None = None,
    pyannote_model: str = PYANNOTE_EMBEDDING_MODEL,
    asr_language: str = "en",
    asr_prompt: str = "",
    asr_max_len: int = 50,
    asr_split_on_word: bool = True,
    timing_offset_ms: int = 820,
) -> dict:
    """执行完整TTS分离流程"""
    output_dir = Path(output_dir)
    print_log("TTS 分离开始", "TTS extraction started", video=video_path, output_dir=output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    audio_path = extract_audio(video_path, output_dir / "audio.wav")
    video_stem = Path(video_path).stem
    final_srt_path = output_dir / f"{video_stem}.final_tts.srt"

    if not vad_model or not Path(vad_model).expanduser().exists():
        raise FileNotFoundError(f"缺少 VAD 模型 / Missing VAD model: {vad_model}")

    separation = separate_vocals(
        audio_path,
        output_dir=output_dir / "separated",
        model=demucs_model,
    )
    segments = split_speech_segments(
        separation.vocals_path,
        vad_model=Path(vad_model).expanduser(),
        output_dir=output_dir / "vad_segments",
        threshold=vad_threshold,
        min_speech_ms=min_speech_ms,
        min_silence_ms=min_silence_ms,
    )
    if speaker_filter:
        dominant = select_dominant_speaker(
            segments.segments_json,
            output_json=output_dir / "dominant_segments.json",
            report_json=output_dir / "speaker_report.json",
            similarity_threshold=speaker_similarity_threshold,
            hf_token=hf_token,
            model_source=pyannote_model,
        )
        segments_json = dominant.segments_json
    else:
        dominant = None
        segments_json = segments.segments_json

    asr_result = transcribe_segments_to_srt(
        segments_json,
        whisper_model=model_path,
        output_srt=final_srt_path,
        work_dir=output_dir / "segment_asr",
        language=asr_language,
        prompt=asr_prompt,
        max_len=asr_max_len,
        split_on_word=asr_split_on_word,
        speaker_filter=speaker_filter,
        speaker_threshold=speaker_threshold,
        timing_offset_ms=timing_offset_ms,
        hf_token=hf_token,
        model_source=pyannote_model,
    )
    parsed_entries = srt_entries(final_srt_path)
    print_log("TTS 分离完成", "TTS extraction completed", entries=len(parsed_entries), srt=final_srt_path)
    return {
        "audio_path": str(audio_path),
        "vocals_audio": str(separation.vocals_path),
        "accompaniment_audio": str(separation.accompaniment_path),
        "speech_segments_json": str(segments.segments_json),
        "dominant_segments_json": str(segments_json),
        "speaker_report_json": str(dominant.report_json) if dominant else "",
        "srt_path": str(final_srt_path),
        "asr_entries": asr_result.entries,
        "entries": parsed_entries,
    }
