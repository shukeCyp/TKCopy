import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tkcopy.utils.script_planner import DEFAULT_RECAP_STYLE_PROMPT, plan_narration_beats


class ScriptPlannerTests(unittest.TestCase):
    def test_default_recap_style_prompt_matches_overseas_tts_samples(self):
        self.assertIn("fast-paced English short-form TV/movie recap style", DEFAULT_RECAP_STYLE_PROMPT)
        self.assertIn("Most sentences should be 6-12 words", DEFAULT_RECAP_STYLE_PROMPT)
        self.assertIn("Do not copy the sample wording", DEFAULT_RECAP_STYLE_PROMPT)

    def test_plan_narration_beats_writes_structured_beats_instead_of_line_rewrite(self):
        captured = {}

        def fake_call_llm(prompt, api_key, model, base_url):
            captured["prompt"] = prompt
            return """```json
[
  {
    "beat": 1,
    "anchor_start": 8.66,
    "anchor_end": 13.32,
    "source_indices": [1, 2],
    "text": "巴尼和马歇尔的职场战争正式开始。",
    "pause_after_ms": 120
  },
  {
    "beat": 2,
    "anchor_start": 13.32,
    "anchor_end": 22.5,
    "source_indices": [3],
    "text": "马歇尔直接把战场搬到了巴尼公司楼下。",
    "pause_after_ms": 100
  }
]
```"""

        with tempfile.TemporaryDirectory() as tmp, patch("tkcopy.utils.script_planner.call_llm", fake_call_llm):
            tmp_path = Path(tmp)
            source = tmp_path / "tts.srt"
            output = tmp_path / "narration_beats.json"
            source.write_text(
                "1\n00:00:08,660 --> 00:00:11,810\nBarney and Marshall start a fight.\n\n"
                "2\n00:00:11,810 --> 00:00:13,320\nMarshall quit Barney's company.\n\n"
                "3\n00:00:13,320 --> 00:00:22,500\nHe starts shouting outside the office.\n\n",
                encoding="utf-8",
            )

            beats = plan_narration_beats(
                source,
                output,
                api_key="key",
                model="model",
                base_url="https://example.com",
                target_language="Chinese",
                style="短视频解说",
                min_beats=2,
                max_beats=3,
            )
            output_beats = json.loads(output.read_text(encoding="utf-8"))

        self.assertIn("剧情 beat", captured["prompt"])
        self.assertIn("不要逐条改写字幕", captured["prompt"])
        self.assertIn("只输出 JSON 数组", captured["prompt"])
        self.assertEqual(
            beats,
            [
                {
                    "index": 1,
                    "anchor_start_ms": 8660,
                    "anchor_end_ms": 13320,
                    "source_indices": [1, 2],
                    "text": "巴尼和马歇尔的职场战争正式开始。",
                    "pause_after_ms": 120,
                },
                {
                    "index": 2,
                    "anchor_start_ms": 13320,
                    "anchor_end_ms": 22500,
                    "source_indices": [3],
                    "text": "马歇尔直接把战场搬到了巴尼公司楼下。",
                    "pause_after_ms": 100,
                },
            ],
        )
        self.assertEqual(output_beats, beats)


if __name__ == "__main__":
    unittest.main()
