# TKCopy

TKCopy 是一个 React + pywebview 桌面应用，用来把爆款影视解说视频复刻到对应原片素材上，最终输出剪映草稿。

当前固定流程是：

1. 从爆款视频分离并转录解说人声。
2. 把解说字幕规划成 6-12 个剧情 beat。
3. 用 VMF 3fps 粗匹配 + 局部精修匹配原片画面。
4. 用 VoxCPM 或 MiniMax 按 beat 生成解说配音。
5. 创建剪映草稿：视频片段按时间线排列，配音进入独立音轨，配音下方电影原声 30%，非配音片段电影原声 100%。

本项目不再把最终结果导出成合成视频，正式产物是剪映草稿。

## 启动

```bash
./run.sh
```

`run.sh` 会按顺序执行：

1. `uv sync`
2. `npm install`
3. `npm run build`
4. `uv run python tkcopy/main.py`

桌面应用加载 `frontend/dist/index.html` 静态文件，不启动 Vite dev server，关闭窗口后不会留下前端服务进程。

## 必要环境

- Python `>=3.10,<3.11`
- Node.js / npm
- `uv`
- `ffmpeg`
- `ffprobe`
- `whisper-cli`
- `whisper-vad-speech-segments`
- VMF 命令行工具，默认路径：`/Users/chaiyapeng/Documents/autocopy/.venv/bin/vmf`

## 核心目录

- `tkcopy/main.py`：pywebview 桌面入口、配置读写、前端 API。
- `tkcopy/workflow.py`：固定流程编排入口。
- `tkcopy/workflow_context.py`：工作流输入、路径、阶段定义。
- `tkcopy/workflow_steps.py`：5 个固定阶段的实现。
- `tkcopy/workflow_logging.py`：统一中英文阶段日志。
- `tkcopy/utils/`：每个具体能力的工具实现。
- `frontend/src/`：React 前端。
- `docs/`：每一步流程、工具、参数说明。

## 默认产物

执行后会生成：

- `output/tts/`：爆款视频解说提取结果。
- `output/narration_beats.json`：beat 级解说规划。
- `output/match/`：镜头匹配缓存、片段和校验结果。
- `output/audio/`：按 beat 生成的配音文件和 manifest。
- `output/文案.txt`：最终解说文案。
- `/Users/chaiyapeng/Downloads/草稿/JianyingPro Drafts/<时间_爆款名_解说优先草稿>`：剪映草稿。

剪映草稿由 `pyJianYingDraft` 写入基础草稿，再由项目补齐新版剪映需要的 `Timelines/`、`common_attachment/`、`draft_virtual_store.json` 等工程索引文件。

## 固定阶段

阶段顺序在 `tkcopy/workflow_steps.py::WORKFLOW_STAGES` 固定：

1. `tts_extraction` / `TTS分离`
2. `narration_planning` / `解说规划`
3. `frame_matching` / `镜头匹配`
4. `audio_generation` / `音频生成`
5. `jianying_export` / `导出剪映`

每个阶段都有统一日志：

- `步骤开始`
- `步骤参数`
- `步骤产物`
- `步骤完成`
- `步骤失败`

## 文档

- [环境与启动](docs/01-environment.md)
- [配置项](docs/02-settings.md)
- [TTS 分离](docs/03-tts-extraction.md)
- [解说规划](docs/04-narration-planning.md)
- [镜头匹配](docs/05-frame-matching.md)
- [TTS 生成](docs/06-tts-generation.md)
- [剪映导出](docs/07-jianying-export.md)
- [批量处理](docs/08-batch-processing.md)
- [日志与排查](docs/09-logging-and-debugging.md)

完整流程总览见 [当前工作流](docs/current-workflow.md)。

## 验证

```bash
uv run python -m unittest discover -s tests
npm --prefix frontend run build
```
