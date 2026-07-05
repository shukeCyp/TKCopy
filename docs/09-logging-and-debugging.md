# 09 日志与排查

所有运行时日志使用：

```text
tkcopy.logging_utils.print_log
```

格式：

```text
[TKCopy] 中文 / English | key=value key=value
```

## 工作流阶段日志

统一由：

```text
tkcopy.workflow_logging.WorkflowLogger
```

输出。

每个阶段都会输出：

```text
步骤开始: <阶段>
步骤参数: <阶段>
步骤产物: <阶段>
步骤完成: <阶段>
```

失败时输出：

```text
步骤失败: <阶段>
```

日志中固定包含：

```text
stage=<stage_key>
```

## 关键排查点

### 前端空白

看启动日志：

```text
加载静态前端 / Loading static frontend | path=...
```

确认：

```text
frontend/dist/index.html
```

存在。如果不存在，运行：

```bash
npm --prefix frontend run build
```

### TTS 分离失败

看：

- `TTS 分离开始`
- `提取音频`
- `开始人声分离`
- `执行 VAD 语音切分`
- `分段 ASR 完成`

常见原因：

- `ffmpeg` 不存在
- `whisper-cli` 不存在
- `whisper_model` 路径不对
- `vad_model` 路径不对
- pyannote 模型或 token 不可用

### VMF 没有匹配窗口

错误：

```text
VMF 没有找到粗匹配窗口 / VMF found no coarse source windows
```

优先检查：

- `frame_match.fps`
- `frame_match.model`
- `video-match-finder` 依赖是否已由 `uv sync` 安装
- 爆款视频和原片是否对应同一集
- 原片是否需要更大 `padding_seconds`

### VoxCPM 失败

看：

- `调用 VoxCPM 本地 Gradio 配音服务`
- `VoxCPM Gradio v2 不可用，切换旧版协议`
- `VoxCPM 配音完成`

常见原因：

- `voxcpm.base_url` 填错
- 服务没启动
- Gradio 端口不是 8808
- 参考音频路径不存在

### 剪映草稿打不开

看是否有：

```text
补齐剪映工程索引 / Wrote Jianying project sidecars
```

草稿目录应包含：

- `draft_content.json`
- `draft_meta_info.json`
- `draft_virtual_store.json`
- `Timelines/project.json`
- `timeline_layout.json`
- `common_attachment/attachment_id_mapping.json`
- `Timelines/<timeline_id>/draft_content.json`

如果素材显示无权限，检查 `Resources/tkcopy` 下的视频和音频文件是否存在。
