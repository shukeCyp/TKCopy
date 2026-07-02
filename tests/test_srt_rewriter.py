import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tkcopy.utils.srt_rewriter import call_llm, rewrite_srt


class SrtRewriterTests(unittest.TestCase):
    def test_call_llm_uses_gemini_generate_content_for_gemini_model(self):
        captured = {}

        class FakeResponse:
            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

            def read(self):
                return json.dumps(
                    {
                        "candidates": [
                            {"content": {"parts": [{"text": "[1] 改写后"}]}}
                        ]
                    }
                ).encode()

        def fake_urlopen(request, timeout):
            captured["url"] = request.full_url
            captured["body"] = json.loads(request.data.decode())
            captured["timeout"] = timeout
            return FakeResponse()

        with patch("tkcopy.utils.srt_rewriter.urllib.request.urlopen", fake_urlopen):
            result = call_llm("prompt", "secret-key", "gemini-3.5-flash", "https://yunwu.ai")

        self.assertEqual(result, "[1] 改写后")
        self.assertIn("/v1beta/models/gemini-3.5-flash:generateContent", captured["url"])
        self.assertEqual(captured["body"]["contents"][0]["parts"][0]["text"], "prompt")

    def test_rewrite_srt_prompt_asks_for_plot_first_not_sentence_replacement(self):
        captured = {}

        def fake_call_llm(prompt, api_key, model, base_url):
            captured["prompt"] = prompt
            return "[1] 巴尼和马歇尔的较量正式开始。"

        with tempfile.TemporaryDirectory() as tmp, patch("tkcopy.utils.srt_rewriter.call_llm", fake_call_llm):
            tmp_path = Path(tmp)
            source = tmp_path / "source.srt"
            output = tmp_path / "rewritten.srt"
            source.write_text(
                "1\n00:00:08,660 --> 00:00:11,810\nBarney and Marshall start a silent fight.\n\n",
                encoding="utf-8",
            )

            rewrite_srt(source, output, api_key="key", model="model", base_url="https://example.com")

        prompt = captured["prompt"]
        self.assertIn("先理解剧情", prompt)
        self.assertIn("剧情事实", prompt)
        self.assertIn("不要逐句同义词替换", prompt)
        self.assertIn("人物译名", prompt)
        self.assertIn("Marshall", prompt)
        self.assertIn("马歇尔", prompt)
        self.assertIn("短视频解说", prompt)
        self.assertIn("保持条目编号和数量不变", prompt)


if __name__ == "__main__":
    unittest.main()
