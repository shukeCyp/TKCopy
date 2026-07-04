import { Play, Save } from 'lucide-react'
import {
  Button,
  Panel,
  PathPicker,
  ProgressStepper,
  Section,
  Select,
  StatusStrip,
  TextArea,
  Toolbar,
} from '../components/ui/index.jsx'

export function SingleTaskView({
  form,
  setForm,
  settings,
  rewriteStyles,
  setSettings,
  running,
  progress,
  error,
  lastResult,
  onRewriteStyleChange,
  onStyleSelect,
  onPickFile,
  onPickDirectory,
  onRun,
  workflowSteps,
}) {
  const selectedStyle =
    rewriteStyles.find((style) => style.id === settings.selected_rewrite_style_id) ||
    rewriteStyles[0]

  return (
    <div className="page-frame single-task-view">
      <Toolbar align="end">
        <Button icon={Play} onClick={onRun} disabled={running}>
          {running ? '运行中' : '开始生成草稿'}
        </Button>
      </Toolbar>

      <div className="workbench-grid">
        <Panel className="primary-work-panel">
          <Section title="素材">
            <PathPicker
              label="爆款视频"
              value={form.viral_video}
              onChange={(viral_video) => setForm({ ...form, viral_video })}
              onSelect={() => onPickFile('viral_video')}
              placeholder="/path/to/viral.mp4"
              disabled={running}
            />
            <PathPicker
              label="原片视频"
              value={form.source_video}
              onChange={(source_video) => setForm({ ...form, source_video })}
              onSelect={() => onPickFile('source_video')}
              placeholder="/path/to/source.mkv"
              disabled={running}
            />
            <PathPicker
              label="输出目录"
              value={form.output_dir}
              onChange={(output_dir) => setForm({ ...form, output_dir })}
              onSelect={() => onPickDirectory('output_dir')}
              placeholder="output"
              disabled={running}
            />
          </Section>

          <Section
            title="改写风格"
            actions={
              <Button
                icon={Save}
                variant="secondary"
                onClick={() =>
                  setSettings({
                    ...settings,
                    rewrite_styles: rewriteStyles.map((style) =>
                      style.id === selectedStyle.id
                        ? { ...style, prompt: settings.rewrite_style }
                        : style,
                    ),
                  })
                }
              >
                同步到风格库
              </Button>
            }
          >
            <Select
              value={selectedStyle?.id}
              onChange={onStyleSelect}
            >
              {rewriteStyles.map((style) => (
                <option key={style.id} value={style.id}>
                  {style.name}
                </option>
              ))}
            </Select>
            <TextArea
              value={settings.rewrite_style}
              onChange={onRewriteStyleChange}
              rows={11}
            />
          </Section>
        </Panel>

        <Panel>
          <Section title="执行">
            <ProgressStepper steps={workflowSteps} progress={progress} running={running} />
          </Section>
          {error && <StatusStrip type="danger">{error}</StatusStrip>}
          {lastResult && (
            <StatusStrip type="success">
              草稿已生成：{lastResult.draft_name || lastResult.draft || lastResult.capcut_draft || '完成'}
            </StatusStrip>
          )}
          <Section title="当前配置">
            <div className="settings-snapshot">
              <span>配音</span>
              <strong>{settings.voxcpm?.voice || settings.minimax?.voice_id || '未设置'}</strong>
              <span>TTS</span>
              <strong>{settings.tts_provider || 'voxcpm'}</strong>
              <span>匹配 FPS</span>
              <strong>{settings.frame_match?.fps ?? 3}</strong>
              <span>电影原声</span>
              <strong>解说 30% / 空档 100%</strong>
            </div>
          </Section>
        </Panel>
      </div>
    </div>
  )
}
