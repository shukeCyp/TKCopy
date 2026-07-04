import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tkcopy.batch import run_batch_workflows, scan_batch_cases


class BatchWorkflowTests(unittest.TestCase):
    def test_scan_batch_cases_pairs_viral_and_source_videos_with_voice_split(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for index in range(1, 7):
                case_dir = root / str(index)
                case_dir.mkdir()
                (case_dir / f"对标爆款_case_{index}.mp4").write_bytes(b"viral")
                (case_dir / f"source_case_{index}.mkv").write_bytes(b"source")

            cases = scan_batch_cases(root, voice_split_count=5)

        self.assertEqual(len(cases), 6)
        self.assertTrue(all(case["enabled"] for case in cases))
        self.assertEqual(cases[0]["voice"], "Natasha")
        self.assertEqual(cases[4]["voice"], "Natasha")
        self.assertEqual(cases[5]["voice"], "Alex")
        self.assertTrue(cases[0]["viral_video"].endswith("对标爆款_case_1.mp4"))
        self.assertTrue(cases[0]["source_video"].endswith("source_case_1.mkv"))

    def test_run_batch_workflows_sets_case_voice_and_case_output_directory(self):
        cases = [
            {
                "id": "1",
                "enabled": True,
                "viral_video": "/videos/viral1.mp4",
                "source_video": "/videos/source1.mkv",
                "voice": "Natasha",
            },
            {
                "id": "2",
                "enabled": True,
                "viral_video": "/videos/viral2.mp4",
                "source_video": "/videos/source2.mkv",
                "voice": "Alex",
            },
        ]
        settings = {
            "voxcpm": {"voice": "Natasha"},
            "tts_provider": "voxcpm",
        }
        events = []

        with tempfile.TemporaryDirectory() as tmp:
            output_root = Path(tmp)
            with patch("tkcopy.batch.run_workflow") as run_workflow:
                run_workflow.side_effect = [
                    {"jianying_draft": "/draft/one"},
                    {"jianying_draft": "/draft/two"},
                ]

                result = run_batch_workflows(
                    cases,
                    settings,
                    output_root,
                    rewrite_style="style",
                    target_language="English",
                    progress=events.append,
                )

        self.assertTrue(result["ok"])
        self.assertEqual(len(result["cases"]), 2)
        self.assertEqual(run_workflow.call_count, 2)
        first_inputs = run_workflow.call_args_list[0].args[0]
        second_inputs = run_workflow.call_args_list[1].args[0]
        first_settings = run_workflow.call_args_list[0].args[1]
        second_settings = run_workflow.call_args_list[1].args[1]
        self.assertTrue(str(first_inputs.output_dir).endswith("case_01_Natasha_1"))
        self.assertTrue(str(second_inputs.output_dir).endswith("case_02_Alex_2"))
        self.assertEqual(first_settings["voxcpm"]["voice"], "Natasha")
        self.assertEqual(second_settings["voxcpm"]["voice"], "Alex")
        self.assertEqual(events[0]["event"], "case_started")
        self.assertEqual(events[-1]["event"], "batch_finished")


if __name__ == "__main__":
    unittest.main()
