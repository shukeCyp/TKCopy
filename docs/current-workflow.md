# TKCopy 当前固定流程

本文档描述当前代码实际执行的固定流程。流程入口是 `tkcopy.workflow.run_workflow`，阶段顺序由 `tkcopy.workflow_steps.WORKFLOW_STAGES` 固定。

## 输入

- 爆款视频：`viral_video`
- 原片视频：`source_video`
- 输出目录：`output_dir`
- 改写风格：`rewrite_style`
- 目标语言：`target_language`，默认 `English`
- 本地配置：`.data/settings.json`，与 `tkcopy.main.DEFAULT_SETTINGS` 深合并

## 固定阶段

| 顺序 | stage key | 中文 | 实现函数 |
| --- | --- | --- | --- |
| 1 | `tts_extraction` | TTS分离 | `run_tts_extraction_step` |
| 2 | `narration_planning` | 解说规划 | `run_narration_planning_step` |
| 3 | `frame_matching` | 镜头匹配 | `run_frame_matching_step` |
| 4 | `audio_generation` | 音频生成 | `run_audio_generation_step` |
| 5 | `jianying_export` | 导出剪映 | `run_jianying_export_step` |

每个阶段都会输出：

- `步骤开始 / Step started`
- `步骤参数 / Step parameters`
- `步骤产物 / Step artifact`
- `步骤完成 / Step completed`
- 出错时输出 `步骤失败 / Step failed`

## 输出

默认输出在用户选择的 `output_dir` 内：

- `tts/`：TTS 分离结果
- `narration_beats.json`：beat 级解说稿
- `match/`：镜头匹配结果
- `audio/`：TTS 音频与 manifest
- `文案.txt`：最终文案

剪映草稿输出到：

```text
/Users/chaiyapeng/Downloads/草稿/JianyingPro Drafts/<时间_爆款名_解说优先草稿>
```

草稿内会复制 `文案.txt`。

## 当前原则

- 不生成 final 合成视频。
- 不把 TTS 强行逐条贴回原 SRT。
- 以 beat 级解说为主线，画面跟随解说铺到剪映草稿。
- 配音片段下方电影原声为 30%。
- 非配音片段电影原声为 100%。
- 剪映导出使用 `pyJianYingDraft` + 项目内 sidecar 补齐逻辑。

