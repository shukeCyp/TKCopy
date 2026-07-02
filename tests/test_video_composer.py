import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tkcopy.utils.video_composer import compose_video


class VideoComposerTests(unittest.TestCase):
    def test_compose_video_mixes_audio_with_shortest_duration(self):
        commands = []

        def fake_run(cmd, check):
            commands.append(cmd)
            Path(cmd[-1]).write_bytes(b"video")
            return subprocess.CompletedProcess(cmd, 0)

        with tempfile.TemporaryDirectory() as tmp, patch(
            "tkcopy.utils.video_composer.subprocess.run",
            side_effect=fake_run,
        ):
            compose_video(
                "source.mkv",
                "voice.m4a",
                Path(tmp) / "final.mp4",
                tts_entries=[{"start_ms": 0, "end_ms": 1000}],
            )

        filter_complex = commands[0][commands[0].index("-filter_complex") + 1]
        self.assertIn("amix=inputs=2:duration=shortest", filter_complex)


if __name__ == "__main__":
    unittest.main()
