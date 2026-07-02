"""文案文件输出工具 / Copy text export helpers."""
from pathlib import Path
from typing import Any

from tkcopy.logging_utils import print_log


def write_copy_text(entries: list[dict[str, Any]], output_path: str | Path) -> Path:
    """Write all subtitle text into a plain copy file, one entry per line."""
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    lines = [str(entry.get("text", "")).strip() for entry in entries]
    text = "\n".join(line for line in lines if line)
    output_path.write_text(text + ("\n" if text else ""), encoding="utf-8")
    print_log("写入文案文件", "Copy text file written", output=output_path, lines=len([line for line in lines if line]))
    return output_path
