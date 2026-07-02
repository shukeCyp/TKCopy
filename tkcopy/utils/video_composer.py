"""视频合成工具 - 合成最终视频"""
import subprocess
from pathlib import Path
from typing import Any

from tkcopy.logging_utils import print_log


def get_video_info(video_path: str | Path) -> tuple[int, int, float]:
    """获取视频信息: width, height, duration"""
    import json
    cmd = [
        "ffprobe", "-v", "error", "-select_streams", "v:0",
        "-show_entries", "stream=width,height,duration", "-of", "json", str(video_path),
    ]
    result = subprocess.run(cmd, check=True, stdout=subprocess.PIPE)
    data = json.loads(result.stdout)
    s = data["streams"][0]
    info = int(s["width"]), int(s["height"]), float(s["duration"])
    print_log("读取视频信息", "Read video info", video=video_path, width=info[0], height=info[1], duration=f"{info[2]:.2f}")
    return info


def compose_video(
    video_path: str | Path,
    audio_path: str | Path,
    output_path: str | Path,
    tts_entries: list[dict] | None = None,
    video_codec: str = "libx264",
    audio_codec: str = "aac",
) -> Path:
    """合成视频和音频，支持原声压低"""
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    print_log(
        "视频合成开始",
        "Video composition started",
        video=video_path,
        audio=audio_path,
        output=output_path,
        subtitles=len(tts_entries or []),
    )

    # 构建音频压低滤镜
    duck_filters = ",".join(
        f"volume=enable='between(t,{e['start_ms']/1000:.3f},{e['end_ms']/1000:.3f})':volume=0.2"
        for e in (tts_entries or [])
    ) or "anull"

    filter_complex = (
        f"[0:a:0]{duck_filters}[bg];"
        "[bg][1:a:0]amix=inputs=2:duration=shortest:dropout_transition=0,aformat=channel_layouts=stereo[aout]"
    )

    print_log("执行 ffmpeg 视频合成", "Running ffmpeg video composition", output=output_path)
    subprocess.run([
        "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
        "-i", str(video_path),
        "-i", str(audio_path),
        "-map", "0:v:0",
        "-filter_complex", filter_complex,
        "-map", "[aout]",
        "-c:v", video_codec,
        "-c:a", audio_codec,
        "-shortest", str(output_path),
    ], check=True)
    print_log("视频合成完成", "Video composition completed", output=output_path)
    return output_path


def cut_video_segments(
    source_video: str | Path,
    segments: list[dict],
    output_path: str | Path,
) -> Path:
    """按segments切分并拼接视频"""
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    print_log("开始切分拼接视频", "Cutting and concatenating video segments", segments=len(segments), output=output_path)

    # 生成临时片段
    temp_dir = output_path.parent / "temp_segments"
    temp_dir.mkdir(exist_ok=True)

    segment_files = []
    for i, seg in enumerate(segments):
        seg_path = temp_dir / f"seg_{i:04d}.mp4"
        print_log("切分视频片段", "Cutting video segment", index=i + 1, start=seg["start"], duration=seg["duration"])
        subprocess.run([
            "ffmpeg", "-y", "-ss", str(seg["start"]), "-i", str(source_video),
            "-t", str(seg["duration"]), "-c", "copy", str(seg_path),
        ], check=True, capture_output=True)
        segment_files.append(seg_path)

    # 拼接
    concat_file = temp_dir / "concat.txt"
    concat_file.write_text("\n".join(f"file '{p}'" for p in segment_files))
    subprocess.run([
        "ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(concat_file),
        "-c", "copy", str(output_path),
    ], check=True, capture_output=True)

    # 清理
    for f in segment_files:
        f.unlink()
    concat_file.unlink()

    print_log("视频片段拼接完成", "Video segments concatenated", output=output_path)
    return output_path
