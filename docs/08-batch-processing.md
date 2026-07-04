# 08 批量处理

批量入口：

```text
tkcopy.batch.scan_batch_cases
tkcopy.batch.run_batch_workflows
```

前端 API：

```text
tkcopy.main.Api.scan_batch_cases
tkcopy.main.Api.run_batch_workflow
```

## 批量扫描

输入：

```text
root_dir
voice_split_count
```

默认：

```text
voice_split_count = 5
```

扫描规则：

- 如果根目录本身包含视频文件，就把根目录当成一个 case。
- 否则把根目录下每个子目录当成一个 case。
- 支持视频后缀：`.mp4`, `.mkv`, `.mov`, `.avi`, `.m4v`, `.webm`

爆款视频识别关键词：

- `对标`
- `爆款`
- `viral`
- `hot`
- `copy`

原片视频识别关键词：

- `原片`
- `source`
- `movie`
- `episode`

如果没有关键词：

- 爆款优先 `.mp4` / `.mov` / `.m4v`
- 原片优先 `.mkv`

## 声音分配

默认前 5 个 ready case 使用：

```text
Natasha
```

第 6 个及之后使用：

```text
Alex
```

## 批量执行

每个 case 会顺序执行完整 `run_workflow`。

case 输出目录：

```text
<output_root>/case_<序号>_<voice>_<case_id>
```

批量输出根目录由前端生成：

```text
<output_dir>/batch_YYYYMMDD_HHMMSS
```

## 失败处理

某个 case 失败不会中断后续 case。

每个 case 返回：

```json
{
  "ok": true,
  "index": 1,
  "total": 10,
  "case_id": "1",
  "voice": "Natasha",
  "output_dir": "...",
  "jianying_draft": "...",
  "copy_text": "..."
}
```

失败时：

```json
{
  "ok": false,
  "error": "..."
}
```

## 关键日志

- `批量目录扫描完成`
- `批量工作流开始`
- `批量案例开始`
- `批量案例完成`
- `批量案例失败`
- `批量工作流结束`

