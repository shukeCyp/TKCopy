import unittest
from unittest.mock import patch
import subprocess
import json
from pathlib import Path
import tempfile

from tkcopy.utils.jianying_export import (
    DEFAULT_DRAFT_FOLDER,
    build_clip_segments,
    create_jianying_clip_draft,
    plan_voiceover_segments,
    create_video_material,
    get_video_info,
    prepare_jianying_audio_source,
    prepare_jianying_video_source,
)


class JianyingExportTests(unittest.TestCase):
    def test_default_draft_folder_uses_configured_downloads_location(self):
        self.assertEqual(DEFAULT_DRAFT_FOLDER, Path("/Users/chaiyapeng/Downloads/草稿/JianyingPro Drafts"))

    def test_build_clip_segments_maps_one_fps_matches_to_timeline_segments(self):
        segments = build_clip_segments(
            [
                {"viral_frame": 1, "source_frame": 10, "distance": 1},
                {"viral_frame": 2, "source_frame": 20, "distance": 1},
                {"viral_frame": 3, "source_frame": 30, "distance": 1},
            ],
            viral_duration=3.2,
            source_duration=60.0,
        )

        self.assertEqual(
            segments,
            [
                {"target_start": 0.0, "duration": 1.0, "source_start": 9.0},
                {"target_start": 1.0, "duration": 1.0, "source_start": 19.0},
                {"target_start": 2.0, "duration": 1.0, "source_start": 29.0},
            ],
        )

    def test_build_clip_segments_clamps_source_range_to_video_duration(self):
        segments = build_clip_segments(
            [{"viral_frame": 1, "source_frame": 60, "distance": 1}],
            viral_duration=2.0,
            source_duration=60.5,
        )

        self.assertEqual(segments, [{"target_start": 0.0, "duration": 1.0, "source_start": 59.0}])

    def test_build_clip_segments_accepts_seconds_based_matches(self):
        segments = build_clip_segments(
            [
                {
                    "target_start": 1.25,
                    "duration": 2.0,
                    "source_start": 20.5,
                    "source_duration": 2.1,
                }
            ],
            viral_duration=10.0,
            source_duration=30.0,
        )

        self.assertEqual(
            segments,
            [{"target_start": 1.25, "duration": 2.0, "source_start": 20.5, "source_duration": 2.1}],
        )

    def test_build_clip_segments_keeps_enough_precision_for_adjacent_frame_segments(self):
        fps = 23.976
        first_count = 101
        second_start_frame = 517
        first_start_frame = second_start_frame - first_count
        segments = build_clip_segments(
            [
                {
                    "target_start": first_start_frame / fps,
                    "duration": first_count / fps,
                    "source_start": 5950 / fps,
                    "source_duration": first_count / fps,
                },
                {
                    "target_start": second_start_frame / fps,
                    "duration": 88 / fps,
                    "source_start": 6004 / fps,
                    "source_duration": 88 / fps,
                },
            ],
            viral_duration=80.0,
            source_duration=400.0,
        )

        first_end_us = round((segments[0]["target_start"] + segments[0]["duration"]) * 1_000_000)
        second_start_us = round(segments[1]["target_start"] * 1_000_000)
        self.assertLessEqual(first_end_us, second_start_us)

    def test_get_video_info_falls_back_to_format_duration_for_mkv_streams(self):
        ffprobe_output = b'{"streams":[{"width":1920,"height":1080}],"format":{"duration":"3485.653000"}}'

        with patch(
            "tkcopy.utils.jianying_export.subprocess.run",
            return_value=subprocess.CompletedProcess(["ffprobe"], 0, stdout=ffprobe_output),
        ):
            self.assertEqual(get_video_info("source.mkv"), (1920, 1080, 3485.653))

    def test_create_video_material_uses_ffprobe_values_without_library_media_parse(self):
        class FakeCc:
            class CropSettings:
                pass

            class VideoMaterial:
                pass

        material = create_video_material(FakeCc, "/tmp/source.mkv", 1920, 1080, 3485.653)

        self.assertEqual(material.path, str(Path("/tmp/source.mkv").resolve()))
        self.assertEqual(material.width, 1920)
        self.assertEqual(material.height, 1080)
        self.assertEqual(material.duration, 3485653000)

    def test_prepare_jianying_video_source_converts_mkv_audio_to_aac_in_draft_resources(self):
        commands = []

        def fake_run(cmd, check):
            commands.append(cmd)
            Path(cmd[-1]).write_bytes(b"mp4")
            return subprocess.CompletedProcess(cmd, 0)

        with tempfile.TemporaryDirectory() as tmp, patch("tkcopy.utils.jianying_export.subprocess.run", side_effect=fake_run):
            source = Path(tmp) / "source.mkv"
            draft_path = Path(tmp) / "draft"
            result = prepare_jianying_video_source(source, draft_path)

        self.assertEqual(result, draft_path / "Resources" / "tkcopy" / "source.mp4")
        self.assertEqual(commands[0][0], "ffmpeg")
        self.assertIn("-c:v", commands[0])
        self.assertIn("copy", commands[0])
        self.assertIn("-c:a", commands[0])
        self.assertIn("aac", commands[0])

    def test_prepare_jianying_video_source_rebuilds_existing_mp4_with_unsupported_audio(self):
        commands = []

        def fake_run(cmd, check, stdout=None):
            commands.append(cmd)
            if cmd[0] == "ffprobe":
                return subprocess.CompletedProcess(
                    cmd,
                    0,
                    stdout=b'{"streams":[{"codec_type":"video","codec_name":"h264"},{"codec_type":"audio","codec_name":"eac3"}]}',
                )
            Path(cmd[-1]).write_bytes(b"rebuilt mp4")
            return subprocess.CompletedProcess(cmd, 0, stdout=b"")

        with tempfile.TemporaryDirectory() as tmp, patch("tkcopy.utils.jianying_export.subprocess.run", side_effect=fake_run):
            source = Path(tmp) / "source.mkv"
            draft_path = Path(tmp) / "draft"
            existing = draft_path / "Resources" / "tkcopy" / "source.mp4"
            existing.parent.mkdir(parents=True)
            existing.write_bytes(b"old mp4")

            result = prepare_jianying_video_source(source, draft_path)

        self.assertEqual(result, existing)
        self.assertEqual(commands[0][0], "ffprobe")
        self.assertEqual(commands[1][0], "ffmpeg")
        self.assertIn("aac", commands[1])

    def test_prepare_jianying_video_source_keeps_mp4_path(self):
        with patch("tkcopy.utils.jianying_export.subprocess.run") as run:
            result = prepare_jianying_video_source(Path("/tmp/source.mp4"), Path("/tmp/draft"))

        self.assertEqual(result, Path("/tmp/source.mp4").resolve())
        run.assert_not_called()

    def test_prepare_jianying_audio_source_copies_audio_into_draft_resources(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            audio = tmp_path / "voice_timeline.m4a"
            audio.write_bytes(b"audio")
            draft_path = tmp_path / "draft"

            result = prepare_jianying_audio_source(audio, draft_path)

            expected = draft_path / "Resources" / "tkcopy" / "voice_timeline.m4a"
            self.assertEqual(result, expected)
            self.assertEqual(expected.read_bytes(), b"audio")

    def test_prepare_jianying_audio_source_can_trim_tts_silence_into_draft_resources(self):
        commands = []

        def fake_run(cmd, check):
            commands.append(cmd)
            Path(cmd[-1]).write_bytes(b"trimmed")
            return subprocess.CompletedProcess(cmd, 0)

        with tempfile.TemporaryDirectory() as tmp, patch(
            "tkcopy.utils.jianying_export.subprocess.run",
            side_effect=fake_run,
        ):
            tmp_path = Path(tmp)
            audio = tmp_path / "0001.mp3"
            audio.write_bytes(b"audio")
            draft_path = tmp_path / "draft"

            result = prepare_jianying_audio_source(audio, draft_path, trim_silence=True)

            expected = draft_path / "Resources" / "tkcopy" / "voiceover_trimmed" / "0001.mp3"
            self.assertEqual(result, expected)
            self.assertEqual(expected.read_bytes(), b"trimmed")
            self.assertEqual(commands[0][0], "ffmpeg")
            self.assertIn("-af", commands[0])
            audio_filter = commands[0][commands[0].index("-af") + 1]
            self.assertIn("silenceremove", audio_filter)
            self.assertIn("start_threshold=-55dB", audio_filter)
            self.assertIn("adelay=100:all=1", audio_filter)
            self.assertIn("apad=pad_dur=0.1", audio_filter)
            self.assertIn("aresample=async=1:first_pts=0", audio_filter)

    def test_create_clip_draft_writes_seconds_as_microseconds(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            srt_path = tmp_path / "subtitles.srt"
            srt_path.write_text(
                "1\n00:00:00,000 --> 00:00:01,000\nhello\n",
                encoding="utf-8",
            )

            with (
                patch(
                    "tkcopy.utils.jianying_export.get_video_info",
                    side_effect=[(1080, 1920, 1.0), (1920, 1080, 10.0)],
                ),
                patch(
                    "tkcopy.utils.jianying_export.prepare_jianying_video_source",
                    return_value=tmp_path / "source.mp4",
                ),
            ):
                draft_path = create_jianying_clip_draft(
                    tmp_path / "viral.mp4",
                    tmp_path / "source.mp4",
                    [{"viral_frame": 1, "source_frame": 3, "distance": 1}],
                    srt_path,
                    draft_name="unit-draft",
                    draft_folder=tmp_path,
                )

            content = json.loads((draft_path / "draft_content.json").read_text(encoding="utf-8"))
            video_track = next(track for track in content["tracks"] if track["type"] == "video")
            segment = video_track["segments"][0]

            self.assertEqual(segment["target_timerange"], {"start": 0, "duration": 1_000_000})
            self.assertEqual(segment["source_timerange"], {"start": 2_000_000, "duration": 1_000_000})

    def test_create_clip_draft_writes_jianying_project_sidecar_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            srt_path = tmp_path / "subtitles.srt"
            srt_path.write_text(
                "1\n00:00:00,000 --> 00:00:01,000\nhello\n",
                encoding="utf-8",
            )

            with (
                patch(
                    "tkcopy.utils.jianying_export.get_video_info",
                    side_effect=[(1080, 1920, 1.0), (1920, 1080, 10.0)],
                ),
                patch(
                    "tkcopy.utils.jianying_export.prepare_jianying_video_source",
                    return_value=tmp_path / "source.mp4",
                ),
            ):
                draft_path = create_jianying_clip_draft(
                    tmp_path / "viral.mp4",
                    tmp_path / "source.mp4",
                    [{"viral_frame": 1, "source_frame": 3, "distance": 1}],
                    srt_path,
                    draft_name="unit-draft",
                    draft_folder=tmp_path,
                )

            self.assertTrue((draft_path / "Timelines" / "project.json").exists())
            self.assertTrue((draft_path / "timeline_layout.json").exists())
            self.assertTrue((draft_path / "common_attachment" / "attachment_id_mapping.json").exists())
            self.assertTrue((draft_path / "draft_virtual_store.json").exists())
            content = json.loads((draft_path / "draft_content.json").read_text(encoding="utf-8"))
            timeline_dir = draft_path / "Timelines" / content["id"]
            self.assertTrue((timeline_dir / "draft_content.json").exists())
            self.assertTrue((timeline_dir / "attachment_pc_common.json").exists())
            self.assertTrue((timeline_dir / "attachment_editing.json").exists())
            self.assertTrue((timeline_dir / "common_attachment" / "attachment_id_mapping.json").exists())
            project = json.loads((draft_path / "Timelines" / "project.json").read_text(encoding="utf-8"))
            layout = json.loads((draft_path / "timeline_layout.json").read_text(encoding="utf-8"))
            id_mapping = json.loads(
                (draft_path / "common_attachment" / "attachment_id_mapping.json").read_text(encoding="utf-8")
            )
            timeline_content = json.loads((timeline_dir / "draft_content.json").read_text(encoding="utf-8"))
            virtual_store = json.loads((draft_path / "draft_virtual_store.json").read_text(encoding="utf-8"))

            self.assertTrue((draft_path / "performance_opt_info.json").exists())
            self.assertTrue((draft_path / "attachment_pc_common.json").exists())
            self.assertTrue((draft_path / "common_attachment" / "coperate_create.json").exists())
            self.assertTrue((draft_path / "common_attachment" / "attachment_script_video.json").exists())
            self.assertTrue((draft_path / "common_attachment" / "attachment_pc_timeline.json").exists())
            self.assertTrue((draft_path / "draft_agency_config.json").exists())
            self.assertTrue((draft_path / "draft_biz_config.json").exists())
            self.assertEqual(project["main_timeline_id"], content["id"])
            self.assertEqual(layout["activeTimeline"], content["id"])
            self.assertEqual(timeline_content["id"], content["id"])
            mapped_uuids = {item["uuid"] for item in id_mapping["id_mapping"]["mapping"]}
            video_material_id = content["materials"]["videos"][0]["id"]
            self.assertIn(video_material_id, mapped_uuids)
            virtual_store_ids = {
                item["child_id"]
                for group in virtual_store["draft_virtual_store"]
                if group["type"] == 1
                for item in group["value"]
            }
            self.assertIn(video_material_id, virtual_store_ids)

    def test_plan_voiceover_segments_uses_original_tts_srt_anchors(self):
        planned = plan_voiceover_segments(
            [
                {"target_start": 0.0, "duration": 10.0, "source_start": 10.0},
                {"target_start": 10.0, "duration": 2.0, "source_start": 20.0},
            ],
            [
                {"path": "a.mp3", "start_ms": 8660, "end_ms": 10000},
                {"path": "b.mp3", "start_ms": 11810, "end_ms": 13320},
                {"path": "c.mp3", "start_ms": 13320, "end_ms": 15540},
            ],
            {"a.mp3": 1.0, "b.mp3": 1.0, "c.mp3": 0.5},
        )

        self.assertEqual(
            planned,
            [
                {"path": "a.mp3", "target_start": 8.66, "duration": 1.0},
                {"path": "b.mp3", "target_start": 11.81, "duration": 1.0},
                {"path": "c.mp3", "target_start": 13.32, "duration": 0.5},
            ],
        )

    def test_plan_voiceover_segments_shifts_overlaps_without_extra_gap(self):
        planned = plan_voiceover_segments(
            [
                {"target_start": 0.0, "duration": 10.0, "source_start": 10.0},
            ],
            [
                {"path": "a.mp3", "start_ms": 0, "end_ms": 1000},
                {"path": "b.mp3", "start_ms": 1000, "end_ms": 2000},
                {"path": "c.mp3", "start_ms": 3500, "end_ms": 4500},
            ],
            {"a.mp3": 2.0, "b.mp3": 1.0, "c.mp3": 1.0},
        )

        self.assertEqual(
            planned,
            [
                {"path": "a.mp3", "target_start": 0.0, "duration": 2.0},
                {"path": "b.mp3", "target_start": 2.0, "duration": 1.0},
                {"path": "c.mp3", "target_start": 3.5, "duration": 1.0},
            ],
        )

    def test_create_clip_draft_extends_last_video_segment_to_cover_voiceover(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            srt_path = tmp_path / "subtitles.srt"
            srt_path.write_text(
                "1\n00:00:00,800 --> 00:00:01,800\nhello\n",
                encoding="utf-8",
            )
            audio = tmp_path / "0001.mp3"
            audio.write_bytes(b"audio")

            with (
                patch(
                    "tkcopy.utils.jianying_export.get_video_info",
                    side_effect=[(1080, 1920, 1.0), (1920, 1080, 10.0)],
                ),
                patch(
                    "tkcopy.utils.jianying_export.prepare_jianying_video_source",
                    return_value=tmp_path / "source.mp4",
                ),
                patch(
                    "tkcopy.utils.jianying_export.prepare_jianying_audio_source",
                    side_effect=lambda path, draft, **kwargs: Path(path),
                ),
                patch("tkcopy.utils.jianying_export.get_media_duration", return_value=1.0),
            ):
                draft_path = create_jianying_clip_draft(
                    tmp_path / "viral.mp4",
                    tmp_path / "source.mp4",
                    [{"target_start": 0.0, "duration": 1.0, "source_start": 2.0, "source_duration": 1.0}],
                    srt_path,
                    voice_segments=[
                        {"path": str(audio), "start_ms": 800, "end_ms": 1800, "text": "hello"},
                    ],
                    draft_name="unit-draft",
                    draft_folder=tmp_path,
                )

            content = json.loads((draft_path / "draft_content.json").read_text(encoding="utf-8"))
            video_track = next(track for track in content["tracks"] if track["type"] == "video")
            audio_track = next(track for track in content["tracks"] if track["type"] == "audio")

            self.assertEqual(
                [segment["target_timerange"] for segment in video_track["segments"]],
                [
                    {"start": 0, "duration": 800_000},
                    {"start": 800_000, "duration": 1_000_000},
                ],
            )
            self.assertEqual([segment["volume"] for segment in video_track["segments"]], [1.0, 0.3])
            self.assertEqual(audio_track["segments"][0]["target_timerange"], {"start": 800_000, "duration": 1_000_000})

    def test_create_clip_draft_uses_segment_voiceover_without_importing_subtitles_and_sets_source_volume(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            srt_path = tmp_path / "subtitles.srt"
            srt_path.write_text(
                "1\n00:00:00,000 --> 00:00:01,000\nhello\n",
                encoding="utf-8",
            )
            first_audio = tmp_path / "0001.mp3"
            second_audio = tmp_path / "0002.mp3"
            first_audio.write_bytes(b"audio1")
            second_audio.write_bytes(b"audio2")

            with (
                patch(
                    "tkcopy.utils.jianying_export.get_video_info",
                    side_effect=[(1080, 1920, 2.0), (1920, 1080, 10.0)],
                ),
                patch(
                    "tkcopy.utils.jianying_export.prepare_jianying_video_source",
                    return_value=tmp_path / "source.mp4",
                ),
                patch(
                    "tkcopy.utils.jianying_export.prepare_jianying_audio_source",
                    side_effect=lambda path, draft, **kwargs: Path(path),
                ),
                patch(
                    "tkcopy.utils.jianying_export.get_media_duration",
                    side_effect=[0.5, 0.4],
                ),
            ):
                draft_path = create_jianying_clip_draft(
                    tmp_path / "viral.mp4",
                    tmp_path / "source.mp4",
                    [
                        {"target_start": 0.0, "duration": 1.0, "source_start": 2.0},
                        {"target_start": 1.0, "duration": 1.0, "source_start": 3.0},
                    ],
                    srt_path,
                    voice_segments=[
                        {"path": str(first_audio), "start_ms": 0, "end_ms": 500, "text": "first"},
                        {"path": str(second_audio), "start_ms": 1000, "end_ms": 1400, "text": "second"},
                    ],
                    draft_name="unit-draft",
                    draft_folder=tmp_path,
                )

            content = json.loads((draft_path / "draft_content.json").read_text(encoding="utf-8"))
            video_track = next(track for track in content["tracks"] if track["type"] == "video")
            audio_track = next(track for track in content["tracks"] if track["type"] == "audio")

            self.assertFalse(any(track["type"] == "text" for track in content["tracks"]))
            self.assertEqual(
                [segment["target_timerange"] for segment in video_track["segments"]],
                [
                    {"start": 0, "duration": 500_000},
                    {"start": 500_000, "duration": 500_000},
                    {"start": 1_000_000, "duration": 400_000},
                    {"start": 1_400_000, "duration": 600_000},
                ],
            )
            self.assertEqual([segment["volume"] for segment in video_track["segments"]], [0.3, 1.0, 0.3, 1.0])
            self.assertEqual(len(audio_track["segments"]), 2)
            self.assertEqual(audio_track["segments"][0]["target_timerange"], {"start": 0, "duration": 500_000})
            self.assertEqual(audio_track["segments"][1]["target_timerange"], {"start": 1_000_000, "duration": 400_000})

    def test_create_clip_draft_keeps_source_volume_full_outside_voiceover_ranges(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            first_audio = tmp_path / "0001.mp3"
            second_audio = tmp_path / "0002.mp3"
            first_audio.write_bytes(b"audio1")
            second_audio.write_bytes(b"audio2")

            with (
                patch(
                    "tkcopy.utils.jianying_export.get_video_info",
                    side_effect=[(1080, 1920, 4.0), (1920, 1080, 20.0)],
                ),
                patch(
                    "tkcopy.utils.jianying_export.prepare_jianying_video_source",
                    return_value=tmp_path / "source.mp4",
                ),
                patch(
                    "tkcopy.utils.jianying_export.prepare_jianying_audio_source",
                    side_effect=lambda path, draft, **kwargs: Path(path),
                ),
                patch(
                    "tkcopy.utils.jianying_export.get_media_duration",
                    side_effect=[1.0, 0.5],
                ),
            ):
                draft_path = create_jianying_clip_draft(
                    tmp_path / "viral.mp4",
                    tmp_path / "source.mp4",
                    [{"target_start": 0.0, "duration": 4.0, "source_start": 10.0, "source_duration": 4.0}],
                    None,
                    voice_segments=[
                        {"path": str(first_audio), "start_ms": 1000, "end_ms": 2000, "text": "first"},
                        {"path": str(second_audio), "start_ms": 3000, "end_ms": 3500, "text": "second"},
                    ],
                    draft_name="unit-draft",
                    draft_folder=tmp_path,
                    source_volume=0.3,
                )

            content = json.loads((draft_path / "draft_content.json").read_text(encoding="utf-8"))
            video_track = next(track for track in content["tracks"] if track["type"] == "video")

            self.assertEqual(
                [segment["target_timerange"] for segment in video_track["segments"]],
                [
                    {"start": 0, "duration": 1_000_000},
                    {"start": 1_000_000, "duration": 1_000_000},
                    {"start": 2_000_000, "duration": 1_000_000},
                    {"start": 3_000_000, "duration": 500_000},
                    {"start": 3_500_000, "duration": 500_000},
                ],
            )
            self.assertEqual([segment["volume"] for segment in video_track["segments"]], [1.0, 0.3, 1.0, 0.3, 1.0])


if __name__ == "__main__":
    unittest.main()
