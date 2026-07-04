# 03 TTS 分离

阶段 key：`tts_extraction`

实现入口：

```text
tkcopy.workflow_steps.run_tts_extraction_step
```

底层工具：

```text
tkcopy.utils.tts_extractor.run_tts_extraction
```

## 目标

从爆款视频中提取解说人声，并输出最终用于解说规划的 SRT。

## 输入

- `viral_video`
- `settings.whisper_model`
- `settings.vad_model`
- `settings.vad`
- `settings.demucs_model`
- `settings.speaker`
- `settings.asr`

## 输出

默认输出目录：

```text
<output_dir>/tts
```

关键产物：

- `audio.wav`：从爆款视频提取的音频
- `separated/<demucs_model>/audio/vocals.wav`：Demucs 分离后人声
- `vad_segments/segments.json`：VAD 切分片段
- `*.final_tts.srt`：最终主讲人解说字幕

## 具体参数

传给 `run_tts_extraction` 的参数：

| 参数 | 来源 | 默认值 |
| --- | --- | --- |
| `video_path` | `viral_video` | 必填 |
| `whisper_model` | `settings.whisper_model` | 本地 large-v3-turbo 或 `base` |
| `output_dir` | `<output_dir>/tts` | 必填 |
| `vad_model` | `settings.vad_model` 或 `default_vad_model()` | 本地 silero 模型 |
| `vad_threshold` | `settings.vad.threshold` | `0.25` |
| `min_speech_ms` | `settings.vad.min_speech_ms` | `10` |
| `min_silence_ms` | `settings.vad.min_silence_ms` | `50` |
| `demucs_model` | `settings.demucs_model` | `htdemucs` |
| `speaker_filter` | `settings.speaker.enabled` | `true` |
| `speaker_similarity_threshold` | `settings.speaker.similarity_threshold` | `0.82` |
| `speaker_threshold` | `settings.asr.speaker_threshold` | `0.3` |
| `hf_token` | `settings.speaker.hf_token` | 空 |
| `pyannote_model` | `settings.speaker.pyannote_model` | `pyannote/wespeaker-voxceleb-resnet34-LM` |
| `asr_language` | `settings.asr.language` | `en` |
| `asr_prompt` | `settings.asr.prompt` | 空 |
| `asr_max_len` | `settings.asr.max_len` | `50` |
| `asr_split_on_word` | `settings.asr.split_on_word` | `true` |
| `timing_offset_ms` | `settings.asr.timing_offset_ms` | `820` |

## 关键日志

- `步骤开始: TTS分离`
- `步骤参数: TTS分离`
- `TTS 分离开始`
- `提取音频`
- `开始人声分离`
- `执行 VAD 语音切分`
- `主讲人筛选完成`
- `分段 ASR 完成`
- `步骤产物: TTS分离`
- `步骤完成: TTS分离`

