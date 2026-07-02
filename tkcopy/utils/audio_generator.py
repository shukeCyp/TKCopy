"""音频生成工具 - 使用Minimax API生成语音"""
import json
import ssl
import subprocess
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

from tkcopy.logging_utils import print_log


def _require_minimax_settings(api_key: str, group_id: str, voice_id: str) -> None:
    missing = []
    if not api_key.strip():
        missing.append("api_key")
    if not group_id.strip():
        missing.append("group_id")
    if not voice_id.strip():
        missing.append("voice_id")
    if missing:
        raise ValueError(
            "Minimax 配置缺失 / Minimax settings missing: " + ", ".join(missing)
        )


def generate_audio(
    text: str,
    output_path: str | Path,
    api_key: str,
    group_id: str,
    base_url: str = "https://api.minimax.chat",
    model: str = "speech-02-hd",
    voice_id: str = "",
    speed: float = 1.2,
    volume: float = 1.0,
    pitch: int = 0,
    audio_format: str = "mp3",
) -> Path:
    """生成单条音频"""
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    if output_path.exists() and output_path.stat().st_size > 0:
        print_log("复用已有音频", "Reusing existing audio", output=output_path)
        return output_path

    _require_minimax_settings(api_key, group_id, voice_id)
    print_log(
        "准备生成音频",
        "Preparing TTS audio generation",
        output=output_path,
        chars=len(text),
        model=model,
        voice_id=voice_id,
    )

    url = f"{base_url.rstrip('/')}/v1/t2a_v2?GroupId={group_id}"
    body = {
        "model": model,
        "text": text,
        "stream": False,
        "voice_setting": {
            "voice_id": voice_id,
            "speed": speed,
            "vol": volume,
            "pitch": pitch,
        },
        "audio_setting": {
            "sample_rate": 32000,
            "bitrate": 128000,
            "format": audio_format,
            "channel": 1,
        },
    }

    req = urllib.request.Request(
        url,
        data=json.dumps(body, ensure_ascii=False).encode(),
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {api_key}"},
    )

    for attempt in range(3):
        try:
            print_log("发送 Minimax 请求", "Sending Minimax request", attempt=attempt + 1, output=output_path)
            with urllib.request.urlopen(req, timeout=180) as resp:
                data = json.loads(resp.read())
            break
        except (urllib.error.URLError, ssl.SSLError) as e:
            if attempt == 2:
                print_log("Minimax 请求失败", "Minimax request failed", error=e)
                raise RuntimeError(f"Minimax请求失败 / Minimax request failed: {e}") from e
            print_log("Minimax 请求失败，准备重试", "Minimax request failed, retrying", attempt=attempt + 1, error=e)
            time.sleep(2 * (attempt + 1))
    else:
        raise RuntimeError("unreachable")

    audio_hex = data.get("data", {}).get("audio")
    if not audio_hex:
        raise RuntimeError(f"Minimax未返回音频 / Minimax did not return audio: {data}")
    output_path.write_bytes(bytes.fromhex(audio_hex))
    print_log("音频生成完成", "TTS audio generated", output=output_path, bytes=output_path.stat().st_size)
    return output_path


def compose_timed_audio(
    entries: list[dict],
    audio_paths: list[Path],
    output_path: str | Path,
) -> Path:
    """按时序合成多段音频"""
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    if not entries:
        raise ValueError("字幕条目为空 / Subtitle entries are empty")
    if len(entries) != len(audio_paths):
        raise ValueError("字幕和音频数量不一致 / Subtitle and audio counts do not match")

    print_log("开始合成时间轴音频", "Composing timed audio", segments=len(entries), output=output_path)

    cmd = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y"]
    for p in audio_paths:
        cmd += ["-i", str(p)]

    filter_parts = []
    delayed = []
    total_ms = max(e["end_ms"] for e in entries) if entries else 0

    for i, entry in enumerate(entries):
        label = f"a{i}"
        filter_parts.append(
            f"[{i}:a]adelay={entry['start_ms']}|{entry['start_ms']},apad=whole_dur={total_ms/1000:.3f}[{label}]"
        )
        delayed.append(f"[{label}]")

    filter_parts.append(f"{''.join(delayed)}amix=inputs={len(delayed)}:normalize=0[out]")
    cmd += ["-filter_complex", ";".join(filter_parts), "-map", "[out]", "-c:a", "aac", str(output_path)]
    print_log("执行 ffmpeg 音频合成", "Running ffmpeg audio mix", output=output_path)
    subprocess.run(cmd, check=True)
    print_log("时间轴音频合成完成", "Timed audio composed", output=output_path)
    return output_path


def generate_srt_audio(
    srt_entries: list[dict],
    output_dir: str | Path,
    api_key: str,
    group_id: str,
    voice_id: str,
    compose_timeline: bool = True,
    **kwargs,
) -> dict:
    """为SRT每个条目生成音频并合成"""
    output_dir = Path(output_dir)
    print_log("开始批量生成配音", "Starting batch TTS generation", entries=len(srt_entries), output_dir=output_dir)
    audio_paths = []
    voice_segments = []
    for index, entry in enumerate(srt_entries, 1):
        print_log("生成配音片段", "Generating TTS segment", index=index, total=len(srt_entries), subtitle=entry["index"])
        audio_path = generate_audio(
            entry["text"],
            output_dir / f"{entry['index']:04d}.mp3",
            api_key=api_key,
            group_id=group_id,
            voice_id=voice_id,
            **kwargs,
        )
        audio_paths.append(audio_path)
        voice_segments.append(
            {
                "path": str(audio_path),
                "index": int(entry["index"]),
                "start_ms": int(entry["start_ms"]),
                "end_ms": int(entry["end_ms"]),
                "text": entry["text"],
            }
        )

    final_audio = compose_timed_audio(srt_entries, audio_paths, output_dir / "voice_timeline.m4a") if compose_timeline else None
    print_log(
        "批量配音完成",
        "Batch TTS generation completed",
        segments=len(voice_segments),
        timeline=final_audio or "",
    )
    return {
        "segments": [str(p) for p in audio_paths],
        "voice_segments": voice_segments,
        "timeline": str(final_audio) if final_audio else "",
    }
