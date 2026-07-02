# TKCopy - 复刻工作流工具

React + pyWebview桌面应用，将爆款视频复刻到源电影并导出剪映草稿。

## 工具模块 (`tkcopy/utils/`)

每个步骤独立封装，方便单独修改:

- `tts_extractor.py` - TTS分离（whisper转录）
- `srt_rewriter.py` - 文案改写（LLM重写）
- `frame_matcher.py` - 镜头匹配（帧hash对比）
- `audio_generator.py` - 音频生成（Minimax TTS）
- `video_composer.py` - 视频合成（ffmpeg）
- `jianying_export.py` - 剪映导出（pycapcut）

## 运行

```bash
# 同步 Python 依赖、安装并编译前端静态文件、启动 pyWebview
./run.sh
```

当前桌面应用加载 `frontend/dist/index.html`，不再依赖 Vite dev server。

需要系统已安装 `ffmpeg`、`ffprobe`、`whisper-cli` 和 `whisper-vad-speech-segments`。

## 当前流程文档

完整流程说明见:

- [docs/current-workflow.md](docs/current-workflow.md)

## ponytail

这个项目采用ponytail原则：最小依赖、最少代码、复用stdlib。
