# 05 镜头匹配

阶段 key：`frame_matching`

实现入口：

```text
tkcopy.workflow_steps.run_frame_matching_step
```

默认底层工具：

```text
tkcopy.utils.vmf_frame_matcher.run_vmf_frame_match
```

备选工具：

```text
tkcopy.utils.frame_matcher.run_frame_match
```

## 目标

把爆款视频中的画面片段匹配到原片视频中，并输出剪映可用的片段时间线。

## 默认方案

当前默认：

```json
{
  "frame_match": {
    "engine": "vmf",
    "fps": 3.0
  }
}
```

VMF 先做 3fps 粗匹配，再只在粗匹配窗口内做本地精修。

## 输入

- `viral_video`
- `source_video`
- `settings.frame_match`

## 输出

默认目录：

```text
<output_dir>/match
```

关键产物：

- `vmf_coarse/vmf_results.json`
- `vmf_coarse/source_windows.json`
- `work/matches.csv`
- `work/raw_segments.json`
- `work/segments.json`
- `work/verify_summary.json`

最终返回：

```json
{
  "matches": [
    {
      "target_start": 0.0,
      "duration": 1.2,
      "source_start": 120.5,
      "source_duration": 1.2
    }
  ]
}
```

## VMF 参数

| 参数 | 默认值 | 说明 |
| --- | --- | --- |
| `engine` | `vmf` | 使用 VMF |
| `fps` | `3.0` | 粗匹配采样帧率 |
| `model` | `dinov2_vits14` | VMF 模型 |
| `device` | `cpu` | 设备 |
| `batch_size` | `64` | batch size |
| `inflight` | `1` | in-flight 队列 |
| `padding_seconds` | `90.0` | 粗匹配窗口扩展 |

VMF 通过 `video-match-finder` Python API 内置调用，等价配置为：

```text
data_dir=<output_dir>/match/vmf_coarse/index
json=<output_dir>/match/vmf_coarse/vmf_results.json
fps=3.0
model=dinov2_vits14
device=cpu
cropdetect=false
mirror=false
batch_size=64
encode_inflight=1
use_smooth=false
```

## 内部匹配参数

当 `frame_match.engine != "vmf"` 时，使用 `run_frame_match`。

内部匹配会输出到同一个 `match/` 目录，但不走 VMF 粗匹配。

## 关键日志

- `步骤开始: 镜头匹配`
- `步骤参数: 镜头匹配`
- `VMF 镜头匹配开始`
- `读取视频帧率`
- `执行内置 VMF 3fps 粗匹配`
- `VMF 粗匹配窗口`
- `VMF 镜头匹配结束`
- `步骤产物: 镜头匹配`
- `步骤完成: 镜头匹配`
