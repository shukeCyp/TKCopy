import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tkcopy.workflow import WorkflowInputs, run_workflow


class WorkflowTests(unittest.TestCase):
    def test_workflow_exports_jianying_draft_without_composing_final_video(self):
        settings = {
            "whisper_model": "model.bin",
            "vad_model": "vad.bin",
            "vad": {"threshold": 0.25, "min_speech_ms": 10, "min_silence_ms": 50},
            "demucs_model": "htdemucs",
            "speaker": {
                "enabled": True,
                "similarity_threshold": 0.82,
                "pyannote_model": "pyannote/wespeaker-voxceleb-resnet34-LM",
                "hf_token": "",
            },
            "asr": {
                "language": "en",
                "prompt": "",
                "max_len": 50,
                "split_on_word": True,
                "speaker_threshold": 0.3,
                "timing_offset_ms": 820,
            },
            "rewrite_style": "style",
            "llm": {"api_key": "llm-key", "model": "gemini-3.5-flash", "base_url": "https://yunwu.ai"},
            "minimax": {
                "api_key": "minimax-key",
                "group_id": "group",
                "voice_id": "voice",
                "base_url": "https://api.minimax.chat",
            },
        }

        with tempfile.TemporaryDirectory() as tmp:
            output_dir = Path(tmp)
            tts_srt = output_dir / "tts.srt"
            tts_srt.write_text("1\n00:00:00,000 --> 00:00:01,000\nhello\n\n", encoding="utf-8")

            with (
                patch("tkcopy.workflow.run_tts_extraction") as run_tts_extraction,
                patch(
                    "tkcopy.workflow.plan_narration_beats",
                    return_value=[
                        {
                            "index": 1,
                            "anchor_start_ms": 0,
                            "anchor_end_ms": 1000,
                            "source_indices": [1],
                            "text": "hi",
                            "pause_after_ms": 100,
                        }
                    ],
                ) as plan_narration_beats,
                patch("tkcopy.workflow.run_frame_match") as run_frame_match,
                patch(
                    "tkcopy.workflow.synthesize_narration_audio",
                    return_value={
                        "timeline": "",
                        "segments": [str(output_dir / "0001.mp3")],
                        "voice_segments": [
                            {"path": str(output_dir / "0001.mp3"), "index": 1, "start_ms": 0, "end_ms": 1000, "text": "hi"}
                        ],
                    },
                ) as synthesize_narration_audio,
                patch("tkcopy.workflow.MiniMaxTTSProvider") as provider_class,
                patch("tkcopy.workflow.compose_video") as compose_video,
                patch("tkcopy.workflow.create_jianying_clip_draft", return_value=output_dir / "draft") as create_draft,
            ):
                run_tts_extraction.return_value = {
                    "srt_path": str(tts_srt),
                    "audio_path": str(output_dir / "audio.wav"),
                    "entries": [{"index": 1}],
                }
                run_frame_match.return_value = {"matches": [{"viral_frame": 1, "source_frame": 10, "distance": 1}]}

                result = run_workflow(
                    WorkflowInputs(
                        viral_video="viral.mp4",
                        source_video="source.mkv",
                        output_dir=output_dir,
                    ),
                    settings,
                )
                copy_text_content = (output_dir / "文案.txt").read_text(encoding="utf-8")
                draft_copy_text_content = (output_dir / "draft" / "文案.txt").read_text(encoding="utf-8")

        compose_video.assert_not_called()
        run_tts_extraction.assert_called_once_with(
            "viral.mp4",
            "model.bin",
            output_dir / "tts",
            vad_model="vad.bin",
            vad_threshold=0.25,
            min_speech_ms=10,
            min_silence_ms=50,
            demucs_model="htdemucs",
            speaker_filter=True,
            speaker_similarity_threshold=0.82,
            speaker_threshold=0.3,
            hf_token="",
            pyannote_model="pyannote/wespeaker-voxceleb-resnet34-LM",
            asr_language="en",
            asr_prompt="",
            asr_max_len=50,
            asr_split_on_word=True,
            timing_offset_ms=820,
        )
        create_draft.assert_called_once()
        plan_narration_beats.assert_called_once_with(
            str(tts_srt),
            output_dir / "narration_beats.json",
            api_key="llm-key",
            model="gemini-3.5-flash",
            base_url="https://yunwu.ai",
            target_language="English",
            style="style",
        )
        self.assertEqual(copy_text_content, "hi\n")
        self.assertEqual(draft_copy_text_content, "hi\n")
        provider_class.assert_called_once()
        self.assertEqual(provider_class.call_args.kwargs["speed"], 1.2)
        synthesize_narration_audio.assert_called_once()
        self.assertEqual(create_draft.call_args.kwargs["voice_segments"][0]["text"], "hi")
        self.assertFalse(create_draft.call_args.kwargs["import_subtitles"])
        self.assertFalse(create_draft.call_args.kwargs["trim_voice_silence"])
        self.assertNotIn("final_video", result)
        self.assertEqual(result["jianying_draft"], str(output_dir / "draft"))
        self.assertEqual(result["copy_text"], str(output_dir / "文案.txt"))
        self.assertEqual(result["narration_beats"], str(output_dir / "narration_beats.json"))

    def test_workflow_uses_voxcpm_provider_when_configured(self):
        settings = {
            "tts_provider": "voxcpm",
            "whisper_model": "model.bin",
            "vad_model": "vad.bin",
            "vad": {"threshold": 0.25, "min_speech_ms": 10, "min_silence_ms": 50},
            "demucs_model": "htdemucs",
            "speaker": {
                "enabled": True,
                "similarity_threshold": 0.82,
                "pyannote_model": "pyannote/wespeaker-voxceleb-resnet34-LM",
                "hf_token": "",
            },
            "asr": {
                "language": "en",
                "prompt": "",
                "max_len": 50,
                "split_on_word": True,
                "speaker_threshold": 0.3,
                "timing_offset_ms": 820,
            },
            "rewrite_style": "style",
            "llm": {"api_key": "llm-key", "model": "gemini-3.5-flash", "base_url": "https://yunwu.ai"},
            "minimax": {
                "api_key": "minimax-key",
                "group_id": "group",
                "voice_id": "voice",
                "base_url": "https://api.minimax.chat",
            },
            "voxcpm": {
                "base_url": "https://tts.example.com",
                "api_type": "gradio",
                "voice": "Alex",
                "voice_refs": {
                    "Natasha": "/voices/natasha.mp3",
                    "Alex": "/voices/alex.mp3",
                },
                "control": "confident",
                "seed": 7,
                "cfg_value": 2.25,
                "inference_timesteps": 12,
                "do_normalize": True,
                "denoise": True,
                "audio_format": "wav",
                "timeout": 900,
            },
        }

        with tempfile.TemporaryDirectory() as tmp:
            output_dir = Path(tmp)
            tts_srt = output_dir / "tts.srt"
            tts_srt.write_text("1\n00:00:00,000 --> 00:00:01,000\nhello\n\n", encoding="utf-8")

            with (
                patch("tkcopy.workflow.run_tts_extraction") as run_tts_extraction,
                patch(
                    "tkcopy.workflow.plan_narration_beats",
                    return_value=[
                        {
                            "index": 1,
                            "anchor_start_ms": 0,
                            "anchor_end_ms": 1000,
                            "source_indices": [1],
                            "text": "hi",
                            "pause_after_ms": 100,
                        }
                    ],
                ),
                patch("tkcopy.workflow.run_frame_match") as run_frame_match,
                patch("tkcopy.workflow.synthesize_narration_audio", return_value={"timeline": "", "voice_segments": []}) as synthesize_narration_audio,
                patch("tkcopy.workflow.MiniMaxTTSProvider") as minimax_provider,
                patch("tkcopy.workflow.VoxCPMTTSProvider", create=True) as voxcpm_provider,
                patch("tkcopy.workflow.create_jianying_clip_draft", return_value=output_dir / "draft"),
            ):
                run_tts_extraction.return_value = {
                    "srt_path": str(tts_srt),
                    "audio_path": str(output_dir / "audio.wav"),
                    "entries": [{"index": 1}],
                }
                run_frame_match.return_value = {"matches": [{"viral_frame": 1, "source_frame": 10, "distance": 1}]}

                run_workflow(
                    WorkflowInputs(
                        viral_video="viral.mp4",
                        source_video="source.mkv",
                        output_dir=output_dir,
                    ),
                    settings,
                )

        minimax_provider.assert_not_called()
        voxcpm_provider.assert_called_once_with(
            base_url="https://tts.example.com",
            api_type="gradio",
            voice="Alex",
            voice_refs={
                "Natasha": "/voices/natasha.mp3",
                "Alex": "/voices/alex.mp3",
            },
            control="confident",
            seed=7,
            cfg_value=2.25,
            inference_timesteps=12,
            do_normalize=True,
            denoise=True,
            audio_format="wav",
            timeout=900,
        )
        synthesize_narration_audio.assert_called_once()
        self.assertEqual(synthesize_narration_audio.call_args.args[2], voxcpm_provider.return_value)

    def test_workflow_uses_vmf_frame_matcher_when_configured(self):
        settings = {
            "frame_match": {
                "engine": "vmf",
                "vmf_bin": "/opt/vmf",
                "fps": 3,
                "model": "dinov2_vits14",
                "device": "cpu",
                "batch_size": 64,
                "inflight": 1,
                "padding_seconds": 90,
            },
            "whisper_model": "model.bin",
            "vad_model": "vad.bin",
            "vad": {"threshold": 0.25, "min_speech_ms": 10, "min_silence_ms": 50},
            "demucs_model": "htdemucs",
            "speaker": {
                "enabled": True,
                "similarity_threshold": 0.82,
                "pyannote_model": "pyannote/wespeaker-voxceleb-resnet34-LM",
                "hf_token": "",
            },
            "asr": {
                "language": "en",
                "prompt": "",
                "max_len": 50,
                "split_on_word": True,
                "speaker_threshold": 0.3,
                "timing_offset_ms": 820,
            },
            "rewrite_style": "style",
            "llm": {"api_key": "llm-key", "model": "gemini-3.5-flash", "base_url": "https://yunwu.ai"},
            "minimax": {
                "api_key": "minimax-key",
                "group_id": "group",
                "voice_id": "voice",
                "base_url": "https://api.minimax.chat",
            },
        }

        with tempfile.TemporaryDirectory() as tmp:
            output_dir = Path(tmp)
            tts_srt = output_dir / "tts.srt"
            tts_srt.write_text("1\n00:00:00,000 --> 00:00:01,000\nhello\n\n", encoding="utf-8")

            with (
                patch("tkcopy.workflow.run_tts_extraction") as run_tts_extraction,
                patch(
                    "tkcopy.workflow.plan_narration_beats",
                    return_value=[
                        {
                            "index": 1,
                            "anchor_start_ms": 0,
                            "anchor_end_ms": 1000,
                            "source_indices": [1],
                            "text": "hi",
                            "pause_after_ms": 100,
                        }
                    ],
                ),
                patch("tkcopy.workflow.run_frame_match") as run_frame_match,
                patch("tkcopy.workflow.run_vmf_frame_match", return_value={"matches": [{"target_start": 0, "duration": 1, "source_start": 10, "source_duration": 1}]}) as run_vmf_frame_match,
                patch("tkcopy.workflow.synthesize_narration_audio", return_value={"timeline": "", "voice_segments": []}),
                patch("tkcopy.workflow.MiniMaxTTSProvider"),
                patch("tkcopy.workflow.create_jianying_clip_draft", return_value=output_dir / "draft"),
            ):
                run_tts_extraction.return_value = {
                    "srt_path": str(tts_srt),
                    "audio_path": str(output_dir / "audio.wav"),
                    "entries": [{"index": 1}],
                }

                run_workflow(
                    WorkflowInputs(
                        viral_video="viral.mp4",
                        source_video="source.mkv",
                        output_dir=output_dir,
                    ),
                    settings,
                )

        run_frame_match.assert_not_called()
        run_vmf_frame_match.assert_called_once_with(
            "viral.mp4",
            "source.mkv",
            output_dir / "match",
            vmf_bin="/opt/vmf",
            vmf_fps=3.0,
            model="dinov2_vits14",
            device="cpu",
            batch_size=64,
            inflight=1,
            padding_seconds=90.0,
        )


if __name__ == "__main__":
    unittest.main()
