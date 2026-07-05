# TKCopy

TKCopy 是一个 React + pywebview 桌面应用，用来把爆款影视解说视频复刻到对应原片素材上，最终输出剪映草稿。

项目当前不导出合成视频，正式产物是剪映草稿。剪映草稿会包含原片画面片段、按 beat 生成的解说配音、文案文件和新版剪映需要的工程索引文件。

## 核心流程

固定工作流在 `tkcopy/workflow_steps.py::WORKFLOW_STAGES` 中定义：

1. `tts_extraction` / `TTS分离`：从爆款视频分离人声并转录字幕。
2. `narration_planning` / `解说规划`：把字幕规划成 6-12 个剧情 beat。
3. `frame_matching` / `镜头匹配`：用内置 VMF 3fps 粗匹配，再做局部逐帧精修。
4. `audio_generation` / `音频生成`：用 VoxCPM 或 MiniMax 按 beat 生成解说配音。
5. `jianying_export` / `导出剪映`：创建剪映草稿，视频片段按时间线排列，配音进入独立音轨。

音量规则：

- 配音覆盖片段下方的电影原声为 30%。
- 非配音片段的电影原声为 100%。

## 快速启动

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

VMF 不再需要外部 `vmf` 命令。项目通过 `video-match-finder` Python 依赖内置调用 VMF，`uv sync` 会安装到项目环境中。

## 本地模型

当前仓库使用的模型目录是：

```text
model/
```

已准备提交的模型文件：

```text
model/ggml-base.en.bin
model/ggml-silero-v6.2.0.bin
```

VAD 模型会优先自动查找：

1. `.models/ggml-silero-v6.2.0.bin`
2. `model/ggml-silero-v6.2.0.bin`
3. `~/Documents/autocopy/model/ggml-silero-v6.2.0.bin`

Whisper 默认会优先查找 `ggml-large-v3-turbo.bin`，找不到时使用 `base`。如果要强制使用仓库里的英文 base 模型，在设置页把 Whisper 模型填为：

```text
model/ggml-base.en.bin
```

模型文件较大，提交到 GitHub 时建议使用 Git LFS，尤其是 `ggml-base.en.bin` 超过 100 MiB。

## 配置

默认配置定义在：

```text
tkcopy/main.py::DEFAULT_SETTINGS
```

运行时本地配置保存到：

```text
.data/settings.json
```

启动时会把 `.data/settings.json` 与默认配置深合并。

常用配置项：

- `whisper_model`：Whisper 模型路径或 `base`。
- `vad_model`：Silero VAD 模型路径。
- `frame_match.engine`：`vmf` 或 `internal`，默认 `vmf`。
- `frame_match.fps`：VMF 粗匹配采样帧率，默认 `3.0`。
- `llm.api_key`、`llm.model`、`llm.base_url`：解说规划使用的 LLM 配置。
- `tts_provider`：`voxcpm` 或 `minimax`，默认 `voxcpm`。
- `voxcpm.base_url`：VoxCPM 服务地址。
- `minimax.api_key`、`minimax.group_id`、`minimax.voice_id`：MiniMax 配音配置。
- `jianying.draft_folder`：剪映草稿目录。

完整配置说明见 [配置项](docs/02-settings.md)。

## 默认产物

执行后会生成：

- `output/tts/`：爆款视频解说提取结果。
- `output/narration_beats.json`：beat 级解说规划。
- `output/match/`：镜头匹配缓存、片段和校验结果。
- `output/audio/`：按 beat 生成的配音文件和 manifest。
- `output/文案.txt`：最终解说文案。
- `/Users/chaiyapeng/Downloads/草稿/JianyingPro Drafts/<时间_爆款名_解说优先草稿>`：剪映草稿。

剪映草稿由 `pyJianYingDraft` 写入基础草稿，再由项目补齐新版剪映需要的 `Timelines/`、`common_attachment/`、`draft_virtual_store.json` 等工程索引文件。

## 核心目录

- `tkcopy/main.py`：pywebview 桌面入口、配置读写、前端 API。
- `tkcopy/workflow.py`：固定流程编排入口。
- `tkcopy/workflow_context.py`：工作流输入、路径、阶段定义。
- `tkcopy/workflow_steps.py`：5 个固定阶段的实现。
- `tkcopy/workflow_logging.py`：统一中英文阶段日志。
- `tkcopy/utils/`：每个具体能力的工具实现。
- `frontend/src/`：React 前端。
- `docs/`：每一步流程、工具、参数说明。
- `model/`：本地模型文件。

## 常用命令

同步 Python 依赖：

```bash
uv sync
```

构建前端：

```bash
npm --prefix frontend run build
```

启动桌面应用：

```bash
uv run python tkcopy/main.py
```

完整验证：

```bash
uv run python -m unittest discover -s tests
npm --prefix frontend run build
uv sync --locked
```

## 日志

每个阶段都有统一中英文日志：

- `步骤开始`
- `步骤参数`
- `步骤产物`
- `步骤完成`
- `步骤失败`

排查流程见 [日志与排查](docs/09-logging-and-debugging.md)。

## 打包注意事项

后续打包 exe 时，VMF 已经不依赖外部 `vmf` 命令，但仍需要处理这些运行时依赖：

- `ffmpeg` / `ffprobe`
- `whisper-cli`
- `whisper-vad-speech-segments`
- `torch` / `torchvision`
- `faiss-cpu`
- 本地模型文件
- VoxCPM 或 MiniMax 的外部服务/API 配置

模型和二进制依赖会影响包体大小。建议先保持模型外置或使用 Git LFS 管理，再根据目标平台决定是否随 exe 打包。

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
