"""文案改写工具 - 使用LLM重写SRT字幕"""
import json
import re
import ssl
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

from tkcopy.logging_utils import print_log


def parse_srt(path: str | Path) -> list[dict]:
    """解析SRT文件"""
    entries = []
    text = Path(path).read_text("utf-8").strip()
    for block in re.split(r"\n\s*\n", text):
        lines = [l.strip() for l in block.splitlines() if l.strip()]
        if len(lines) < 3 or "-->" not in lines[1]:
            continue
        start, end = lines[1].split("-->")
        entries.append({
            "index": int(lines[0]),
            "start_ms": _parse_time(start.strip()),
            "end_ms": _parse_time(end.strip()),
            "text": " ".join(lines[2:]),
        })
    return entries


def _parse_time(value: str) -> int:
    h, m, rest = value.split(":")
    s, ms = rest.split(",")
    return ((int(h) * 60 + int(m)) * 60 + int(s)) * 1000 + int(ms)


def _format_time(ms: int) -> str:
    s, ms = divmod(ms, 1000)
    m, s = divmod(s, 60)
    h, m = divmod(m, 60)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def _uses_gemini_endpoint(model: str, base_url: str) -> bool:
    return model.lower().startswith("gemini-") or "yunwu.ai" in base_url.lower()


def _build_gemini_request(prompt: str, api_key: str, model: str, base_url: str) -> urllib.request.Request:
    body = {
        "contents": [{"role": "user", "parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0.2},
    }
    url = (
        f"{base_url.rstrip('/')}/v1beta/models/{urllib.parse.quote(model)}"
        f":generateContent?key={urllib.parse.quote(api_key)}"
    )
    return urllib.request.Request(
        url,
        data=json.dumps(body, ensure_ascii=False).encode(),
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {api_key}"},
    )


def _build_openai_request(prompt: str, api_key: str, model: str, base_url: str) -> urllib.request.Request:
    body = {"model": model, "messages": [{"role": "user", "content": prompt}]}
    req = urllib.request.Request(
        f"{base_url.rstrip('/')}/v1/chat/completions",
        data=json.dumps(body, ensure_ascii=False).encode(),
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {api_key}"},
    )
    return req


def _read_llm_response(data: dict[str, Any], provider: str) -> str:
    if provider == "gemini":
        return data["candidates"][0]["content"]["parts"][0]["text"]
    return data["choices"][0]["message"]["content"]


def call_llm(prompt: str, api_key: str, model: str, base_url: str) -> str:
    """调用LLM API"""
    if not api_key.strip():
        raise ValueError("LLM API Key 缺失 / LLM API key is missing")

    provider = "gemini" if _uses_gemini_endpoint(model, base_url) else "openai"
    print_log(
        "准备请求 LLM",
        "Preparing LLM request",
        provider=provider,
        model=model,
        base_url=base_url,
        prompt_chars=len(prompt),
    )
    for attempt in range(3):
        try:
            req = (
                _build_gemini_request(prompt, api_key, model, base_url)
                if provider == "gemini"
                else _build_openai_request(prompt, api_key, model, base_url)
            )
            print_log("发送 LLM 请求", "Sending LLM request", attempt=attempt + 1, provider=provider)
            with urllib.request.urlopen(req, timeout=120) as resp:
                text = _read_llm_response(json.loads(resp.read()), provider)
                print_log("LLM 返回成功", "LLM response received", chars=len(text))
                return text
        except (urllib.error.URLError, ssl.SSLError) as e:
            if attempt == 2:
                print_log("LLM 请求失败", "LLM request failed", error=e)
                raise RuntimeError(f"LLM请求失败 / LLM request failed: {e}") from e
            print_log("LLM 请求失败，准备重试", "LLM request failed, retrying", attempt=attempt + 1, error=e)
            time.sleep(2 * (attempt + 1))
    raise RuntimeError("unreachable")


def rewrite_srt(
    srt_path: str | Path,
    output_path: str | Path,
    api_key: str,
    model: str,
    base_url: str,
    target_language: str = "Chinese",
    style: str = "localized short-video recap",
) -> Path:
    """重写SRT字幕"""
    print_log("开始文案改写", "Starting SRT rewrite", input=srt_path, output=output_path)
    entries = parse_srt(srt_path)
    print_log("读取原始字幕", "Loaded source subtitles", entries=len(entries), path=srt_path)
    if not entries:
        raise ValueError("SRT文件为空 / SRT file is empty")

    text_blocks = [f"[{i+1}] {e['text']}" for i, e in enumerate(entries)]
    prompt = f"""你是短视频影视解说编导。请把下面字幕改写成{target_language}的短视频解说稿，风格: {style}。

先理解剧情，但不要输出分析过程：
1. 先在内部提炼人物、动作、冲突、转折、结果这些剧情事实。
2. 再根据剧情事实重新组织表达，不要逐句同义词替换，不要保留原句结构。
3. 输出适合 TTS 朗读的口语化短视频解说，每条都要是完整短句，避免“转投”“但他”这类半句话。
4. 人物译名要前后一致，英文人名优先使用常见影视译名；例如 Barney=巴尼，Marshall=马歇尔，不要把 Marshall 写成马修。
5. 可以轻微补足上下文，让观众听得懂，但不要编造原字幕没有支撑的新剧情。
6. 保持条目编号和数量不变，每行一条。

{chr(10).join(text_blocks)}

只输出改写后的内容，格式: [编号] 文字"""

    rewritten = call_llm(prompt, api_key, model, base_url)
    new_texts = {}
    for line in rewritten.splitlines():
        if match := re.match(r"\[(\d+)\]\s*(.+)", line.strip()):
            new_texts[int(match.group(1))] = match.group(2)

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as f:
        for entry in entries:
            new_text = new_texts.get(entry["index"], entry["text"])
            f.write(f"{entry['index']}\n")
            f.write(f"{_format_time(entry['start_ms'])} --> {_format_time(entry['end_ms'])}\n")
            f.write(f"{new_text}\n\n")
    print_log("文案改写完成", "SRT rewrite completed", output=output_path, entries=len(entries))
    return output_path
