# 06 TTS 生成

阶段 key：`audio_generation`

实现入口：

```text
tkcopy.workflow_steps.run_audio_generation_step
```

底层工具：

```text
tkcopy.utils.copy_text.write_copy_text
tkcopy.utils.tts_provider.synthesize_narration_audio
```

## 目标

把 `narration_beats.json` 中每个 beat 的 `text` 生成一段 TTS 音频，并写出文案文件。

## 输入

- `<output_dir>/narration_beats.json`
- `settings.tts_provider`
- `settings.voxcpm`
- `settings.minimax`

## 输出

```text
<output_dir>/文案.txt
<output_dir>/audio/
```

`audio/` 中包含：

- `0001.wav` 或 `0001.mp3`
- `0002.wav` 或 `0002.mp3`
- `tts_result_manifest.json`

返回给剪映导出的 `voice_segments` 结构：

```json
{
  "path": "output/audio/0001.wav",
  "index": 1,
  "start_ms": 0,
  "end_ms": 3000,
  "text": "Narration text"
}
```

## Provider 选择

`settings.tts_provider`：

- `voxcpm`：默认
- `minimax`

## VoxCPM 参数

| 参数 | 默认值 |
| --- | --- |
| `base_url` | `https://swc0syb3hwdavikr-8808.container.x-gpu.com/` |
| `api_type` | `gradio` |
| `voice` | `Natasha` |
| `control` | 空 |
| `seed` | `42` |
| `cfg_value` | `2.0` |
| `inference_timesteps` | `10` |
| `do_normalize` | `false` |
| `denoise` | `false` |
| `audio_format` | `wav` |
| `timeout` | `900` |

参考音频：

```text
Natasha -> /Users/chaiyapeng/Documents/VoxCPM/reference_audio/Natasha.mp3
Alex    -> /Users/chaiyapeng/Documents/VoxCPM/reference_audio/Alex.mp3
```

Gradio 调用会优先请求：

```text
/gradio_api/call/v2/generate
```

如果服务返回 405 / 422 / 500，会自动切换：

```text
/gradio_api/call/generate
```

## MiniMax 参数

| 参数 | 默认值 |
| --- | --- |
| `base_url` | `https://api.minimax.chat` |
| `model` | `speech-02-hd` |
| `speed` | `1.2` |
| `volume` | `1.0` |
| `pitch` | `0` |
| `audio_format` | `mp3` |

MiniMax 需要：

- `api_key`
- `group_id`
- `voice_id`

## 关键日志

- `步骤开始: 音频生成`
- `步骤参数: 音频生成`
- `写入文案文件`
- `开始生成 beat 级配音`
- `生成 beat 配音`
- `调用 VoxCPM 本地 Gradio 配音服务`
- `VoxCPM 配音完成`
- `beat 级配音完成`
- `步骤产物: 音频生成`
- `步骤完成: 音频生成`

