"""解说稿规划工具 - 把 TTS SRT 合并成剧情 beat。"""
import json
import re
from pathlib import Path
from typing import Any

from tkcopy.logging_utils import print_log
from tkcopy.utils.srt_rewriter import call_llm, parse_srt


DEFAULT_RECAP_STYLE_PROMPT = """Write in fast-paced English short-form TV/movie recap style.

Use short, clear, conversational sentences. Most sentences should be 6-12 words.
Start directly with the main conflict, mystery, danger, or unusual action. Do not add greetings, introductions, or background explanation.
Narrate events in a clean chronological order, but make every beat feel like it is moving toward a new complication.
Each beat should contain a simple mini-arc: what happened, why it matters, and what new twist or reaction follows.

Use natural transition phrases such as:
- But...
- When...
- After...
- Before long...
- Suddenly...
- Meanwhile...
- That's when...
- To his surprise...
- At the same time...
- With this lead...

Use mild suspense and forward momentum. Phrases like "he had no idea", "something unexpected happened", "the plan was about to unfold", or "the truth was finally revealed" are allowed when appropriate.

Keep the tone objective but engaging. Do not over-hype. Do not use Chinese short-video exaggeration. Do not add fake jokes, internet slang, or dramatic clickbait unless the scene itself is comedic.
For comedy scenes, allow light sarcasm or dry humor, but still prioritize clear plot progression.
For crime or medical scenes, keep the tone serious, direct, and procedural.

Make the narration TTS-friendly:
- Avoid long clauses.
- Avoid complicated names repeated too often.
- Use punctuation to create natural pauses.
- Keep each beat concise enough to be spoken smoothly at 1.2x speed.

Do not translate line by line from the source subtitles.
Do not copy the sample wording.
Extract only the pacing, sentence shape, transition style, and narrative structure."""


def _extract_json_array(text: str) -> list[Any]:
    """Extract a JSON array from a raw LLM response."""
    stripped = text.strip()
    fenced = re.search(r"```(?:json)?\s*(\[.*?\])\s*```", stripped, re.DOTALL)
    if fenced:
        stripped = fenced.group(1)
    else:
        start = stripped.find("[")
        end = stripped.rfind("]")
        if start != -1 and end != -1 and end > start:
            stripped = stripped[start : end + 1]
    data = json.loads(stripped)
    if not isinstance(data, list):
        raise ValueError("LLM 未返回 JSON 数组 / LLM did not return a JSON array")
    return data


def _seconds_to_ms(value: Any) -> int:
    return int(round(float(value) * 1000))


def _normalize_beat(raw: dict[str, Any], fallback_index: int) -> dict[str, Any]:
    index = int(raw.get("index", raw.get("beat", fallback_index)))
    if "anchor_start_ms" in raw:
        anchor_start_ms = int(raw["anchor_start_ms"])
    else:
        anchor_start_ms = _seconds_to_ms(raw["anchor_start"])
    if "anchor_end_ms" in raw:
        anchor_end_ms = int(raw["anchor_end_ms"])
    else:
        anchor_end_ms = _seconds_to_ms(raw["anchor_end"])
    text = str(raw.get("text", "")).strip()
    if not text:
        raise ValueError(f"解说 beat 缺少 text / Narration beat missing text: {index}")
    return {
        "index": index,
        "anchor_start_ms": max(0, anchor_start_ms),
        "anchor_end_ms": max(anchor_start_ms + 1, anchor_end_ms),
        "source_indices": [int(item) for item in raw.get("source_indices", [])],
        "text": text,
        "pause_after_ms": max(0, int(raw.get("pause_after_ms", 100))),
    }


def plan_narration_beats(
    srt_path: str | Path,
    output_path: str | Path,
    api_key: str,
    model: str,
    base_url: str,
    target_language: str = "English",
    style: str = DEFAULT_RECAP_STYLE_PROMPT,
    min_beats: int = 6,
    max_beats: int = 12,
) -> list[dict[str, Any]]:
    """Plan narration beats from an extracted TTS SRT."""
    print_log("开始规划解说 beat", "Planning narration beats", input=srt_path, output=output_path)
    entries = parse_srt(srt_path)
    if not entries:
        raise ValueError("SRT文件为空 / SRT file is empty")

    source_blocks = [
        (
            f"[{entry['index']}] "
            f"{entry['start_ms'] / 1000:.3f}-{entry['end_ms'] / 1000:.3f}s "
            f"{entry['text']}"
        )
        for entry in entries
    ]
    prompt = f"""你是短视频影视解说编导。请把下面从爆款视频提取出来的旁白字幕，重新规划成{target_language}解说稿的剧情 beat。

目标风格: {style}

要求：
1. 先理解剧情事实、人物关系、冲突升级和笑点/反转，但不要输出分析过程。
2. 不要逐条改写字幕，不要保持原 SRT 条目数量；把相邻字幕合并成 {min_beats}-{max_beats} 个剧情 beat。
3. 每个 beat 是一段完整解说，适合单独生成一段 TTS，句子要自然、连贯、口语化。
4. anchor_start/anchor_end 只作为粗时间锚点，取该 beat 覆盖的原字幕起止时间，单位秒。
5. source_indices 填入该 beat 覆盖的原字幕编号。
6. pause_after_ms 是该 beat 后建议追加的停顿，通常 80-160。
7. 不要编造原字幕没有支撑的新剧情。
8. 人物译名要统一，例如 Barney=巴尼，Marshall=马歇尔。
9. 只输出 JSON 数组，不要输出 Markdown、解释或多余文本。

JSON 格式：
[
  {{
    "beat": 1,
    "anchor_start": 8.66,
    "anchor_end": 22.50,
    "source_indices": [1, 2, 3],
    "text": "一段完整解说。",
    "pause_after_ms": 120
  }}
]

原始旁白字幕：
{chr(10).join(source_blocks)}"""

    response = call_llm(prompt, api_key, model, base_url)
    raw_beats = _extract_json_array(response)
    beats = [_normalize_beat(raw, index) for index, raw in enumerate(raw_beats, 1)]
    beats.sort(key=lambda item: (item["anchor_start_ms"], item["index"]))
    for index, beat in enumerate(beats, 1):
        beat["index"] = index

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(beats, ensure_ascii=False, indent=2), encoding="utf-8")
    print_log("解说 beat 规划完成", "Narration beats planned", output=output_path, beats=len(beats))
    return beats
