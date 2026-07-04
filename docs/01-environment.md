# 01 环境与启动

## 启动命令

```bash
./run.sh
```

脚本位置：`run.sh`

执行顺序：

1. 进入项目根目录。
2. `uv sync` 同步 Python 依赖。
3. 进入 `frontend`。
4. `npm install` 安装前端依赖。
5. `npm run build` 编译静态前端。
6. 回到项目根目录。
7. `uv run python tkcopy/main.py` 启动桌面应用。

## 前端加载方式

桌面应用加载：

```text
frontend/dist/index.html
```

入口代码：

```text
tkcopy/main.py
```

当前不再使用 Vite dev server，因此窗口关闭后不会遗留前端服务进程。

## Python 依赖

定义位置：`pyproject.toml`

主要依赖：

- `demucs>=4.0`：人声分离
- `pyannote-audio>=4.0.5`：主讲人筛选
- `whispercpp>=0.0.13`：本地 Whisper 相关能力
- `pywebview>=5.0`：桌面窗口
- `pyjianyingdraft>=0.2.7`：剪映草稿基础写入
- `numpy>=1.26`
- `scipy>=1.15`
- `pillow>=11.0.0`

## 系统命令

工作流依赖以下命令可用：

- `ffmpeg`
- `ffprobe`
- `whisper-cli`
- `whisper-vad-speech-segments`
- `vmf`

VMF 默认路径：

```text
/Users/chaiyapeng/Documents/autocopy/.venv/bin/vmf
```

## 本地模型默认查找路径

Whisper 模型查找顺序：

1. `.models/ggml-large-v3-turbo.bin`
2. `model/ggml-large-v3-turbo.bin`
3. `~/Documents/autocopy/model/ggml-large-v3-turbo.bin`
4. `~/Downloads/爆款文案洗稿/.models/ggml-large-v3-turbo.bin`
5. 都不存在时使用 `base`

VAD 模型查找顺序：

1. `.models/ggml-silero-v6.2.0.bin`
2. `model/ggml-silero-v6.2.0.bin`
3. `~/Documents/autocopy/model/ggml-silero-v6.2.0.bin`

