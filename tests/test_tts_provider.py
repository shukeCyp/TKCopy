import tempfile
import unittest
from pathlib import Path
import json
from unittest.mock import patch
from urllib.error import HTTPError

from tkcopy.utils.tts_provider import MiniMaxTTSProvider, VoxCPMTTSProvider, synthesize_narration_audio


class TTSProviderTests(unittest.TestCase):
    def test_minimax_provider_wraps_existing_audio_generator(self):
        with tempfile.TemporaryDirectory() as tmp, patch("tkcopy.utils.tts_provider.generate_audio") as generate:
            output = Path(tmp) / "voice.mp3"
            generate.return_value = output
            provider = MiniMaxTTSProvider(
                api_key="api",
                group_id="group",
                voice_id="voice",
                base_url="https://api.minimax.chat",
                model="speech-2.8-hd",
                speed=1.2,
                volume=1.0,
                pitch=0,
                audio_format="mp3",
            )

            result = provider.synthesize("hello", output)

        self.assertEqual(result, output)
        generate.assert_called_once_with(
            "hello",
            output,
            api_key="api",
            group_id="group",
            voice_id="voice",
            base_url="https://api.minimax.chat",
            model="speech-2.8-hd",
            speed=1.2,
            volume=1.0,
            pitch=0,
            audio_format="mp3",
        )

    def test_voxcpm_provider_posts_text_and_voice_to_remote_service(self):
        class Response:
            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

            def read(self):
                return b"wav-bytes"

        with tempfile.TemporaryDirectory() as tmp, patch("tkcopy.utils.tts_provider.urlopen", return_value=Response()) as urlopen:
            output = Path(tmp) / "voice.wav"
            provider = VoxCPMTTSProvider(
                base_url="https://tts.example.com/",
                voice="Natasha",
                control="calm",
                seed=123,
                cfg_value=2.5,
                inference_timesteps=12,
                audio_format="wav",
                timeout=30,
            )

            result = provider.synthesize("hello world", output)
            output_bytes = output.read_bytes()

        self.assertEqual(result, output)
        self.assertEqual(output_bytes, b"wav-bytes")
        request = urlopen.call_args.args[0]
        payload = json.loads(request.data.decode("utf-8"))
        self.assertEqual(request.full_url, "https://tts.example.com/synthesize")
        self.assertEqual(payload["text"], "hello world")
        self.assertEqual(payload["voice"], "Natasha")
        self.assertEqual(payload["control"], "calm")
        self.assertEqual(payload["seed"], 123)
        self.assertEqual(payload["cfg_value"], 2.5)
        self.assertEqual(payload["inference_timesteps"], 12)

    def test_voxcpm_provider_uses_gradio_api_with_reference_voice(self):
        class Response:
            def __init__(self, body):
                self.body = body

            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

            def read(self):
                return self.body

        calls = []

        def fake_urlopen(request, timeout=None):
            url = request.full_url if hasattr(request, "full_url") else request
            calls.append((url, getattr(request, "data", None), dict(getattr(request, "header_items", lambda: [])())))
            if url == "http://127.0.0.1:8808/gradio_api/upload":
                self.assertIn("multipart/form-data", request.get_header("Content-type"))
                self.assertIn(b"Natasha.mp3", request.data)
                return Response(json.dumps(["/tmp/gradio/Natasha.mp3"]).encode("utf-8"))
            if url == "http://127.0.0.1:8808/gradio_api/call/v2/generate":
                payload = json.loads(request.data.decode("utf-8"))
                self.assertEqual(payload["text"], "hello local")
                self.assertEqual(payload["control_instruction"], "cinematic")
                self.assertEqual(payload["ref_wav"]["path"], "/tmp/gradio/Natasha.mp3")
                self.assertFalse(payload["use_prompt_text"])
                self.assertEqual(payload["cfg_value"], 2.75)
                self.assertTrue(payload["do_normalize"])
                self.assertTrue(payload["denoise"])
                self.assertEqual(payload["dit_steps"], 14)
                self.assertEqual(payload["seed_value"], 9)
                return Response(json.dumps({"event_id": "evt-1"}).encode("utf-8"))
            if url == "http://127.0.0.1:8808/gradio_api/call/generate/evt-1":
                body = (
                    "event: complete\n"
                    'data: [{"path": "/tmp/generated.wav", "url": "/gradio_api/file=/tmp/generated.wav", '
                    '"meta": {"_type": "gradio.FileData"}}, 9]\n\n'
                )
                return Response(body.encode("utf-8"))
            if url == "http://127.0.0.1:8808/gradio_api/file=/tmp/generated.wav":
                return Response(b"wav-bytes")
            raise AssertionError(f"unexpected url: {url}")

        with tempfile.TemporaryDirectory() as tmp, patch("tkcopy.utils.tts_provider.urlopen", side_effect=fake_urlopen):
            ref_path = Path(tmp) / "Natasha.mp3"
            ref_path.write_bytes(b"ref-audio")
            output = Path(tmp) / "voice.wav"
            provider = VoxCPMTTSProvider(
                base_url="http://127.0.0.1:8808/",
                api_type="gradio",
                voice="Natasha",
                voice_refs={"Natasha": str(ref_path)},
                control="cinematic",
                seed=9,
                cfg_value=2.75,
                inference_timesteps=14,
                do_normalize=True,
                denoise=True,
                audio_format="wav",
                timeout=30,
            )

            result = provider.synthesize("hello local", output)
            output_bytes = output.read_bytes()

        self.assertEqual(result, output)
        self.assertEqual(output_bytes, b"wav-bytes")
        self.assertEqual([call[0] for call in calls], [
            "http://127.0.0.1:8808/gradio_api/upload",
            "http://127.0.0.1:8808/gradio_api/call/v2/generate",
            "http://127.0.0.1:8808/gradio_api/call/generate/evt-1",
            "http://127.0.0.1:8808/gradio_api/file=/tmp/generated.wav",
        ])

    def test_voxcpm_provider_falls_back_to_legacy_gradio_call_protocol(self):
        class Response:
            def __init__(self, body):
                self.body = body

            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

            def read(self):
                return self.body

        calls = []

        def fake_urlopen(request, timeout=None):
            url = request.full_url if hasattr(request, "full_url") else request
            calls.append(url)
            if url == "http://127.0.0.1:8808/gradio_api/call/v2/generate":
                raise HTTPError(url, 405, "Method Not Allowed", {}, None)
            if url == "http://127.0.0.1:8808/gradio_api/call/generate":
                payload = json.loads(request.data.decode("utf-8"))
                self.assertEqual(
                    payload["data"],
                    ["hello local", "cinematic", None, False, "", 2.75, True, False, 14, 9],
                )
                return Response(json.dumps({"event_id": "evt-legacy"}).encode("utf-8"))
            if url == "http://127.0.0.1:8808/gradio_api/call/generate/evt-legacy":
                body = (
                    "event: complete\n"
                    'data: [{"path": "/tmp/generated.wav", "url": "/gradio_api/file=/tmp/generated.wav"}, 9]\n\n'
                )
                return Response(body.encode("utf-8"))
            if url == "http://127.0.0.1:8808/gradio_api/file=/tmp/generated.wav":
                return Response(b"wav-bytes")
            raise AssertionError(f"unexpected url: {url}")

        with tempfile.TemporaryDirectory() as tmp, patch("tkcopy.utils.tts_provider.urlopen", side_effect=fake_urlopen):
            output = Path(tmp) / "voice.wav"
            provider = VoxCPMTTSProvider(
                base_url="http://127.0.0.1:8808",
                api_type="gradio",
                voice="Natasha",
                control="cinematic",
                seed=9,
                cfg_value=2.75,
                inference_timesteps=14,
                do_normalize=True,
                denoise=False,
                audio_format="wav",
                timeout=30,
            )

            result = provider.synthesize("hello local", output)
            output_bytes = output.read_bytes()

        self.assertEqual(result, output)
        self.assertEqual(output_bytes, b"wav-bytes")
        self.assertEqual(calls[:2], [
            "http://127.0.0.1:8808/gradio_api/call/v2/generate",
            "http://127.0.0.1:8808/gradio_api/call/generate",
        ])

    def test_voxcpm_provider_falls_back_to_legacy_gradio_protocol_when_v2_returns_500(self):
        class Response:
            def __init__(self, body):
                self.body = body

            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

            def read(self):
                return self.body

        calls = []

        def fake_urlopen(request, timeout=None):
            url = request.full_url if hasattr(request, "full_url") else request
            calls.append(url)
            if url == "https://tts.example.com/gradio_api/call/v2/generate":
                raise HTTPError(url, 500, "Internal Server Error", {}, None)
            if url == "https://tts.example.com/gradio_api/call/generate":
                payload = json.loads(request.data.decode("utf-8"))
                self.assertEqual(payload["data"][0], "hello remote")
                return Response(json.dumps({"event_id": "evt-500"}).encode("utf-8"))
            if url == "https://tts.example.com/gradio_api/call/generate/evt-500":
                body = (
                    "event: complete\n"
                    'data: [{"path": "/tmp/generated.wav", "url": "/gradio_api/file=/tmp/generated.wav"}, 42]\n\n'
                )
                return Response(body.encode("utf-8"))
            if url == "https://tts.example.com/gradio_api/file=/tmp/generated.wav":
                return Response(b"wav-bytes")
            raise AssertionError(f"unexpected url: {url}")

        with tempfile.TemporaryDirectory() as tmp, patch("tkcopy.utils.tts_provider.urlopen", side_effect=fake_urlopen):
            output = Path(tmp) / "voice.wav"
            provider = VoxCPMTTSProvider(
                base_url="https://tts.example.com",
                api_type="gradio",
                voice="Natasha",
                voice_refs={},
                audio_format="wav",
                timeout=30,
            )

            result = provider.synthesize("hello remote", output)
            output_bytes = output.read_bytes()

        self.assertEqual(result, output)
        self.assertEqual(output_bytes, b"wav-bytes")
        self.assertEqual(calls[:2], [
            "https://tts.example.com/gradio_api/call/v2/generate",
            "https://tts.example.com/gradio_api/call/generate",
        ])

    def test_synthesize_narration_audio_keeps_beats_near_source_anchors(self):
        class FakeProvider:
            name = "fake"
            audio_format = "mp3"

            def synthesize(self, text, output_path):
                output_path.write_bytes(text.encode())
                return output_path

        beats = [
            {"index": 1, "anchor_start_ms": 8660, "anchor_end_ms": 11810, "text": "first", "pause_after_ms": 120},
            {"index": 2, "anchor_start_ms": 30900, "anchor_end_ms": 34180, "text": "second", "pause_after_ms": 100},
        ]

        def fake_append_pause(src, dst, pause_ms):
            dst.write_bytes(Path(src).read_bytes())
            return dst

        with tempfile.TemporaryDirectory() as tmp:
            with (
                patch("tkcopy.utils.tts_provider.append_trailing_pause", side_effect=fake_append_pause),
                patch("tkcopy.utils.tts_provider.get_media_duration", side_effect=[1.25, 2.0]),
            ):
                result = synthesize_narration_audio(beats, Path(tmp), FakeProvider())

        self.assertEqual(result["timeline"], "")
        self.assertEqual(len(result["segments"]), 2)
        self.assertEqual(
            result["voice_segments"],
            [
                {
                    "path": result["segments"][0],
                    "index": 1,
                    "start_ms": 8660,
                    "end_ms": 9910,
                    "anchor_start_ms": 8660,
                    "anchor_end_ms": 11810,
                    "duration_ms": 1250,
                    "text": "first",
                    "provider": "fake",
                },
                {
                    "path": result["segments"][1],
                    "index": 2,
                    "start_ms": 30900,
                    "end_ms": 32900,
                    "anchor_start_ms": 30900,
                    "anchor_end_ms": 34180,
                    "duration_ms": 2000,
                    "text": "second",
                    "provider": "fake",
                },
            ],
        )


if __name__ == "__main__":
    unittest.main()
