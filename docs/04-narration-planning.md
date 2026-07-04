# 04 解说规划

阶段 key：`narration_planning`

实现入口：

```text
tkcopy.workflow_steps.run_narration_planning_step
```

底层工具：

```text
tkcopy.utils.script_planner.plan_narration_beats
```

## 目标

把 TTS 分离得到的 SRT 当作剧情素材和粗时间锚点，规划成 beat 级解说稿。

当前不按 SRT 单条洗稿。

## 输入

- `<output_dir>/tts/*.final_tts.srt`
- `settings.llm`
- `rewrite_style`
- `target_language`

## 输出

```text
<output_dir>/narration_beats.json
```

每个 beat 的结构：

```json
{
  "index": 1,
  "anchor_start_ms": 8660,
  "anchor_end_ms": 22500,
  "source_indices": [1, 2, 3],
  "text": "A complete narration beat.",
  "pause_after_ms": 120
}
```

## 具体参数

传给 `plan_narration_beats` 的参数：

| 参数 | 来源 | 默认值 |
| --- | --- | --- |
| `srt_path` | TTS 分离产物 | 必填 |
| `output_path` | `<output_dir>/narration_beats.json` | 必填 |
| `api_key` | `settings.llm.api_key` | 空 |
| `model` | `settings.llm.model` | `gemini-3.5-flash` |
| `base_url` | `settings.llm.base_url` | `https://yunwu.ai` |
| `target_language` | 前端传入 | `English` |
| `style` | 前端选中风格或 `settings.rewrite_style` | 默认海外影视解说风格 |
| `min_beats` | 函数默认 | `6` |
| `max_beats` | 函数默认 | `12` |

## 默认风格

默认风格强调：

- English short-form TV/movie recap style
- 句子短，通常 6-12 个词
- 直接进入冲突、谜题、危险或异常行动
- beat 内有小弧线：发生了什么、为什么重要、下一步反转
- TTS-friendly，适合 1.2x 语速
- 不逐句翻译，不复制样本文案

## 关键日志

- `步骤开始: 解说规划`
- `步骤参数: 解说规划`
- `开始规划解说 beat`
- `准备请求 LLM`
- `发送 LLM 请求`
- `LLM 返回成功`
- `解说 beat 规划完成`
- `步骤产物: 解说规划`
- `步骤完成: 解说规划`
