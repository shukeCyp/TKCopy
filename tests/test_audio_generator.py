import tempfile
import json
import unittest
from pathlib import Path
from unittest.mock import patch

from tkcopy.utils.audio_generator import generate_audio, generate_srt_audio


class AudioGeneratorTests(unittest.TestCase):
    def test_generate_audio_requires_minimax_credentials_before_network(self):
        with tempfile.TemporaryDirectory() as tmp:
            with patch("tkcopy.utils.audio_generator.urllib.request.urlopen") as urlopen:
                with self.assertRaisesRegex(ValueError, "Minimax"):
                    generate_audio(
                        "hello",
                        Path(tmp) / "voice.mp3",
                        api_key="",
                        group_id="",
                        voice_id="",
                    )

        urlopen.assert_not_called()

    def test_generate_audio_uses_default_tts_speed_1_2(self):
        captured = {}

        class FakeResponse:
            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

            def read(self):
                return json.dumps({"data": {"audio": "00"}}).encode()

        def fake_urlopen(request, timeout):
            captured["body"] = json.loads(request.data.decode())
            captured["timeout"] = timeout
            return FakeResponse()

        with tempfile.TemporaryDirectory() as tmp:
            with patch("tkcopy.utils.audio_generator.urllib.request.urlopen", fake_urlopen):
                generate_audio(
                    "hello",
                    Path(tmp) / "voice.mp3",
                    api_key="key",
                    group_id="group",
                    voice_id="voice",
                )

        self.assertEqual(captured["body"]["voice_setting"]["speed"], 1.2)

    def test_generate_srt_audio_can_return_segment_details_without_timeline_mix(self):
        entries = [
            {"index": 1, "start_ms": 500, "end_ms": 1500, "text": "first"},
            {"index": 2, "start_ms": 2500, "end_ms": 3500, "text": "second"},
        ]

        with tempfile.TemporaryDirectory() as tmp:
            with patch("tkcopy.utils.audio_generator.generate_audio") as generate:
                def fake_generate(_text, output_path, **_kwargs):
                    output_path = Path(output_path)
                    output_path.write_bytes(b"mp3")
                    return output_path

                generate.side_effect = fake_generate

                result = generate_srt_audio(
                    entries,
                    Path(tmp),
                    api_key="key",
                    group_id="group",
                    voice_id="voice",
                    compose_timeline=False,
                )

        self.assertEqual(result["timeline"], "")
        self.assertEqual(len(result["segments"]), 2)
        self.assertEqual(
            result["voice_segments"],
            [
                {"path": result["segments"][0], "index": 1, "start_ms": 500, "end_ms": 1500, "text": "first"},
                {"path": result["segments"][1], "index": 2, "start_ms": 2500, "end_ms": 3500, "text": "second"},
            ],
        )


if __name__ == "__main__":
    unittest.main()
