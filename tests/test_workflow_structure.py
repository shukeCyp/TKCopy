import unittest


class WorkflowStructureTests(unittest.TestCase):
    def test_workflow_declares_fixed_stage_sequence(self):
        from tkcopy.workflow_steps import WORKFLOW_STAGES

        self.assertEqual(
            [(stage.key, stage.zh, stage.en) for stage in WORKFLOW_STAGES],
            [
                ("tts_extraction", "TTS分离", "TTS extraction"),
                ("narration_planning", "解说规划", "Narration planning"),
                ("frame_matching", "镜头匹配", "Frame matching"),
                ("audio_generation", "音频生成", "Audio generation"),
                ("jianying_export", "导出剪映", "Jianying export"),
            ],
        )

    def test_workflow_logger_emits_bilingual_stage_logs_with_stage_key(self):
        from tkcopy.workflow_context import WorkflowStage
        from tkcopy.workflow_logging import WorkflowLogger

        calls = []
        logger = WorkflowLogger(print_fn=lambda zh, en, **details: calls.append((zh, en, details)))
        stage = WorkflowStage("tts_extraction", "TTS分离", "TTS extraction")

        logger.stage_started(stage, output_dir="output/tts")
        logger.stage_completed(stage, srt="output/tts/final.srt", entries=37)

        self.assertEqual(
            calls,
            [
                (
                    "步骤开始: TTS分离",
                    "Step started: TTS extraction",
                    {"stage": "tts_extraction", "output_dir": "output/tts"},
                ),
                (
                    "步骤完成: TTS分离",
                    "Step completed: TTS extraction",
                    {"stage": "tts_extraction", "srt": "output/tts/final.srt", "entries": 37},
                ),
            ],
        )


if __name__ == "__main__":
    unittest.main()
