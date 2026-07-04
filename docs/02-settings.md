# 02 配置项

配置默认值定义在：

```text
tkcopy/main.py::DEFAULT_SETTINGS
```

运行时本地配置保存到：

```text
.data/settings.json
```

启动时会把 `.data/settings.json` 与默认配置深合并。

## Whisper / VAD

| key | 默认值 | 说明 |
| --- | --- | --- |
| `whisper_model` | 本地 `ggml-large-v3-turbo.bin` 或 `base` | Whisper 模型 |
| `vad_model` | 本地 `ggml-silero-v6.2.0.bin` 或空 | Silero VAD 模型 |
| `vad.threshold` | `0.25` | VAD 阈值 |
| `vad.min_speech_ms` | `10` | 最短语音片段 |
| `vad.min_silence_ms` | `50` | 最短静音间隔 |
| `demucs_model` | `htdemucs` | Demucs 人声分离模型 |

## 主讲人筛选

| key | 默认值 | 说明 |
| --- | --- | --- |
| `speaker.enabled` | `true` | 是否启用主讲人筛选 |
| `speaker.similarity_threshold` | `0.82` | 主讲人相似度阈值 |
| `speaker.pyannote_model` | `pyannote/wespeaker-voxceleb-resnet34-LM` | pyannote 说话人模型 |
| `speaker.hf_token` | 空 | Hugging Face token |

## ASR

| key | 默认值 | 说明 |
| --- | --- | --- |
| `asr.language` | `en` | 识别语言 |
| `asr.prompt` | 空 | Whisper prompt |
| `asr.max_len` | `50` | 字幕最大长度 |
| `asr.split_on_word` | `true` | 按词拆分 |
| `asr.speaker_threshold` | `0.3` | ASR 行级主讲人阈值 |
| `asr.timing_offset_ms` | `820` | 时间偏移修正 |

## 镜头匹配

| key | 默认值 | 说明 |
| --- | --- | --- |
| `frame_match.engine` | `vmf` | `vmf` 或 `internal` |
| `frame_match.vmf_bin` | `/Users/chaiyapeng/Documents/autocopy/.venv/bin/vmf` | VMF 命令路径 |
| `frame_match.fps` | `3.0` | VMF 粗匹配采样帧率 |
| `frame_match.model` | `dinov2_vits14` | VMF 模型 |
| `frame_match.device` | `cpu` | VMF 运行设备 |
| `frame_match.batch_size` | `64` | VMF batch size |
| `frame_match.inflight` | `1` | VMF 并发队列数 |
| `frame_match.padding_seconds` | `90.0` | 粗匹配窗口两侧扩展秒数 |

## LLM

| key | 默认值 | 说明 |
| --- | --- | --- |
| `llm.api_key` | 空 | LLM API key |
| `llm.model` | `gemini-3.5-flash` | 模型名 |
| `llm.base_url` | `https://yunwu.ai` | API base URL |

## TTS Provider

默认：

```json
{
  "tts_provider": "voxcpm"
}
```

### VoxCPM

| key | 默认值 | 说明 |
| --- | --- | --- |
| `voxcpm.base_url` | `https://swc0syb3hwdavikr-8808.container.x-gpu.com/` | VoxCPM 服务地址 |
| `voxcpm.api_type` | `gradio` | 调用协议 |
| `voxcpm.voice` | `Natasha` | 默认声音 |
| `voxcpm.voice_refs.Natasha` | `/Users/chaiyapeng/Documents/VoxCPM/reference_audio/Natasha.mp3` | 女声参考音频 |
| `voxcpm.voice_refs.Alex` | `/Users/chaiyapeng/Documents/VoxCPM/reference_audio/Alex.mp3` | 男声参考音频 |
| `voxcpm.control` | 空 | 控制指令 |
| `voxcpm.seed` | `42` | 随机种子 |
| `voxcpm.cfg_value` | `2.0` | CFG |
| `voxcpm.inference_timesteps` | `10` | 推理步数 |
| `voxcpm.do_normalize` | `false` | 是否 normalize |
| `voxcpm.denoise` | `false` | 是否 denoise |
| `voxcpm.audio_format` | `wav` | 输出音频格式 |
| `voxcpm.timeout` | `900` | 请求超时秒数 |

### MiniMax

| key | 默认值 | 说明 |
| --- | --- | --- |
| `minimax.api_key` | 空 | API key |
| `minimax.group_id` | 空 | group id |
| `minimax.voice_id` | 空 | voice id |
| `minimax.base_url` | `https://api.minimax.chat` | API base URL |
| `minimax.speed` | `1.2` | 默认语速 |

## 剪映

| key | 默认值 | 说明 |
| --- | --- | --- |
| `jianying.draft_folder` | `/Users/chaiyapeng/Downloads/草稿/JianyingPro Drafts` | 剪映草稿目录 |

## 改写风格

默认风格在 `tkcopy.utils.script_planner.DEFAULT_RECAP_STYLE_PROMPT`。

风格库字段：

- `rewrite_styles`
- `selected_rewrite_style_id`
- `rewrite_style`

旧配置里的 `rewrite_style` 会迁移到默认风格卡片。

