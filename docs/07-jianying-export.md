# 07 剪映导出

阶段 key：`jianying_export`

实现入口：

```text
tkcopy.workflow_steps.run_jianying_export_step
```

底层工具：

```text
tkcopy.utils.jianying_export.create_jianying_clip_draft
```

## 目标

创建剪映草稿，不生成 final 合成视频。

草稿中包含：

- 匹配后的原片视频片段
- beat 级 TTS 配音音轨
- `文案.txt`
- 新版剪映需要的工程 sidecar 文件

## 输入

- `viral_video`
- `source_video`
- `match_result.matches`
- `audio_result.voice_segments`
- `settings.jianying.draft_folder`

## 输出

默认草稿目录：

```text
/Users/chaiyapeng/Downloads/草稿/JianyingPro Drafts
```

草稿命名：

```text
YYYYMMDD_HHMMSS_<爆款视频文件名>_解说优先草稿
```

草稿内资源目录：

```text
Resources/tkcopy
```

## 剪映参数

传给 `create_jianying_clip_draft` 的固定参数：

| 参数 | 值 |
| --- | --- |
| `srt_path` | `None` |
| `voice_segments` | TTS 生成结果 |
| `import_subtitles` | `False` |
| `source_volume` | `0.3` |
| `trim_voice_silence` | `False` |
| `normal_source_volume` | `1.0` |

音量逻辑：

- 配音覆盖的视频片段：电影原声 `0.3`
- 非配音视频片段：电影原声 `1.0`

如果最后一段视频短于配音，会拉长最后视频片段覆盖配音时长。

## 素材处理

`.mkv` 源片会转封装为剪映更稳定的 `.mp4`：

- 视频流 copy
- 音频转 AAC
- 输出到 `Resources/tkcopy`

如果已有 MP4 但音频编码不兼容，会重新生成。

## 草稿库

基础草稿使用：

```text
pyJianYingDraft>=0.2.7
```

项目会额外补齐新版剪映工程索引：

- `draft_virtual_store.json`
- `performance_opt_info.json`
- `attachment_pc_common.json`
- `common_attachment/attachment_id_mapping.json`
- `common_attachment/coperate_create.json`
- `common_attachment/attachment_script_video.json`
- `common_attachment/attachment_pc_timeline.json`
- `Timelines/project.json`
- `Timelines/<timeline_id>/draft_content.json`
- `Timelines/<timeline_id>/common_attachment/*`
- `timeline_layout.json`
- `draft_agency_config.json`
- `draft_biz_config.json`

## 关键日志

- `步骤开始: 导出剪映`
- `步骤参数: 导出剪映`
- `开始创建剪映片段草稿`
- `转封装 MKV 为剪映兼容 MP4`
- `添加视频片段`
- `添加分段配音`
- `补齐剪映工程索引`
- `步骤产物: 导出剪映`
- `步骤完成: 导出剪映`

