"""TTS provider abstraction for narration-first workflow."""
from __future__ import annotations

import json
import shutil
import subprocess
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol
from urllib.parse import quote, urljoin
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from tkcopy.logging_utils import print_log
from tkcopy.utils.audio_generator import generate_audio


class TTSProvider(Protocol):
    name: str
    audio_format: str

    def synthesize(self, text: str, output_path: Path) -> Path:
        """Synthesize text to an audio file."""


@dataclass
class MiniMaxTTSProvider:
    api_key: str
    group_id: str
    voice_id: str
    base_url: str = "https://api.minimax.chat"
    model: str = "speech-02-hd"
    speed: float = 1.2
    volume: float = 1.0
    pitch: int = 0
    audio_format: str = "mp3"
    name: str = "minimax"

    def synthesize(self, text: str, output_path: Path) -> Path:
        return generate_audio(
            text,
            output_path,
            api_key=self.api_key,
            group_id=self.group_id,
            voice_id=self.voice_id,
            base_url=self.base_url,
            model=self.model,
            speed=self.speed,
            volume=self.volume,
            pitch=self.pitch,
            audio_format=self.audio_format,
        )


@dataclass
class VoxCPMTTSProvider:
    base_url: str
    api_type: str = "synthesize"
    voice: str = "Natasha"
    voice_refs: dict[str, str] | None = None
    control: str = ""
    seed: int | None = None
    cfg_value: float = 2.0
    inference_timesteps: int = 10
    do_normalize: bool = False
    denoise: bool = False
    audio_format: str = "wav"
    timeout: int = 900
    name: str = "voxcpm"

    def synthesize(self, text: str, output_path: Path) -> Path:
        base_url = self.base_url.rstrip("/")
        if not base_url:
            raise ValueError("VoxCPM 配置缺失 / VoxCPM settings missing: base_url")
        if not self.voice.strip():
            raise ValueError("VoxCPM 配置缺失 / VoxCPM settings missing: voice")
        if self.api_type.strip().lower() == "gradio":
            return self._synthesize_gradio(base_url, text, output_path)

        return self._synthesize_remote(base_url, text, output_path)

    def _synthesize_remote(self, base_url: str, text: str, output_path: Path) -> Path:
        payload = {
            "text": text,
            "voice": self.voice,
            "control": self.control,
            "seed": self.seed,
            "cfg_value": self.cfg_value,
            "inference_timesteps": self.inference_timesteps,
            "audio_format": self.audio_format,
        }
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        request = Request(
            f"{base_url}/synthesize",
            data=body,
            headers={"Content-Type": "application/json", "Accept": "audio/*"},
            method="POST",
        )
        print_log(
            "调用 VoxCPM 远程配音服务",
            "Calling VoxCPM remote TTS service",
            base_url=base_url,
            voice=self.voice,
            chars=len(text),
        )
        try:
            with urlopen(request, timeout=self.timeout) as response:
                audio_bytes = response.read()
        except HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"VoxCPM 请求失败 / VoxCPM request failed: HTTP {exc.code} {detail}") from exc
        except URLError as exc:
            raise RuntimeError(f"VoxCPM 请求失败 / VoxCPM request failed: {exc.reason}") from exc

        if not audio_bytes:
            raise RuntimeError("VoxCPM 返回空音频 / VoxCPM returned empty audio")

        return self._write_audio(output_path, audio_bytes)

    def _synthesize_gradio(self, base_url: str, text: str, output_path: Path) -> Path:
        ref_wav = self._upload_gradio_reference(base_url)
        payload = {
            "text": text,
            "control_instruction": self.control,
            "ref_wav": ref_wav,
            "use_prompt_text": False,
            "prompt_text_value": "",
            "cfg_value": self.cfg_value,
            "do_normalize": self.do_normalize,
            "denoise": self.denoise,
            "dit_steps": self.inference_timesteps,
            "seed_value": self.seed if self.seed is not None else 42,
        }
        print_log(
            "调用 VoxCPM 本地 Gradio 配音服务",
            "Calling local VoxCPM Gradio TTS service",
            base_url=base_url,
            voice=self.voice,
            chars=len(text),
        )
        try:
            response = self._post_json(f"{base_url}/gradio_api/call/v2/generate", payload)
        except RuntimeError as exc:
            if not _is_gradio_v2_fallback_error(exc):
                raise
            print_log(
                "VoxCPM Gradio v2 不可用，切换旧版协议",
                "VoxCPM Gradio v2 unavailable; falling back to legacy protocol",
            )
            response = self._post_json(
                f"{base_url}/gradio_api/call/generate",
                {
                    "data": [
                        payload["text"],
                        payload["control_instruction"],
                        payload["ref_wav"],
                        payload["use_prompt_text"],
                        payload["prompt_text_value"],
                        payload["cfg_value"],
                        payload["do_normalize"],
                        payload["denoise"],
                        payload["dit_steps"],
                        payload["seed_value"],
                    ]
                },
            )
        event_id = response.get("event_id")
        if not event_id:
            raise RuntimeError(f"VoxCPM Gradio 未返回 event_id / missing event_id: {response}")

        gradio_data = self._wait_gradio_result(base_url, str(event_id))
        file_data = self._extract_gradio_file_data(gradio_data)
        audio_bytes = self._download_gradio_audio(base_url, file_data)
        if not audio_bytes:
            raise RuntimeError("VoxCPM Gradio 返回空音频 / VoxCPM Gradio returned empty audio")
        return self._write_audio(output_path, audio_bytes)

    def _upload_gradio_reference(self, base_url: str) -> dict[str, Any] | None:
        ref_value = str((self.voice_refs or {}).get(self.voice, "") or "").strip()
        if not ref_value:
            print_log("VoxCPM 未配置参考音频", "VoxCPM reference audio not configured", voice=self.voice)
            return None
        ref_path = Path(ref_value).expanduser()
        if not ref_path.exists():
            raise FileNotFoundError(f"VoxCPM 参考音频不存在 / reference audio missing: {ref_path}")

        boundary = f"----TKCopyVoxCPM{uuid.uuid4().hex}"
        body = b"".join(
            [
                f"--{boundary}\r\n".encode("utf-8"),
                f'Content-Disposition: form-data; name="files"; filename="{ref_path.name}"\r\n'.encode("utf-8"),
                b"Content-Type: application/octet-stream\r\n\r\n",
                ref_path.read_bytes(),
                f"\r\n--{boundary}--\r\n".encode("utf-8"),
            ]
        )
        request = Request(
            f"{base_url}/gradio_api/upload",
            data=body,
            headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
            method="POST",
        )
        print_log("上传 VoxCPM 参考音频", "Uploading VoxCPM reference audio", voice=self.voice, path=ref_path)
        uploaded = json.loads(self._read_url(request).decode("utf-8"))
        uploaded_path: str | None = None
        if isinstance(uploaded, list) and uploaded:
            first = uploaded[0]
            uploaded_path = first.get("path") if isinstance(first, dict) else str(first)
        elif isinstance(uploaded, dict):
            uploaded_path = uploaded.get("path") or uploaded.get("name")
        if not uploaded_path:
            raise RuntimeError(f"VoxCPM Gradio 上传失败 / upload failed: {uploaded}")
        return {"path": uploaded_path, "meta": {"_type": "gradio.FileData"}}

    def _post_json(self, url: str, payload: dict[str, Any]) -> dict[str, Any]:
        request = Request(
            url,
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            headers={"Content-Type": "application/json", "Accept": "application/json"},
            method="POST",
        )
        return json.loads(self._read_url(request).decode("utf-8"))

    def _wait_gradio_result(self, base_url: str, event_id: str) -> Any:
        deadline = time.monotonic() + max(1, self.timeout)
        event_url = f"{base_url}/gradio_api/call/generate/{event_id}"
        last_data: Any = None
        while True:
            body = self._read_url(event_url).decode("utf-8", errors="replace")
            event_name = ""
            for raw_line in body.splitlines():
                line = raw_line.strip()
                if not line:
                    continue
                if line.startswith("event:"):
                    event_name = line.split(":", 1)[1].strip()
                    continue
                if not line.startswith("data:"):
                    continue
                data_text = line.split(":", 1)[1].strip()
                data = json.loads(data_text)
                if event_name == "error":
                    raise RuntimeError(f"VoxCPM Gradio 生成失败 / generation failed: {data}")
                last_data = data
                if event_name == "complete":
                    return data
            if last_data is not None:
                return last_data
            if time.monotonic() >= deadline:
                raise TimeoutError(f"VoxCPM Gradio 超时 / timed out waiting for event: {event_id}")
            time.sleep(0.5)

    def _extract_gradio_file_data(self, gradio_data: Any) -> dict[str, Any]:
        data = gradio_data.get("data", gradio_data) if isinstance(gradio_data, dict) else gradio_data
        if isinstance(data, list) and data:
            first = data[0]
            if isinstance(first, list) and first:
                first = first[0]
            if isinstance(first, dict):
                return first
        if isinstance(data, dict) and ("url" in data or "path" in data):
            return data
        raise RuntimeError(f"VoxCPM Gradio 返回格式无法识别 / unexpected response: {gradio_data}")

    def _download_gradio_audio(self, base_url: str, file_data: dict[str, Any]) -> bytes:
        file_url = file_data.get("url")
        if file_url:
            download_url = file_url if str(file_url).startswith(("http://", "https://")) else urljoin(f"{base_url}/", str(file_url).lstrip("/"))
        else:
            file_path = file_data.get("path")
            if not file_path:
                raise RuntimeError(f"VoxCPM Gradio 缺少音频路径 / missing audio path: {file_data}")
            download_url = f"{base_url}/gradio_api/file={quote(str(file_path), safe='/:._-')}"
        return self._read_url(download_url)

    def _read_url(self, request_or_url) -> bytes:
        try:
            with urlopen(request_or_url, timeout=self.timeout) as response:
                return response.read()
        except HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"VoxCPM 请求失败 / VoxCPM request failed: HTTP {exc.code} {detail}") from exc
        except URLError as exc:
            raise RuntimeError(f"VoxCPM 请求失败 / VoxCPM request failed: {exc.reason}") from exc

    def _write_audio(self, output_path: Path, audio_bytes: bytes) -> Path:
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(audio_bytes)
        print_log("VoxCPM 配音完成", "VoxCPM audio generated", output=output_path, bytes=len(audio_bytes))
        return output_path


def _is_gradio_v2_fallback_error(exc: RuntimeError) -> bool:
    message = str(exc)
    return any(code in message for code in ("HTTP 405", "HTTP 422", "HTTP 500"))


def get_media_duration(media_path: str | Path) -> float:
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
    return float(result.stdout.decode().strip())


def append_trailing_pause(input_path: str | Path, output_path: str | Path, pause_ms: int) -> Path:
    """Append provider-independent silence after synthesized narration."""
    input_path = Path(input_path)
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    if pause_ms <= 0:
        shutil.copy2(input_path, output_path)
        return output_path

    pause_seconds = max(0.0, pause_ms / 1000)
    codec_args = []
    if output_path.suffix.lower() == ".mp3":
        codec_args = ["-c:a", "libmp3lame", "-q:a", "2"]
    elif output_path.suffix.lower() in {".m4a", ".aac"}:
        codec_args = ["-c:a", "aac", "-b:a", "192k"]
    cmd = [
        "ffmpeg",
        "-hide_banner",
        "-loglevel",
        "error",
        "-y",
        "-i",
        str(input_path),
        "-af",
        f"apad=pad_dur={pause_seconds:g},aresample=async=1:first_pts=0",
        *codec_args,
        str(output_path),
    ]
    subprocess.run(cmd, check=True)
    return output_path


def synthesize_narration_audio(
    beats: list[dict[str, Any]],
    output_dir: str | Path,
    provider: TTSProvider,
) -> dict[str, Any]:
    """Generate beat-level narration audio and keep each beat near its source anchor."""
    output_dir = Path(output_dir)
    raw_dir = output_dir / "raw"
    output_dir.mkdir(parents=True, exist_ok=True)
    raw_dir.mkdir(parents=True, exist_ok=True)

    audio_paths: list[Path] = []
    voice_segments: list[dict[str, Any]] = []
    cursor_ms: int | None = None
    print_log("开始生成 beat 级配音", "Starting beat-level TTS generation", beats=len(beats), provider=provider.name)
    for index, beat in enumerate(beats, 1):
        audio_format = getattr(provider, "audio_format", "mp3") or "mp3"
        raw_path = raw_dir / f"{index:04d}.{audio_format}"
        audio_path = output_dir / f"{index:04d}.{audio_format}"
        text = str(beat["text"])
        print_log("生成 beat 配音", "Generating beat TTS", index=index, chars=len(text))
        provider.synthesize(text, raw_path)
        append_trailing_pause(raw_path, audio_path, int(beat.get("pause_after_ms", 0)))
        duration_ms = int(round(get_media_duration(audio_path) * 1000))
        anchor_start_ms = int(beat.get("anchor_start_ms", 0))
        start_ms = max(anchor_start_ms, cursor_ms or 0)
        end_ms = start_ms + duration_ms
        cursor_ms = end_ms
        audio_paths.append(audio_path)
        voice_segments.append(
            {
                "path": str(audio_path),
                "index": int(beat.get("index", index)),
                "start_ms": start_ms,
                "end_ms": end_ms,
                "anchor_start_ms": anchor_start_ms,
                "anchor_end_ms": int(beat.get("anchor_end_ms", end_ms)),
                "duration_ms": duration_ms,
                "text": text,
                "provider": provider.name,
            }
        )

    manifest_path = output_dir / "tts_result_manifest.json"
    manifest_path.write_text(
        json.dumps({"provider": provider.name, "voice_segments": voice_segments}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print_log("beat 级配音完成", "Beat-level TTS completed", segments=len(voice_segments), manifest=manifest_path)
    return {
        "segments": [str(path) for path in audio_paths],
        "voice_segments": voice_segments,
        "timeline": "",
        "manifest": str(manifest_path),
    }
