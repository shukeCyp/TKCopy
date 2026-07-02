from pathlib import Path
import inspect
import numpy as np
import subprocess
import sys
import tempfile
import types
import unittest
from unittest.mock import patch

from tkcopy.utils import tts_extractor
from tkcopy.utils.tts_extractor import load_whisper_model, resolve_whisper_model_name


class TtsExtractorTests(unittest.TestCase):
    def test_resolve_whisper_model_name_accepts_model_name_and_ggml_filename(self):
        self.assertEqual(resolve_whisper_model_name("base"), "base")
        self.assertEqual(resolve_whisper_model_name("model/ggml-base.bin"), "base")

    def test_load_whisper_model_uses_local_file_without_download(self):
        calls = []

        class FakeWhisper:
            @staticmethod
            def from_pretrained(model_name):
                raise AssertionError(f"unexpected download for {model_name}")

        class FakeContext:
            def __init__(self):
                self.reset_called = False

            def reset_timings(self):
                self.reset_called = True

        class FakeContextFactory:
            @staticmethod
            def from_file(filename, no_state=False):
                calls.append((filename, no_state))
                return FakeContext()

        class FakeParams:
            @staticmethod
            def from_enum(_sampling_enum):
                return FakeParams()

            def with_print_progress(self, _enabled):
                return self

            def with_print_realtime(self, _enabled):
                return self

            def build(self):
                return self

        fake_wp = types.SimpleNamespace(
            Whisper=FakeWhisper,
            api=types.SimpleNamespace(
                Context=FakeContextFactory,
                Params=FakeParams,
                SAMPLING_GREEDY=object(),
            ),
        )

        with tempfile.TemporaryDirectory() as tmp, patch.dict(sys.modules, {"whispercpp": fake_wp}):
            model_path = Path(tmp) / "ggml-large-v3-turbo.bin"
            model_path.write_bytes(b"fake model")

            model = load_whisper_model(model_path)

        self.assertEqual(calls, [(str(model_path), False)])
        self.assertTrue(model.context.reset_called)
        self.assertTrue(model._context_initialized)

    def test_transcribe_with_local_model_uses_whisper_cli(self):
        commands = []

        def fake_run(cmd, check):
            commands.append(cmd)
            output_stem = Path(cmd[cmd.index("-of") + 1])
            output_stem.with_suffix(".srt").write_text(
                "1\n00:00:00,000 --> 00:00:01,000\nhello\n\n",
                encoding="utf-8",
            )
            return subprocess.CompletedProcess(cmd, 0)

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            audio_path = root / "audio.wav"
            model_path = root / "ggml-large-v3-turbo.bin"
            audio_path.write_bytes(b"fake audio")
            model_path.write_bytes(b"fake model")

            with (
                patch("tkcopy.utils.tts_extractor.shutil.which", return_value="/usr/local/bin/whisper-cli"),
                patch("tkcopy.utils.tts_extractor.subprocess.run", side_effect=fake_run),
                patch("tkcopy.utils.tts_extractor.load_whisper_model") as load_model,
            ):
                srt_path = tts_extractor.transcribe_with_whisper(audio_path, model_path, root / "out")

        self.assertEqual(srt_path.name, "transcript.srt")
        self.assertEqual(commands[0][0], "/usr/local/bin/whisper-cli")
        self.assertIn("-osrt", commands[0])
        load_model.assert_not_called()

    def test_transcription_uses_loader_not_direct_constructor(self):
        source = Path("tkcopy/utils/tts_extractor.py").read_text(encoding="utf-8")

        self.assertIn("load_whisper_model", source)
        self.assertNotIn("wp.Whisper(str", source)

    def test_run_tts_extraction_uses_vocal_pipeline_without_gemini(self):
        with tempfile.TemporaryDirectory() as tmp:
            output_dir = Path(tmp)
            video_path = output_dir / "viral.mp4"
            vad_model = output_dir / "vad.bin"
            video_path.write_bytes(b"video")
            vad_model.write_bytes(b"vad")

            def fake_extract_audio(_video_path, output_path):
                output_path = Path(output_path)
                output_path.write_bytes(b"audio")
                return output_path

            with (
                patch("tkcopy.utils.tts_extractor.extract_audio", side_effect=fake_extract_audio),
                patch("tkcopy.utils.tts_extractor.separate_vocals") as separate_vocals,
                patch("tkcopy.utils.tts_extractor.split_speech_segments") as split_speech_segments,
                patch("tkcopy.utils.tts_extractor.select_dominant_speaker") as select_dominant_speaker,
                patch("tkcopy.utils.tts_extractor.transcribe_segments_to_srt") as transcribe_segments_to_srt,
            ):
                vocals_path = output_dir / "vocals.wav"
                accompaniment_path = output_dir / "no_vocals.wav"
                segments_json = output_dir / "segments.json"
                dominant_json = output_dir / "dominant_segments.json"
                report_json = output_dir / "speaker_report.json"
                final_srt = output_dir / "viral.final_tts.srt"
                vocals_path.write_bytes(b"vocals")
                accompaniment_path.write_bytes(b"music")
                segments_json.write_text("[]", encoding="utf-8")
                dominant_json.write_text("[]", encoding="utf-8")
                final_srt.write_text(
                    "1\n00:00:00,000 --> 00:00:01,000\nBarney and Marshall were in a silent war.\n\n",
                    encoding="utf-8",
                )
                separate_vocals.return_value = tts_extractor.VocalSeparationResult(
                    output_dir / "separated",
                    vocals_path,
                    accompaniment_path,
                )
                split_speech_segments.return_value = tts_extractor.SpeechSegmentsResult(
                    output_dir / "vad_segments",
                    segments_json,
                    [],
                )
                select_dominant_speaker.return_value = tts_extractor.DominantSpeakerResult(
                    dominant_json,
                    report_json,
                    0,
                    [],
                )
                transcribe_segments_to_srt.return_value = tts_extractor.SegmentAsrResult(
                    final_srt,
                    [(0, 1000, "Barney and Marshall were in a silent war.")],
                )

                result = tts_extractor.run_tts_extraction(
                    video_path,
                    "model.bin",
                    output_dir,
                    vad_model=vad_model,
                )

            final_text = Path(result["srt_path"]).read_text(encoding="utf-8")

            self.assertIn("Barney and Marshall were in a silent war.", final_text)
            separate_vocals.assert_called_once()
            split_speech_segments.assert_called_once()
            select_dominant_speaker.assert_called_once()
            transcribe_segments_to_srt.assert_called_once_with(
                dominant_json,
                whisper_model="model.bin",
                output_srt=final_srt,
                work_dir=output_dir / "segment_asr",
                language="en",
                prompt="",
                max_len=50,
                split_on_word=True,
                speaker_filter=True,
                speaker_threshold=0.3,
                timing_offset_ms=820,
                hf_token=None,
                model_source=tts_extractor.PYANNOTE_EMBEDDING_MODEL,
            )
            self.assertEqual(len(result["entries"]), 1)

    def test_tts_extraction_signature_has_no_llm_script_extraction_args(self):
        signature = inspect.signature(tts_extractor.run_tts_extraction)

        for removed_arg in ("api_key", "llm_model", "base_url", "min_word_overlap", "refresh_gemini"):
            self.assertNotIn(removed_arg, signature.parameters)

        source = Path("tkcopy/utils/tts_extractor.py").read_text(encoding="utf-8")
        self.assertNotIn("gemini_audio_text", source)

    def test_transcribe_segments_to_srt_can_filter_asr_lines_by_speaker(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            commands = []
            segment_audio = root / "segment_0001.wav"
            segment_audio.write_bytes(b"audio")
            segments_json = root / "segments.json"
            segments_json.write_text(
                '[{"index": 1, "start_ms": 1000, "end_ms": 5000, "duration_ms": 4000, "audio_path": "%s"}]'
                % str(segment_audio),
                encoding="utf-8",
            )

            def fake_run(cmd, check, stdout=None, stderr=None):
                commands.append(cmd)
                output_stem = Path(cmd[cmd.index("-of") + 1])
                output_stem.with_suffix(".srt").write_text(
                    "1\n00:00:00,000 --> 00:00:01,000\nkeep this line\n\n"
                    "2\n00:00:01,000 --> 00:00:02,000\nremove this line\n\n",
                    encoding="utf-8",
                )
                return subprocess.CompletedProcess(cmd, 0)

            with (
                patch("tkcopy.utils.tts_extractor.shutil.which", return_value="/usr/local/bin/whisper-cli"),
                patch("tkcopy.utils.tts_extractor.subprocess.run", side_effect=fake_run),
                patch(
                    "tkcopy.utils.tts_extractor._filter_asr_entries_by_dominant_speaker",
                    return_value=[(1000, 2000, "keep this line")],
                ) as filter_entries,
            ):
                result = tts_extractor.transcribe_segments_to_srt(
                    segments_json,
                    whisper_model="model.bin",
                    output_srt=root / "out.srt",
                    work_dir=root / "work",
                    speaker_filter=True,
                    speaker_threshold=0.31,
                    timing_offset_ms=0,
                    hf_token="hf",
                    model_source="speaker-model",
                )
                srt_text = result.srt_path.read_text(encoding="utf-8")

        filter_entries.assert_called_once()
        self.assertIn("-ml", commands[0])
        self.assertEqual(commands[0][commands[0].index("-ml") + 1], "50")
        self.assertIn("-sow", commands[0])
        self.assertEqual(result.entries, [(1000, 2000, "keep this line")])
        self.assertIn("keep this line", srt_text)
        self.assertNotIn("remove this line", srt_text)

    def test_speaker_filter_attaches_short_rejected_continuation_to_previous_line(self):
        records = [
            {
                "entry": (0, 1000, "Barney was chatting with a beautiful"),
                "audio_path": Path("segment.wav"),
                "local_start_ms": 0,
                "local_end_ms": 1000,
            },
            {
                "entry": (1000, 1400, "woman."),
                "audio_path": Path("segment.wav"),
                "local_start_ms": 1000,
                "local_end_ms": 1400,
            },
        ]

        with tempfile.TemporaryDirectory() as tmp:
            with (
                patch("tkcopy.utils.tts_extractor.subprocess.run", return_value=subprocess.CompletedProcess(["ffmpeg"], 0)),
                patch(
                    "tkcopy.utils.tts_extractor.voice_embedding",
                    side_effect=[np.array([1.0, 0.0]), np.array([0.0, 1.0])],
                ),
            ):
                result = tts_extractor._filter_asr_entries_by_dominant_speaker(
                    records,
                    output_dir=Path(tmp),
                    similarity_threshold=0.9,
                    hf_token=None,
                    model_source=tts_extractor.PYANNOTE_EMBEDDING_MODEL,
                )

        self.assertEqual(result, [(0, 1400, "Barney was chatting with a beautiful woman.")])


if __name__ == "__main__":
    unittest.main()
