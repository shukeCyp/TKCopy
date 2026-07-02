# TKCopy 当前流程说明

本文档沉淀截至 2026-07-02 的 TKCopy 现有实现和近期调参结果。它描述的是当前代码真实在做什么，不是最终推荐架构。

当前结论先放在前面：

- 当前正式工作流是“爆款视频 TTS 分离 -> 逐条 SRT 洗稿 -> 逐条 TTS -> 镜头匹配 -> 剪映草稿”。
- 当前最终产物不是合成视频，而是剪映草稿；草稿中包含匹配后的视频片段、分段 TTS 配音、压低到 30% 的电影原声。
- 前端已经改为静态文件加载：`run.sh` 先编译 `frontend/dist`，`pywebview` 再加载本地 `index.html`，不再依赖动态 Vite dev server。
- 当前方案的主要问题不在单个 VAD 参数，而在“逐条 SRT 洗稿 + 逐条 TTS + 强行贴回原时间线”的流程本身。它更像字幕改写，不像影视解说创作。

## 1. 项目目标

TKCopy 的目标是把一个“爆款解说视频”的结构复刻到对应原片素材上，最终让用户在剪映里继续编辑。

输入：

- 爆款视频：已经剪好的短视频，通常包含旁白、字幕、画面片段。
- 源视频：原片或剧集，例如 `.mkv`。
- 设置：Whisper、VAD、Demucs、说话人筛选、LLM、MiniMax TTS 等配置。

当前输出：

- `output/.../tts/*.srt`：从爆款视频中提取的旁白字幕。
- `output/.../rewritten.srt`：LLM 洗稿后的 SRT。
- `output/.../audio/*.mp3`：按 SRT 条目生成的分段 TTS。
- `output/.../文案.txt`：洗稿后的纯文案，一行一条。
- `output/.../match/...`：镜头匹配结果和缓存。
- `~/Downloads/草稿/JianyingPro Drafts/<draft_name>`：剪映草稿。
- 草稿内 `Resources/tkcopy`：转封装后的源片 MP4、裁剪/补留白后的 TTS 资源。

当前不输出：

- 不再要求生成最终合成视频。
- `video_composer.py` 仍存在，但正式工作流中不调用。

## 2. 运行入口

### 2.1 启动命令

项目根目录执行：

```bash
./run.sh
```

`run.sh` 当前步骤：

1. 进入脚本所在目录。
2. `uv sync` 同步 Python 依赖。
3. 进入 `frontend`。
4. `npm install` 安装前端依赖。
5. `npm run build` 编译静态前端到 `frontend/dist`。
6. 回到项目根目录。
7. `uv run python tkcopy/main.py` 启动 pywebview 桌面应用。

对应文件：

- `run.sh`
- `tkcopy/main.py`
- `frontend/package.json`
- `frontend/vite.config.ts`

### 2.2 前端加载方式

当前 pywebview 加载的是本地静态文件：

```python
frontend_path = Path(__file__).parent.parent / "frontend" / "dist"
index_path = frontend_path / "index.html"
webview.create_window("TKCopy", str(index_path), js_api=api, maximized=True)
webview.start(debug=False)
```

关键点：

- 不使用 `TKCOPY_FRONTEND_URL`。
- 不启动 Vite dev server。
- 窗口默认最大化。
- `debug=False`，不打开开发工具。
- 如果 `frontend/dist/index.html` 不存在，会直接报错，提示先运行 `./run.sh`。

这次改造的原因：

- 之前使用动态前端服务，关闭窗口后前端服务可能留下野进程。
- 本地静态文件方案让桌面应用生命周期更简单，窗口退出后没有额外 dev server 需要回收。

## 3. 前端界面

当前前端是 React + Vite。

主要文件：

- `frontend/src/App.jsx`
- `frontend/src/index.css`
- `frontend/src/main.jsx`

界面结构：

- 左侧抽屉 `drawer`
  - 品牌：`TKCopy`
  - 菜单：
    - `任务`
    - `设置`
  - 底部状态：空闲、执行中、当前步骤
- 右侧主区域 `main-panel`
  - `TaskView`
  - `SettingsView`

### 3.1 任务页

任务页字段：

- `爆款视频`
- `源电影`
- `输出目录`
- `改写风格`

任务页行为：

1. 点击“选择”调用 `window.pywebview.api.select_file()`。
2. 点击“开始执行”调用 `window.pywebview.api.run_workflow()`。
3. 前端监听后端派发的浏览器事件：
   - `progress`
   - `complete`
   - `error`
4. 进度条固定显示 5 个步骤：
   - `TTS分离`
   - `文案改写`
   - `镜头匹配`
   - `音频生成`
   - `导出剪映`

### 3.2 设置页

设置页字段主要映射到 `.data/settings.json`。

Whisper / VAD / ASR：

- `whisper_model`
- `vad_model`
- `vad.threshold`
- `vad.min_speech_ms`
- `vad.min_silence_ms`
- `demucs_model`
- `speaker.enabled`
- `speaker.similarity_threshold`
- `speaker.pyannote_model`
- `speaker.hf_token`
- `asr.language`
- `asr.prompt`
- `asr.max_len`
- `asr.split_on_word`
- `asr.speaker_threshold`
- `asr.timing_offset_ms`

LLM：

- `llm.api_key`
- `llm.model`
- `llm.base_url`

MiniMax：

- `minimax.api_key`
- `minimax.group_id`
- `minimax.voice_id`
- `minimax.base_url`
- `minimax.speed`
- 代码中也支持 `volume`、`pitch`、`audio_format`，但当前前端 UI 只展示了基础字段。

默认值位置：

- 后端：`tkcopy/main.py::DEFAULT_SETTINGS`
- 前端：`frontend/src/App.jsx::DEFAULT_SETTINGS`

当前关键默认值：

```json
{
  "vad": {
    "threshold": 0.25,
    "min_speech_ms": 10,
    "min_silence_ms": 50
  },
  "speaker": {
    "enabled": true,
    "similarity_threshold": 0.82
  },
  "asr": {
    "language": "en",
    "max_len": 50,
    "split_on_word": true,
    "speaker_threshold": 0.3,
    "timing_offset_ms": 820
  },
  "minimax": {
    "speed": 1.2
  }
}
```

## 4. 后端 API

后端 API 类在 `tkcopy/main.py::Api`。

### 4.1 `get_settings`

前端启动时调用。

行为：

- 读取 `.data/settings.json`。
- 与 `DEFAULT_SETTINGS` 深合并。
- 丢弃废弃顶层 key：`tts_extract`。
- 返回完整设置。

### 4.2 `update_settings`

前端保存设置时逐项调用。

行为：

- 更新 `self.settings[key] = value`。
- 写回 `.data/settings.json`。

### 4.3 `select_file`

前端选择视频时调用。

行为：

- 调用 `webview.windows[0].create_file_dialog(webview.OPEN_DIALOG)`。
- 返回第一个文件路径。

### 4.4 `run_workflow`

前端点击“开始执行”时调用。

参数：

```json
{
  "viral_video": "...",
  "source_video": "...",
  "output_dir": "output",
  "rewrite_style": "...",
  "target_language": "Chinese"
}
```

行为：

1. 构造 `WorkflowInputs`。
2. 开启后台线程执行 `tkcopy.workflow.run_workflow()`。
3. 执行中通过 `emit_frontend_event("progress", msg)` 发进度。
4. 成功后发 `complete`。
5. 失败后发 `error`。

注意：

- 线程是 `daemon=True`。
- 当前没有任务取消机制。
- 当前没有并发任务互斥，前端靠 `running` 状态禁用按钮。

## 5. 后端主工作流

主入口：

- `tkcopy/workflow.py::run_workflow`

输入结构：

```python
WorkflowInputs(
    viral_video="爆款视频路径",
    source_video="源片路径",
    output_dir="输出目录",
    rewrite_style="改写风格",
    target_language="Chinese",
)
```

总体流程：

```text
爆款视频
  |
  v
TTS分离 -> tts.final_tts.srt
  |
  v
文案改写 -> rewritten.srt + 文案.txt
  |
  v
镜头匹配 -> matches / segments
  |
  v
音频生成 -> audio/0001.mp3 ... voice_segments
  |
  v
导出剪映 -> JianyingPro Drafts/<draft>
```

### 5.1 步骤 1：TTS 分离

调用：

```python
run_tts_extraction(
    inputs.viral_video,
    settings["whisper_model"],
    output_dir / "tts",
    vad_model=settings.get("vad_model") or default_vad_model(),
    vad_threshold=...,
    min_speech_ms=...,
    min_silence_ms=...,
    demucs_model=...,
    speaker_filter=...,
    speaker_similarity_threshold=...,
    speaker_threshold=...,
    hf_token=...,
    pyannote_model=...,
    asr_language=...,
    asr_prompt=...,
    asr_max_len=...,
    asr_split_on_word=...,
    timing_offset_ms=...,
)
```

实现文件：

- `tkcopy/utils/tts_extractor.py`

核心子步骤：

1. `extract_audio`
   - 使用 ffmpeg 从爆款视频抽取音频。
   - 输出：`output/<run>/tts/audio.wav`

2. `separate_vocals`
   - 使用 Demucs `--two-stems vocals` 分离人声和伴奏。
   - 默认模型：`htdemucs`
   - 输出：
     - `tts/separated/htdemucs/audio/vocals.wav`
     - `tts/separated/htdemucs/audio/no_vocals.wav`

3. `split_speech_segments`
   - 使用 `whisper-vad-speech-segments` + Silero VAD 模型找语音片段。
   - 根据 VAD 输出裁成单段 wav。
   - 输出：
     - `tts/vad_segments/segment_0001.wav`
     - `tts/vad_segments/segment_0002.wav`
     - `tts/vad_segments/segments.json`

4. `select_dominant_speaker`
   - 使用 pyannote/wespeaker embedding 对 VAD 片段聚类。
   - 保留累计时长最长的主讲人。
   - 输出：
     - `tts/dominant_segments.json`
     - `tts/speaker_report.json`

5. `transcribe_segments_to_srt`
   - 对主讲人片段逐段调用 `whisper-cli`。
   - 用每个片段原始 start_ms 把局部 ASR 时间还原到全局时间。
   - 可再次做行级主讲人筛选，减少角色对白混入。
   - 应用 `timing_offset_ms`，当前默认 `820ms`。
   - 输出最终 SRT：
     - `tts/<爆款视频名>.final_tts.srt`

返回结构：

```json
{
  "audio_path": "tts/audio.wav",
  "vocals_audio": "tts/separated/.../vocals.wav",
  "accompaniment_audio": "tts/separated/.../no_vocals.wav",
  "speech_segments_json": "tts/vad_segments/segments.json",
  "dominant_segments_json": "tts/dominant_segments.json",
  "speaker_report_json": "tts/speaker_report.json",
  "srt_path": "tts/<name>.final_tts.srt",
  "asr_entries": [],
  "entries": []
}
```

当前依赖：

- `ffmpeg`
- `ffprobe`
- `demucs`
- `whisper-cli`
- `whisper-vad-speech-segments`
- 本地 ggml Whisper 模型
- 本地 ggml Silero VAD 模型
- `pyannote.audio`
- `pyannote/wespeaker-voxceleb-resnet34-LM` 或兼容模型

当前已知问题：

- VAD 参数会显著影响片段边界。
- `timing_offset_ms=820` 是经验偏移，不是普适值。
- TTS 分离本质上是从成片里反推旁白，容易混入角色对白或漏掉轻声。
- 主讲人筛选依赖 embedding 和阈值，对短句、混响、BGM、人声分离质量敏感。

### 5.2 步骤 2：文案改写

调用：

```python
rewrite_srt(
    tts_result["srt_path"],
    rewritten_srt,
    api_key=settings["llm"]["api_key"],
    model=settings["llm"]["model"],
    base_url=settings["llm"]["base_url"],
    target_language=inputs.target_language,
    style=inputs.rewrite_style or settings.get("rewrite_style", ""),
)
```

实现文件：

- `tkcopy/utils/srt_rewriter.py`

当前流程：

1. `parse_srt` 读取 TTS 分离得到的 SRT。
2. 构造 prompt，要求 LLM：
   - 先内部提炼剧情事实。
   - 不逐句同义词替换。
   - 输出适合 TTS 朗读的口语化短视频解说。
   - 保持条目编号和数量不变。
   - 每行格式为 `[编号] 文案`。
3. 调用 `call_llm`。
4. 把 LLM 返回的文字写回原 SRT 的时间轴。

当前 LLM provider 判断：

- `model` 以 `gemini-` 开头，或 `base_url` 包含 `yunwu.ai`，走 Gemini 风格接口。
- 否则走 OpenAI-compatible `/v1/chat/completions`。

输出：

- `output/<run>/rewritten.srt`

当前关键限制：

- 条目数量不变。
- 时间轴沿用 TTS 分离的原始时间。
- LLM 只改文本，不重新设计讲解结构。
- 没有根据目标 TTS 时长做迭代重写。

当前主要问题：

- 这是“逐条字幕洗稿”，不是“整段解说稿创作”。
- 改写后文字长度可能超过原条目时长。
- 后续逐条 TTS 会产生自然停顿、首尾静音和不同语速，导致音频与原 SRT 时间槽不匹配。
- 为了避免音频重叠，剪映导出会顺延后续片段，造成“现在是乱的”的感受。

### 5.3 步骤 3：镜头匹配

调用：

```python
run_frame_match(
    inputs.viral_video,
    inputs.source_video,
    output_dir / "match",
)
```

实现文件：

- `tkcopy/utils/frame_matcher.py`

当前项目内自研匹配逻辑：

1. 用 `ffprobe` 读取爆款和源片：
   - fps
   - frame count
   - width / height
   - duration

2. 爆款视频特征：
   - 读取全片帧。
   - scale 到 `108x108`。
   - 转灰度。
   - `18x18` block mean。
   - normalize。

3. 源片特征：
   - 以 `CHUNK_SECONDS = 180` 分窗口处理。
   - scale 到 `192x108`。
   - 横向裁剪成 `108x108`。
   - 按 `CROP_STEP = 40` 遍历 crop。
   - 同时考虑翻转 `flipped=True/False`。
   - 同样计算 `18x18` block mean。
   - 使用缓存避免重复计算。

4. 候选搜索：
   - `scipy.spatial.cKDTree`
   - `CANDIDATE_TOP_K = 20`
   - 每个爆款帧找源片候选。

5. 连续性选择：
   - `choose_temporal_matches`
   - 优先选择 source_frame 和 viral_frame 同步递增的候选。
   - 使用 offset、crop、flipped 约束。

6. 片段构建和修正：
   - `build_segments`
   - 分数阈值：`SCORE_PERCENTILE = 99`
   - 平滑短片段。
   - 丢弃坏片段。
   - 优化边界。
   - `fill_gaps_by_extending_previous` 用前一片段补齐 gap。

7. 转成剪映可用的秒级 matches：
   - `target_start`
   - `duration`
   - `source_start`
   - `source_duration`
   - `score`
   - `max_score`
   - `crop_x`
   - `flipped`

输出目录：

```text
output/<run>/match/
  source_cache/<source_md5>/
    meta.json
    window_0000.npz
    window_0001.npz
  work/
    matches.csv
    raw_segments.json
    segments.json
    verify_summary.json
```

返回结构核心字段：

```json
{
  "segment_count": 19,
  "segment_frames": 1761,
  "viral_frames": 1761,
  "segments": "output/.../match/work/segments.json",
  "raw_segments": "output/.../match/work/raw_segments.json",
  "matches_csv": "output/.../match/work/matches.csv",
  "matches": [
    {
      "target_start": 0.0,
      "duration": 10.51,
      "source_start": 315.565,
      "source_duration": 10.51
    }
  ]
}
```

当前另有一份 VMF 方案文档：

- `画面匹配方案.md`

VMF 实验结论：

- 低 fps VMF 适合做粗定位。
- 最终剪映片段必须保证源片帧数和爆款帧数一致。
- 对 HIMYM 样例，3fps 粗匹配 + 局部逐帧精修总耗时约 213.70s。
- 逐帧精修输出的 filled segments 为 19 段，coverage 100%，frame_count_equal 为 true。

当前注意点：

- 自研 `run_frame_match` 输出是秒级 matches。
- VMF 精修方案强调最终应以整数帧为准，再换算成秒。
- 后续如果追求高精度，应把 VMF 精修输出接入正式 `run_frame_match` 或替换当前自研匹配器。

### 5.4 步骤 4：音频生成

调用：

```python
generate_srt_audio(
    entries,
    output_dir / "audio",
    api_key=settings["minimax"]["api_key"],
    group_id=settings["minimax"]["group_id"],
    voice_id=settings["minimax"]["voice_id"],
    base_url=settings["minimax"].get("base_url", "https://api.minimax.chat"),
    model=settings["minimax"].get("model", "speech-02-hd"),
    speed=float(settings["minimax"].get("speed", 1.2)),
    volume=float(settings["minimax"].get("volume", 1.0)),
    pitch=int(settings["minimax"].get("pitch", 0)),
    audio_format=settings["minimax"].get("audio_format", "mp3"),
    compose_timeline=False,
)
```

实现文件：

- `tkcopy/utils/audio_generator.py`

当前流程：

1. 读取 `rewritten.srt`。
2. `write_copy_text` 写出纯文案：
   - `output/<run>/文案.txt`
3. 遍历 SRT 条目。
4. 每条调用 MiniMax T2A V2。
5. 音频保存为：
   - `output/<run>/audio/0001.mp3`
   - `output/<run>/audio/0002.mp3`
6. 返回 `voice_segments`。

单条 TTS 请求体核心结构：

```json
{
  "model": "speech-02-hd",
  "text": "文案",
  "stream": false,
  "voice_setting": {
    "voice_id": "...",
    "speed": 1.2,
    "vol": 1.0,
    "pitch": 0
  },
  "audio_setting": {
    "sample_rate": 32000,
    "bitrate": 128000,
    "format": "mp3",
    "channel": 1
  }
}
```

返回结构：

```json
{
  "segments": [
    "output/<run>/audio/0001.mp3"
  ],
  "voice_segments": [
    {
      "path": "output/<run>/audio/0001.mp3",
      "index": 1,
      "start_ms": 8660,
      "end_ms": 11810,
      "text": "..."
    }
  ],
  "timeline": ""
}
```

当前注意点：

- `compose_timeline=False`，因此不会生成单条合成配音时间轴。
- 正式剪映导出使用分段 TTS，而不是 `voice_timeline.m4a`。
- 默认 TTS 速度已经改成 `1.2`。
- 当前 TTS 生成逻辑与 MiniMax 强耦合，后续如果切换其他 TTS，应引入 provider adapter。

### 5.5 步骤 5：导出剪映草稿

调用：

```python
create_jianying_clip_draft(
    inputs.viral_video,
    inputs.source_video,
    match_result["matches"],
    rewritten_srt,
    draft_name=Path(inputs.viral_video).stem,
    voice_segments=audio_result["voice_segments"],
    import_subtitles=False,
    source_volume=0.3,
)
```

实现文件：

- `tkcopy/utils/jianying_export.py`

当前草稿目录：

```text
~/Downloads/草稿/JianyingPro Drafts/<draft_name>
```

核心流程：

1. 读取爆款视频和源片信息：
   - width
   - height
   - duration

2. `build_clip_segments`
   - 如果 matches 已包含 `target_start`、`duration`、`source_start`，按秒级片段处理。
   - 如果是旧的 `viral_frame/source_frame` 形式，则按 `sample_interval` 转换。

3. 准备源片素材：
   - 如果源片不是 `.mkv`，直接复用。
   - 如果源片是 `.mkv`，转封装到草稿资源目录：

```text
<draft>/Resources/tkcopy/<source_stem>.mp4
```

转封装规则：

```bash
ffmpeg -i source.mkv \
  -map 0:v:0 -map 0:a? \
  -c:v copy \
  -c:a aac -b:a 192k \
  -movflags +faststart \
  output.mp4
```

这样做的原因：

- 剪映对 MKV 和部分音频编码兼容性不好。
- 之前出现过视频素材没链接进去、草稿损坏等问题。

4. 准备分段 TTS：
   - 每个 TTS 文件复制/处理到：

```text
<draft>/Resources/tkcopy/voiceover_trimmed/0001.mp3
```

   - 当前会先做首尾静音处理：

```text
silenceremove=start_periods=1:start_duration=0.08:start_threshold=-55dB:detection=rms,
areverse,
silenceremove=start_periods=1:start_duration=0.08:start_threshold=-55dB:detection=rms,
areverse,
adelay=100:all=1,
apad=pad_dur=0.1,
aresample=async=1:first_pts=0
```

含义：

- 保守裁掉首尾长静音。
- 不硬切轻声开头。
- 人工补回约 `100ms` 首尾留白。
- `aresample=async=1:first_pts=0` 用于稳定 MP3 编码时间戳，解决第 6 段曾出现的 `libmp3lame` 编码错误。

5. 规划配音片段：

```python
plan_voiceover_segments(...)
```

当前策略：

- 每段优先放在其 SRT `start_ms` 对应位置。
- 如果上一段实际音频还没结束，为避免同一音轨重叠，下一段顺延到上一段结束。
- 默认 `voice_gap_seconds = 0.0`，不再人为额外添加 100ms gap。
- 100ms 留白在音频文件内部补，不在时间线上额外插。

6. 写视频轨：

- track name：`matched_video`
- 每个匹配片段生成 `VideoSegment`。
- `source_volume=0.3`，即电影原声音量为 30%。
- 如果最后一段配音超过视频结尾，直接延长最后一个视频片段的 target duration。
- 延长时保留 source duration，调整 speed，让最后片段拉长覆盖配音。

7. 写配音轨：

- track name：`voiceover`
- 每个分段 TTS 生成 `AudioSegment`。
- 音量 `1.0`。

8. 字幕：

- 当前 `import_subtitles=False`。
- 不把 SRT 导入剪映字幕轨。

9. 保存草稿：

- `script.save()`

当前草稿验证点：

- `draft_content.json` 可解析。
- 有 1 条 video track 和 1 条 audio track。
- video segments 数量等于 matches 数量。
- audio segments 数量等于 voice_segments 数量。
- video volume 均为 `0.3`。
- `video_end >= audio_end`。
- `Resources/tkcopy` 中有可用 MP4 和裁剪后的 TTS。

## 6. 当前一次真实样例

近期使用的样例输入：

```text
爆款视频:
/Users/chaiyapeng/Downloads/对标/9/对标爆款老爸老妈的浪漫史S6E22.mp4

源片:
/Users/chaiyapeng/Downloads/对标/9/How.I.Met.Your.Mother.S06E22.1080p.AMZN.WEBRip.DDP5.1.x264-NOGRP.mkv
```

相关输出：

```text
output/quick_rewrite_20260702_103423/rewritten_fast.srt
output/quick_draft_20260702_103618/audio/*.mp3
output/quick_draft_20260702_103618/文案.txt
output/vmf-himym-coarse3-refine/frame_refine_220_400/frame_refine_summary.json
output/vad100_draft_20260702_110600/jianying_draft_manifest.json
```

最新草稿：

```text
/Users/chaiyapeng/Downloads/草稿/JianyingPro Drafts/20260702_110600_老爸老妈S6E22_快改版草稿_100msVAD_修复
```

最新草稿验证结果：

```text
tracks:
  video matched_video: 19 segments
  audio voiceover: 19 segments

video_end_s: 75.985938
audio_end_s: 75.985938
video_covers_audio: true
video_volumes: [0.3]
trimmed_count: 19
remux_mp4_count: 1
```

抽查裁剪后 TTS：

```text
0001.mp3:
  duration: 2.924813
  leading silence: ~0.0998438s
  trailing silence: ~0.1s

0006.mp3:
  duration: 3.027125
  leading silence: ~0.1s
  middle silence: ~0.286781s
  trailing silence: ~0.1s

0019.mp3:
  duration: 1.795719
  leading silence: ~0.1s
  trailing silence: ~0.09975s
```

说明：

- `0006` 中间的停顿属于句子内部停顿，当前只处理首尾静音，不处理句内停顿。
- 这版解决了“首尾硬切”和“完全没有 VAD”的问题，但没有解决逐条 SRT 洗稿带来的整体节奏问题。

## 7. 日志体系

日志工具：

- `tkcopy/logging_utils.py`

格式：

```text
[TKCopy] 中文消息 / English message | key=value key2=value2
```

当前重要日志点：

- 应用启动：
  - `准备启动应用 / Preparing to start app`
  - `加载静态前端 / Loading static frontend`
  - `窗口已创建 / Window created`
- 工作流：
  - `工作流开始 / Workflow started`
  - `配置状态 / Settings status`
  - `步骤开始: TTS分离 / Step started: TTS extraction`
  - `步骤完成: TTS分离 / Step completed: TTS extraction`
  - `工作流结束 / Workflow finished`
- 剪映导出：
  - `转封装 MKV 为剪映兼容 MP4 / Remuxing MKV to Jianying-compatible MP4`
  - `裁剪配音首尾静音 / Trimming voiceover leading/trailing silence`
  - `规划配音片段 / Planned anchored voiceover segments`
  - `延长最后视频片段覆盖配音 / Extending last video clip to cover voiceover`
  - `剪映片段草稿创建完成 / Jianying clip draft created`

注意：

- 日志里会把 API Key 状态打印成 `SET/EMPTY`，不会打印真实 key。
- `.data/settings.json` 中真实保存了密钥，文档和日志中不要直接暴露。

## 8. 依赖和外部命令

Python 版本：

```text
>=3.10,<3.11
```

Python 依赖见：

- `pyproject.toml`
- `uv.lock`

核心 Python 依赖：

- `demucs`
- `numpy`
- `pyannote-audio`
- `whispercpp`
- `pycapcut`
- `pillow`
- `pywebview`
- `scipy`

系统命令：

- `ffmpeg`
- `ffprobe`
- `demucs` 或 `python -m demucs.separate`
- `whisper-cli`
- `whisper-vad-speech-segments`

前端：

- React
- Vite
- TypeScript 作为 Vite 相关依赖

## 9. 测试覆盖

当前主要测试：

- `tests/test_main_window.py`
  - pywebview 加载静态 `frontend/dist/index.html`
  - 默认最大化
  - debug 关闭
  - 不使用旧 dev server 环境变量
  - 前端事件派发
  - 设置深合并

- `tests/test_run_script.py`
  - `run.sh` 包含静态构建前端

- `tests/test_workflow.py`
  - 完整工作流不生成 final video
  - 导出剪映草稿
  - 传入 TTS 分段
  - 电影原声 30%

- `tests/test_srt_rewriter.py`
  - LLM prompt 要求先理解剧情，不做逐句同义词替换

- `tests/test_audio_generator.py`
  - MiniMax 配置校验
  - 默认 speed 为 1.2
  - `compose_timeline=False` 时返回分段详情

- `tests/test_frame_matcher.py`
  - 匹配片段构建和平滑逻辑

- `tests/test_jianying_export.py`
  - 秒级片段写入剪映微秒时间轴
  - MKV 转封装为剪映兼容 MP4
  - 分段配音写入草稿资源
  - TTS 首尾静音裁剪 + 100ms 留白
  - 配音按 SRT anchor 放置，重叠时只顺延真实重叠
  - 最后一段视频拉长覆盖最后一句配音
  - 视频原声音量为 0.3

最近验证命令：

```bash
uv run python -m unittest discover -s tests
```

最近结果：

```text
Ran 46 tests in 1.129s
OK
```

## 10. 当前流程的核心问题

这部分是后续重构最重要的背景。

### 10.1 文案改写层的问题

当前 `rewrite_srt` 保持原 SRT 条目数量和时间轴，只替换每条文本。

这导致：

- 每条新文案长短不可控。
- TTS 生成后的实际时长不一定适配原 SRT slot。
- 如果配音比 slot 长，后续片段只能顺延。
- 一旦连续多条变长，后面整体会越来越偏。
- 逐条短句不利于形成完整影视解说节奏。

用户反馈中“感觉现在的方案还是有问题，从 TTS 改写洗稿这里我觉得方案就不对”指向的就是这里。

### 10.2 TTS 层的问题

当前 `generate_srt_audio` 每条 SRT 单独调用一次 TTS。

这导致：

- 每段音频有自己的首尾静音。
- 句间衔接不像真实连续解说。
- TTS 内部停顿不可控。
- 不同 TTS provider 的时间戳能力不同。

目前的补救：

- 首尾静音裁剪。
- 人工补 100ms 留白。
- TTS speed 默认 1.2。

但这只是局部补救，不改变上游文案结构。

### 10.3 时间线层的问题

当前剪映导出遵循：

```text
优先 SRT start_ms -> 如果音频重叠则顺延
```

这比完全连续排布更接近原 SRT，但仍有问题：

- 如果连续几条 TTS 超时，后续 start 会偏移。
- 偏移不是创作上设计出来的，而是为了避免技术上的音频重叠。
- 用户在剪映里看到的音频位置会与原 TTSSRT 不完全一致。

### 10.4 画面层的问题

当前视频片段跟随爆款时间线，而配音来自洗稿后的 TTS。

如果配音更长：

- 最后一段可以拉长覆盖。
- 中间片段不能随意整体拉长，否则会改变画面节奏。
- 这会让“画面跟解说”与“画面跟爆款原节奏”冲突。

## 11. 已讨论的下一版方向

当前还没有落地，但已经形成比较明确的方向：不要继续把流程绑死在 MiniMax，也不要继续以逐条 SRT 洗稿作为核心。

建议方向是“解说稿优先 + TTS 无关适配层”。

### 11.1 新的中间数据结构：解说 beat

不要把 LLM 输出直接写回 SRT，而是输出结构化解说稿：

```json
[
  {
    "beat": 1,
    "anchor_start": 8.66,
    "anchor_end": 22.50,
    "source_srt_ids": [1, 2, 3, 4, 5, 6, 7],
    "text": "巴尼和马歇尔表面是朋友，其实一场职场战争已经开始了。",
    "pause_after_ms": 120
  }
]
```

特点：

- 原 SRT 只作为剧情事实和粗锚点。
- LLM 可以合并多条字幕，形成完整解说段落。
- 每个 beat 是创作单位，不是字幕行。
- 后续 TTS、字幕、剪映都围绕 beat 走。

### 11.2 新的 TTS 统一结果

不管后面用 MiniMax、ElevenLabs、Azure、OpenAI TTS、火山、讯飞，都统一转成：

```json
{
  "provider": "minimax",
  "audio_path": "output/.../voice/0001.mp3",
  "duration_ms": 2920,
  "text": "...",
  "sentences": [],
  "words": []
}
```

如果 provider 支持时间戳：

- 直接读原生 sentence / word timestamp。

如果 provider 不支持时间戳：

- 用 forced alignment 做兜底。
- 可选工具方向：
  - WhisperX
  - Montreal Forced Aligner
  - aeneas

如果 provider 不支持 pause marker：

- 不在文本里塞 MiniMax 专用 pause 语法。
- 由本地 ffmpeg 根据 `pause_after_ms` 插入静音。

### 11.3 新的剪映导出策略

下一版不再是“配音贴原 SRT 时间线”，而是：

```text
解说音频时间线优先
  -> 根据每个 beat 的实际 TTS 时长铺配音
  -> 根据 beat anchor 去找对应画面片段
  -> 画面跟随解说填充
```

好处：

- TTS 不再被原 SRT 每行时长强行限制。
- 更接近短视频解说制作流程。
- 换 TTS provider 时只改 adapter，不重写剪映导出。

风险：

- 需要重新设计文案生成、音频生成和草稿导出的接口。
- 和“严格复刻爆款原视频节奏”的目标会有冲突，需要确定优先级。

## 12. 当前代码模块地图

```text
tkcopy/
  main.py
    pywebview 入口
    设置读写
    前端 API
    后台线程启动 workflow

  workflow.py
    五步主流程编排

  logging_utils.py
    中英文日志

  utils/
    tts_extractor.py
      爆款视频旁白提取
      Demucs / VAD / speaker embedding / whisper-cli

    srt_rewriter.py
      LLM 洗稿
      当前保持 SRT 条目数量和时间轴

    frame_matcher.py
      自研帧特征镜头匹配
      输出剪映可用 matches

    audio_generator.py
      MiniMax TTS
      逐 SRT 条目生成 mp3

    copy_text.py
      写文案.txt

    jianying_export.py
      pycapcut 草稿创建
      MKV 转 MP4
      TTS 裁静音 + 100ms 留白
      视频轨/配音轨写入

    video_composer.py
      旧的最终视频合成工具
      当前正式 workflow 不调用

frontend/
  src/App.jsx
    左侧抽屉
    任务页
    设置页
    pywebview API 调用

  src/index.css
    当前 UI 样式

  vite.config.ts
    base: './'
    静态资源相对路径
```

## 13. 新人接手时的调试顺序

如果草稿有问题，建议按下面顺序排查。

### 13.1 前端白屏

检查：

```bash
ls frontend/dist/index.html
npm run build --prefix frontend
uv run python tkcopy/main.py
```

确认：

- `frontend/dist/index.html` 存在。
- `vite.config.ts` 中 `base: './'`。
- `main.py` 加载的是路径字符串，不是 `file://`。
- `webview.start(debug=False)`。

### 13.2 文件选择没反应

检查：

- `window.pywebview.api.select_file` 是否存在。
- 前端是否收到 `pywebviewready`。
- `fallbackApi` 是否被误用。
- 后端日志是否出现：

```text
打开文件选择器 / Opening file picker
文件选择完成 / File picker completed
```

### 13.3 TTS 分离结果不对

检查：

- `tts/audio.wav`
- `tts/separated/.../vocals.wav`
- `tts/vad_segments/segments.json`
- `tts/dominant_segments.json`
- `tts/speaker_report.json`
- `tts/segment_asr/*.srt`
- `tts/*.final_tts.srt`

重点参数：

- `vad.threshold`
- `vad.min_speech_ms`
- `vad.min_silence_ms`
- `speaker.similarity_threshold`
- `asr.speaker_threshold`
- `asr.timing_offset_ms`

### 13.4 文案节奏不对

优先看：

- `tts/*.final_tts.srt`
- `rewritten.srt`
- `文案.txt`

判断：

- 是 TTS 分离的文本和时间就错了？
- 还是 LLM 洗稿后变长/变散？
- 还是 TTS 生成后实际时长超过原时间槽？

当前很多节奏问题源头在 `rewritten.srt` 阶段。

### 13.5 草稿打不开或素材没链接

检查草稿：

```bash
python3 - <<'PY'
import json
from pathlib import Path
p = Path("草稿路径/draft_content.json")
print(p.exists(), p.stat().st_size)
json.loads(p.read_text(encoding="utf-8"))
print("ok")
PY
```

检查资源：

```text
<draft>/Resources/tkcopy/*.mp4
<draft>/Resources/tkcopy/voiceover_trimmed/*.mp3
```

确认：

- 源片 MKV 是否已转成 AAC MP4。
- `draft_content.json` 是否是明文 JSON。
- 不要在剪映打开草稿时同时用脚本覆盖同一个草稿。

### 13.6 配音位置乱

检查：

- `voice_segments` 的 `start_ms/end_ms`。
- 裁剪后音频真实时长。
- `plan_voiceover_segments` 输出。
- 是否因为前段音频超过后段 SRT start 导致顺延。

当前逻辑：

```text
target_start = max(anchor_seconds, cursor)
cursor = target_start + duration + voice_gap_seconds
```

如果连续多段 TTS 比原 slot 长，顺延是必然的。

## 14. 当前建议的下一步重构切口

如果要从根上解决，而不是继续调 VAD，可以按这个顺序做：

1. 新增 `script_planner.py`
   - 输入原始 TTS SRT。
   - 输出 beat JSON。
   - 不再逐条保持 SRT。

2. 新增 `tts_provider.py`
   - 定义统一接口。
   - 当前 MiniMax 实现只是一个 adapter。
   - 未来可接其他 TTS。

3. 新增 `tts_alignment.py`
   - 优先使用 provider 原生时间戳。
   - 无时间戳时走 forced alignment。

4. 改 `jianying_export.py`
   - 从 `voice_segments` 切到 `NarrationSegment` / `TTSResult`。
   - 配音时间线优先。
   - 画面按 beat 时长填充。

5. 保留当前 SRT 流程为 legacy mode
   - 避免一次性重构把可运行流程打断。

## 15. 术语

爆款视频：

- 已经发布或作为对标的短视频。

源片：

- 原始剧集/电影素材，用于重新排列画面。

TTS 分离：

- 从爆款视频里提取旁白语音和字幕时间轴。

TTSSRT：

- TTS 分离得到的 SRT，用作当前洗稿和配音锚点。

洗稿：

- 当前是逐条字幕改写。后续建议升级为剧情 beat 级解说稿创作。

voice_segments：

- 当前音频生成后传给剪映导出的分段配音描述。

剪映草稿：

- pycapcut 生成的 JianyingPro Drafts 目录，不是最终视频文件。

VAD：

- Voice Activity Detection，语音活动检测，用于找人声片段或控制静音。

forced alignment：

- 给定文本和音频，反推出字/词/句在音频里的时间戳。

