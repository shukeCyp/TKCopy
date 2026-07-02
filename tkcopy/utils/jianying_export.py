"""剪映草稿工具 - 生成剪映项目文件"""
import json
import re
import shutil
import subprocess
import uuid
from pathlib import Path
from typing import Any

from tkcopy.logging_utils import print_log

DEFAULT_DRAFT_FOLDER = Path.home() / "Downloads/草稿/JianyingPro Drafts"
MICROSECONDS_PER_SECOND = 1_000_000


def seconds_to_microseconds(seconds: float) -> int:
    """把秒转换为剪映草稿使用的微秒。"""
    return int(round(float(seconds) * MICROSECONDS_PER_SECOND))


def seconds_timerange(cc, start_seconds: float, duration_seconds: float):
    """Create a pycapcut Timerange from seconds."""
    return cc.Timerange(
        seconds_to_microseconds(start_seconds),
        seconds_to_microseconds(duration_seconds),
    )


def microseconds_timerange(cc, start_microseconds: int, duration_microseconds: int):
    """Create a pycapcut Timerange from already-normalized microseconds."""
    return cc.Timerange(int(start_microseconds), int(duration_microseconds))


def safe_draft_name(name: str) -> str:
    """生成安全的草稿名称"""
    name = name.strip()
    name = re.sub(r'[\\/:*?"<>|]+', "_", name)
    safe_name = name or "tkcopy_draft"
    print_log("生成草稿名称", "Generated draft name", name=safe_name)
    return safe_name


def get_video_info(video_path: str | Path) -> tuple[int, int, float]:
    """获取视频信息: width, height, duration"""
    cmd = [
        "ffprobe", "-v", "error", "-select_streams", "v:0",
        "-show_entries", "stream=width,height,duration:format=duration", "-of", "json", str(video_path),
    ]
    result = subprocess.run(cmd, check=True, stdout=subprocess.PIPE)
    data = json.loads(result.stdout)
    s = data["streams"][0]
    duration = s.get("duration") or data.get("format", {}).get("duration")
    if duration is None:
        raise ValueError(f"无法读取视频时长 / Could not read video duration: {video_path}")
    info = int(s["width"]), int(s["height"]), float(duration)
    print_log("读取剪映视频信息", "Read Jianying video info", video=video_path, width=info[0], height=info[1], duration=f"{info[2]:.2f}")
    return info


def get_media_duration(media_path: str | Path) -> float:
    """获取媒体时长(秒)"""
    cmd = [
        "ffprobe",
        "-v",
        "error",
        "-show_entries",
        "format=duration",
        "-of",
        "default=nokey=1:noprint_wrappers=1",
        str(media_path),
    ]
    result = subprocess.run(cmd, check=True, stdout=subprocess.PIPE)
    duration = float(result.stdout.decode().strip())
    print_log("读取媒体时长", "Read media duration", media=media_path, duration=f"{duration:.2f}")
    return duration


def create_video_material(cc, path: str | Path, width: int, height: int, duration: float):
    """Create a pycapcut VideoMaterial from ffprobe data, avoiding MKV parser duration bugs."""
    material = object.__new__(cc.VideoMaterial)
    material.material_name = Path(path).name
    material.material_id = uuid.uuid4().hex
    material.path = str(Path(path).expanduser().resolve())
    material.crop_settings = cc.CropSettings()
    material.local_material_id = ""
    material.material_type = "video"
    material.duration = int(round(float(duration) * 1_000_000))
    material.width = int(width)
    material.height = int(height)
    return material


def create_audio_material(cc, path: str | Path, duration: float):
    """Create a pycapcut AudioMaterial from ffprobe duration."""
    material = object.__new__(cc.AudioMaterial)
    material.material_name = Path(path).name
    material.material_id = uuid.uuid4().hex
    material.path = str(Path(path).expanduser().resolve())
    material.duration = int(round(float(duration) * MICROSECONDS_PER_SECOND))
    return material


def prepare_jianying_video_source(source_video: str | Path, draft_path: str | Path) -> Path:
    """Prepare a Jianying-friendly video file for timeline segments."""
    source_video = Path(source_video).expanduser().resolve()
    if source_video.suffix.lower() != ".mkv":
        print_log("复用剪映视频素材", "Reusing Jianying video source", source=source_video)
        return source_video

    resource_dir = Path(draft_path).expanduser() / "Resources" / "tkcopy"
    resource_dir.mkdir(parents=True, exist_ok=True)
    output_path = resource_dir / f"{source_video.stem}.mp4"
    if output_path.exists() and output_path.stat().st_size > 0:
        if is_jianying_mp4_compatible(output_path):
            print_log("复用已转封装 MP4", "Reusing remuxed MP4", output=output_path)
            return output_path
        print_log("旧 MP4 不兼容，重新生成", "Existing MP4 is incompatible, rebuilding", output=output_path)
        output_path.unlink()

    cmd = [
        "ffmpeg",
        "-hide_banner",
        "-loglevel",
        "error",
        "-y",
        "-i",
        str(source_video),
        "-map",
        "0:v:0",
        "-map",
        "0:a?",
        "-c:v",
        "copy",
        "-c:a",
        "aac",
        "-b:a",
        "192k",
        "-movflags",
        "+faststart",
        str(output_path),
    ]
    print_log("转封装 MKV 为剪映兼容 MP4", "Remuxing MKV to Jianying-compatible MP4", source=source_video, output=output_path)
    subprocess.run(cmd, check=True)
    print_log("MP4 转封装完成", "MP4 remux completed", output=output_path)
    return output_path


def prepare_jianying_audio_source(
    audio_path: str | Path,
    draft_path: str | Path,
    *,
    trim_silence: bool = False,
    padding_seconds: float = 0.1,
) -> Path:
    """Copy voiceover audio into the draft resource folder for Jianying access."""
    audio_path = Path(audio_path).expanduser().resolve()
    resource_dir = Path(draft_path).expanduser() / "Resources" / "tkcopy"
    resource_dir.mkdir(parents=True, exist_ok=True)
    if trim_silence:
        trim_dir = resource_dir / "voiceover_trimmed"
        trim_dir.mkdir(parents=True, exist_ok=True)
        output_path = trim_dir / audio_path.name
        if output_path.resolve() == audio_path:
            print_log("复用草稿内裁剪配音素材", "Reusing draft-local trimmed voiceover", audio=output_path)
            return output_path
        if output_path.exists():
            output_path.unlink()

        codec_args = []
        if output_path.suffix.lower() == ".mp3":
            codec_args = ["-c:a", "libmp3lame", "-q:a", "2"]
        elif output_path.suffix.lower() in {".m4a", ".aac"}:
            codec_args = ["-c:a", "aac", "-b:a", "192k"]
        safe_padding = max(0.0, float(padding_seconds))
        delay_ms = int(round(safe_padding * 1000))
        silence_filter = (
            "silenceremove=start_periods=1:start_duration=0.08:start_threshold=-55dB:detection=rms,"
            "areverse,"
            "silenceremove=start_periods=1:start_duration=0.08:start_threshold=-55dB:detection=rms,"
            "areverse,"
            f"adelay={delay_ms}:all=1,"
            f"apad=pad_dur={safe_padding:g},"
            "aresample=async=1:first_pts=0"
        )
        cmd = [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-i",
            str(audio_path),
            "-af",
            silence_filter,
            *codec_args,
            str(output_path),
        ]
        print_log("裁剪配音首尾静音", "Trimming voiceover leading/trailing silence", source=audio_path, output=output_path)
        subprocess.run(cmd, check=True)
        print_log("配音静音裁剪完成", "Voiceover silence trim completed", output=output_path)
        return output_path

    output_path = resource_dir / audio_path.name
    if output_path.resolve() == audio_path:
        print_log("复用草稿内配音素材", "Reusing draft-local voiceover", audio=output_path)
        return output_path
    if not output_path.exists() or output_path.stat().st_size != audio_path.stat().st_size:
        print_log("复制配音到草稿资源", "Copying voiceover into draft resources", source=audio_path, output=output_path)
        shutil.copy2(audio_path, output_path)
    else:
        print_log("复用已复制配音素材", "Reusing copied voiceover", audio=output_path)
    return output_path


def is_jianying_mp4_compatible(video_path: str | Path) -> bool:
    """Return whether the generated MP4 uses codecs that Jianying handles reliably."""
    cmd = [
        "ffprobe",
        "-v",
        "error",
        "-show_entries",
        "stream=codec_type,codec_name",
        "-of",
        "json",
        str(video_path),
    ]
    try:
        result = subprocess.run(cmd, check=True, stdout=subprocess.PIPE)
        streams = json.loads(result.stdout).get("streams", [])
    except Exception:
        return False

    has_video = any(stream.get("codec_type") == "video" for stream in streams)
    unsupported_audio = [
        stream.get("codec_name")
        for stream in streams
        if stream.get("codec_type") == "audio" and stream.get("codec_name") not in {"aac", "mp3"}
    ]
    return has_video and not unsupported_audio


def build_clip_segments(
    matches: list[dict[str, Any]],
    viral_duration: float,
    source_duration: float,
    sample_interval: float = 1.0,
) -> list[dict[str, float]]:
    """把 1fps 镜头匹配结果转换成剪映时间线片段。"""
    segments = []
    if matches and {"target_start", "duration", "source_start"}.issubset(matches[0]):
        for match in sorted(matches, key=lambda item: float(item["target_start"])):
            target_start = max(0.0, float(match["target_start"]))
            duration = max(0.001, float(match["duration"]))
            source_start = max(0.0, float(match["source_start"]))
            if target_start >= viral_duration or source_start >= source_duration:
                continue
            duration = min(duration, max(0.001, viral_duration - target_start))
            segment = {
                "target_start": round(target_start, 6),
                "duration": round(duration, 6),
                "source_start": round(source_start, 6),
            }
            if "source_duration" in match:
                source_clip_duration = max(0.001, float(match["source_duration"]))
                source_clip_duration = min(source_clip_duration, max(0.001, source_duration - source_start))
                segment["source_duration"] = round(source_clip_duration, 6)
            segments.append(segment)
        print_log("构建剪映秒级片段时间线", "Built seconds-based Jianying clip timeline", segments=len(segments))
        return segments

    sorted_matches = sorted(matches, key=lambda item: int(item["viral_frame"]))
    for index, match in enumerate(sorted_matches):
        viral_frame = int(match["viral_frame"])
        source_frame = int(match["source_frame"])
        target_start = max(0.0, (viral_frame - 1) * sample_interval)
        if target_start >= viral_duration:
            continue

        if index + 1 < len(sorted_matches):
            next_start = max(0.0, (int(sorted_matches[index + 1]["viral_frame"]) - 1) * sample_interval)
            duration = max(0.001, next_start - target_start)
        else:
            duration = min(sample_interval, max(0.001, viral_duration - target_start))

        source_start = max(0.0, (source_frame - 1) * sample_interval)
        if source_start >= source_duration:
            continue
        duration = min(duration, max(0.001, source_duration - source_start))
        segments.append(
            {
                "target_start": round(target_start, 3),
                "duration": round(duration, 3),
                "source_start": round(source_start, 3),
            }
        )
    print_log("构建剪映片段时间线", "Built Jianying clip timeline", segments=len(segments))
    return segments


def plan_voiceover_segments(
    clip_segments: list[dict[str, float]],
    voice_segments: list[dict[str, Any]],
    media_durations: dict[str, float],
    gap_seconds: float = 0.0,
) -> list[dict[str, float | str]]:
    """Place TTS clips on their SRT anchors, shifting only real overlaps."""
    planned = []
    cursor = 0.0
    duration_by_path = {str(path): float(duration) for path, duration in media_durations.items()}
    for voice in voice_segments:
        path = str(voice["path"])
        duration = max(0.001, float(voice.get("duration", duration_by_path[path])))
        anchor_seconds = max(0.0, float(voice.get("start_ms", 0)) / 1000)
        target_start = max(anchor_seconds, cursor)
        target_start = round(target_start, 6)
        duration = round(duration, 6)
        planned.append(
            {
                "path": path,
                "target_start": target_start,
                "duration": duration,
            }
        )
        cursor = target_start + duration + max(0.0, gap_seconds)
    print_log("规划配音片段", "Planned anchored voiceover segments", segments=len(planned), gap_seconds=gap_seconds)
    return planned


def _merge_microsecond_ranges(ranges: list[tuple[int, int]]) -> list[tuple[int, int]]:
    merged: list[tuple[int, int]] = []
    for start, end in sorted((max(0, start), max(0, end)) for start, end in ranges if end > start):
        if not merged or start > merged[-1][1]:
            merged.append((start, end))
        else:
            merged[-1] = (merged[-1][0], max(merged[-1][1], end))
    return merged


def _split_video_segment_by_voiceover(
    target_start_us: int,
    target_duration_us: int,
    source_start_us: int,
    source_duration_us: int,
    voiceover_ranges_us: list[tuple[int, int]],
    *,
    ducked_volume: float,
    normal_volume: float,
) -> list[dict[str, int | float]]:
    """Split one video segment so source audio can duck only under TTS."""
    target_end_us = target_start_us + target_duration_us
    boundaries = {target_start_us, target_end_us}
    for voice_start_us, voice_end_us in voiceover_ranges_us:
        overlap_start_us = max(target_start_us, voice_start_us)
        overlap_end_us = min(target_end_us, voice_end_us)
        if overlap_start_us < overlap_end_us:
            boundaries.add(overlap_start_us)
            boundaries.add(overlap_end_us)

    ordered = sorted(boundaries)
    source_scale = source_duration_us / target_duration_us if target_duration_us > 0 else 1.0
    parts: list[dict[str, int | float]] = []
    for start_us, end_us in zip(ordered, ordered[1:]):
        if end_us <= start_us:
            continue
        overlaps_voiceover = any(start_us < voice_end and end_us > voice_start for voice_start, voice_end in voiceover_ranges_us)
        source_part_start_us = source_start_us + int(round((start_us - target_start_us) * source_scale))
        source_part_end_us = source_start_us + int(round((end_us - target_start_us) * source_scale))
        parts.append(
            {
                "target_start_us": start_us,
                "target_duration_us": max(1, end_us - start_us),
                "source_start_us": source_part_start_us,
                "source_duration_us": max(1, source_part_end_us - source_part_start_us),
                "volume": ducked_volume if overlaps_voiceover else normal_volume,
            }
        )
    return parts


def create_jianying_clip_draft(
    viral_video: str | Path,
    source_video: str | Path,
    matches: list[dict[str, Any]],
    srt_path: str | Path | None,
    audio_path: str | Path | None = None,
    draft_name: str | None = None,
    draft_folder: str | Path = DEFAULT_DRAFT_FOLDER,
    *,
    voice_segments: list[dict[str, Any]] | None = None,
    import_subtitles: bool = False,
    source_volume: float = 0.3,
    voice_gap_seconds: float = 0.0,
    trim_voice_silence: bool = True,
    voice_padding_seconds: float = 0.1,
    normal_source_volume: float = 1.0,
) -> Path:
    """创建剪映草稿：排列匹配视频片段，并可加入分段配音。"""
    import pycapcut as cc

    viral_video = Path(viral_video).expanduser().resolve()
    source_video = Path(source_video).expanduser().resolve()
    srt_path = Path(srt_path).expanduser().resolve() if srt_path else None
    audio_path = Path(audio_path).expanduser().resolve() if audio_path else None
    draft_folder = Path(draft_folder).expanduser()
    draft_folder.mkdir(parents=True, exist_ok=True)

    width, height, viral_duration = get_video_info(viral_video)
    source_width, source_height, source_duration = get_video_info(source_video)
    clip_segments = build_clip_segments(matches, viral_duration, source_duration)
    if not clip_segments:
        raise ValueError("没有可导出的匹配片段 / No matched clips to export")

    name = safe_draft_name(draft_name or viral_video.stem)
    print_log(
        "开始创建剪映片段草稿",
        "Creating Jianying clip draft",
        draft=name,
        clips=len(clip_segments),
        srt=srt_path or "",
        audio=audio_path or "",
        voice_segments=len(voice_segments or []),
    )
    script = cc.DraftFolder(str(draft_folder)).create_draft(
        name,
        width,
        height,
        allow_replace=True,
    )
    draft_path = draft_folder / name
    jianying_source_video = prepare_jianying_video_source(source_video, draft_path)

    script.add_track(cc.TrackType.video, "matched_video")
    source_material = create_video_material(cc, jianying_source_video, source_width, source_height, source_duration)
    planned_voiceovers = []
    single_audio = None
    voiceover_end_us = 0
    voiceover_ranges_us: list[tuple[int, int]] = []
    if voice_segments:
        draft_voice_segments = []
        duration_by_path = {}
        for voice in voice_segments:
            jianying_audio = prepare_jianying_audio_source(
                voice["path"],
                draft_path,
                trim_silence=trim_voice_silence,
                padding_seconds=voice_padding_seconds,
            )
            duration = get_media_duration(jianying_audio)
            segment = {**voice, "path": str(jianying_audio)}
            draft_voice_segments.append(segment)
            duration_by_path[str(jianying_audio)] = duration

        planned_voiceovers = plan_voiceover_segments(
            clip_segments,
            draft_voice_segments,
            duration_by_path,
            gap_seconds=voice_gap_seconds,
        )
        voiceover_end_us = max(
            (
                seconds_to_microseconds(float(voice["target_start"]) + float(voice["duration"]))
                for voice in planned_voiceovers
            ),
            default=0,
        )
        voiceover_ranges_us = _merge_microsecond_ranges(
            [
                (
                    seconds_to_microseconds(float(voice["target_start"])),
                    seconds_to_microseconds(float(voice["target_start"]) + float(voice["duration"])),
                )
                for voice in planned_voiceovers
            ]
        )
    elif audio_path:
        jianying_audio = prepare_jianying_audio_source(audio_path, draft_path)
        audio_duration = get_media_duration(jianying_audio)
        single_audio = (jianying_audio, audio_duration)
        voiceover_end_us = seconds_to_microseconds(audio_duration)
        voiceover_ranges_us = [(0, voiceover_end_us)]

    previous_target_end_us = 0
    for index, segment in enumerate(clip_segments, 1):
        target_start_us = seconds_to_microseconds(segment["target_start"])
        target_end_us = seconds_to_microseconds(segment["target_start"] + segment["duration"])
        if target_start_us < previous_target_end_us:
            target_start_us = previous_target_end_us
        if index == len(clip_segments) and voiceover_end_us > target_end_us:
            print_log(
                "延长最后视频片段覆盖配音",
                "Extending last video clip to cover voiceover",
                original_end_us=target_end_us,
                voiceover_end_us=voiceover_end_us,
            )
            target_end_us = voiceover_end_us
        target_duration_us = max(1, target_end_us - target_start_us)
        previous_target_end_us = target_start_us + target_duration_us

        source_clip_duration = segment.get("source_duration", segment["duration"])
        source_start_us = seconds_to_microseconds(segment["source_start"])
        source_duration_us = max(1, seconds_to_microseconds(source_clip_duration))
        speed = source_duration_us / target_duration_us if source_duration_us > 0 else None
        video_parts = _split_video_segment_by_voiceover(
            target_start_us,
            target_duration_us,
            source_start_us,
            source_duration_us,
            voiceover_ranges_us,
            ducked_volume=source_volume,
            normal_volume=normal_source_volume,
        )
        for part_index, part in enumerate(video_parts, 1):
            part_target_duration_us = int(part["target_duration_us"])
            part_source_duration_us = int(part["source_duration_us"])
            part_speed = part_source_duration_us / part_target_duration_us if part_source_duration_us > 0 else speed
            print_log(
                "添加视频片段",
                "Adding video clip",
                index=f"{index}.{part_index}" if len(video_parts) > 1 else index,
                target_start_us=part["target_start_us"],
                source_start_us=part["source_start_us"],
                duration_us=part_target_duration_us,
                source_duration_us=part_source_duration_us,
                volume=part["volume"],
            )
            script.add_segment(
                cc.VideoSegment(
                    source_material,
                    microseconds_timerange(cc, int(part["target_start_us"]), part_target_duration_us),
                    source_timerange=microseconds_timerange(cc, int(part["source_start_us"]), part_source_duration_us),
                    speed=part_speed,
                    volume=float(part["volume"]),
                ),
                "matched_video",
            )

    if planned_voiceovers:
        script.add_track(cc.TrackType.audio, "voiceover")
        for index, voice in enumerate(planned_voiceovers, 1):
            duration_us = max(1, seconds_to_microseconds(float(voice["duration"])))
            target_start_us = seconds_to_microseconds(float(voice["target_start"]))
            material = create_audio_material(cc, voice["path"], float(voice["duration"]))
            script.add_segment(
                cc.AudioSegment(
                    material,
                    microseconds_timerange(cc, target_start_us, duration_us),
                    source_timerange=microseconds_timerange(cc, 0, duration_us),
                    volume=1.0,
                ),
                "voiceover",
            )
            print_log(
                "添加分段配音",
                "Added voiceover segment",
                index=index,
                audio=voice["path"],
                target_start_us=target_start_us,
                duration_us=duration_us,
            )
    elif single_audio:
        jianying_audio, audio_duration = single_audio
        script.add_track(cc.TrackType.audio, "voiceover")
        audio_material = create_audio_material(cc, jianying_audio, audio_duration)
        script.add_segment(
            cc.AudioSegment(audio_material, seconds_timerange(cc, 0, audio_duration)),
            "voiceover",
        )
        print_log("添加配音轨", "Added voiceover track", audio=jianying_audio, duration=f"{audio_duration:.2f}")

    if import_subtitles and srt_path:
        script.import_srt(
            str(srt_path),
            track_name="srt_subtitles",
            text_style=cc.TextStyle(size=8.0, bold=True, color=(1.0, 1.0, 1.0), align=1, auto_wrapping=True),
        )
        print_log("导入 SRT 字幕", "Imported SRT subtitles", srt=srt_path)
    else:
        print_log("跳过 SRT 字幕导入", "Skipped SRT subtitle import")
    script.save()

    print_log("剪映片段草稿创建完成", "Jianying clip draft created", draft=draft_path)
    return draft_path


def create_jianying_draft(
    final_video: str | Path,
    draft_name: str,
    draft_folder: str | Path = DEFAULT_DRAFT_FOLDER,
) -> Path:
    """创建剪映草稿"""
    import pycapcut as cc

    final_video = Path(final_video).resolve()
    draft_folder = Path(draft_folder).expanduser()
    draft_folder.mkdir(parents=True, exist_ok=True)
    print_log("开始创建剪映草稿", "Creating Jianying draft", video=final_video, folder=draft_folder)

    width, height, duration = get_video_info(final_video)
    draft_safe_name = safe_draft_name(draft_name)
    script = cc.DraftFolder(str(draft_folder)).create_draft(
        draft_safe_name,
        width,
        height,
        allow_replace=True,
    )
    script.add_track(cc.TrackType.video)
    script.add_segment(cc.VideoSegment(str(final_video), seconds_timerange(cc, 0, duration)))
    script.save()
    draft_path = draft_folder / draft_safe_name
    print_log("剪映草稿创建完成", "Jianying draft created", draft=draft_path)
    return draft_path


def create_jianying_draft_with_subtitles(
    video_path: str | Path,
    srt_entries: list[dict],
    draft_name: str,
    draft_folder: str | Path = DEFAULT_DRAFT_FOLDER,
) -> Path:
    """创建带字幕的剪映草稿"""
    import pycapcut as cc

    video_path = Path(video_path).resolve()
    draft_folder = Path(draft_folder).expanduser()
    draft_folder.mkdir(parents=True, exist_ok=True)
    print_log("开始创建带字幕剪映草稿", "Creating Jianying draft with subtitles", video=video_path, subtitles=len(srt_entries))

    width, height, duration = get_video_info(video_path)
    draft_safe_name = safe_draft_name(draft_name)
    script = cc.DraftFolder(str(draft_folder)).create_draft(
        draft_safe_name,
        width,
        height,
        allow_replace=True,
    )

    # 视频轨道
    script.add_track(cc.TrackType.video)
    script.add_segment(cc.VideoSegment(str(video_path), seconds_timerange(cc, 0, duration)))

    # 字幕轨道
    script.add_track(cc.TrackType.text, "subtitles")
    style = cc.TextStyle(
        size=8.0,
        bold=True,
        color=(1.0, 1.0, 1.0),
        align=1,
        auto_wrapping=True,
        max_line_width=0.82,
    )
    border = cc.TextBorder(width=14.0, color=(0.0, 0.0, 0.0), alpha=1.0)

    for entry in srt_entries:
        dur = max(0.001, (entry["end_ms"] - entry["start_ms"]) / 1000)
        script.add_segment(
            cc.TextSegment(
                entry["text"],
                seconds_timerange(cc, entry["start_ms"] / 1000, dur),
                style=style,
                border=border,
            ),
            "subtitles",
        )

    script.save()
    draft_path = draft_folder / draft_safe_name
    print_log("带字幕剪映草稿创建完成", "Jianying draft with subtitles created", draft=draft_path)
    return draft_path
