import { Play } from 'lucide-react'
import {
  Button,
  CaseTable,
  NumberInput,
  Panel,
  PathPicker,
  ProgressStepper,
  SearchAction,
  Section,
  Select,
  StatusStrip,
  TextArea,
  Toolbar,
} from '../components/ui/index.jsx'

export function BatchView({
  batchForm,
  setBatchForm,
  settings,
  setSettings,
  rewriteStyles,
  running,
  progress,
  error,
  lastResult,
  batchCases,
  setBatchCases,
  onRewriteStyleChange,
  onStyleSelect,
  onPickDirectory,
  onScanBatch,
  onRunBatch,
  workflowSteps,
}) {
  const selectedStyle =
    rewriteStyles.find((style) => style.id === settings.selected_rewrite_style_id) ||
    rewriteStyles[0]

  const updateCase = (index, patch) => {
    setBatchCases(
      batchCases.map((item, itemIndex) =>
        itemIndex === index ? { ...item, ...patch } : item,
      ),
    )
  }

  return (
    <div className="page-frame batch-view">
      <Toolbar align="end">
        <SearchAction onClick={onScanBatch} disabled={running} />
        <Button icon={Play} onClick={onRunBatch} disabled={running || !batchCases.length}>
          {running ? '运行中' : '批量生成草稿'}
        </Button>
      </Toolbar>

      <div className="workbench-grid">
        <Panel className="primary-work-panel">
          <Section title="批量来源">
            <PathPicker
              label="对标根目录"
              value={batchForm.root_dir}
              onChange={(root_dir) => setBatchForm({ ...batchForm, root_dir })}
              onSelect={() => onPickDirectory('batch_root_dir')}
              placeholder="/Users/.../Downloads/对标"
              disabled={running}
            />
            <PathPicker
              label="输出目录"
              value={batchForm.output_dir}
              onChange={(output_dir) => setBatchForm({ ...batchForm, output_dir })}
              onSelect={() => onPickDirectory('batch_output_dir')}
              placeholder="output/batch"
              disabled={running}
            />
            <NumberInput
              label="Natasha 数量"
              min="0"
              max="10"
              value={batchForm.natasha_count}
              onChange={(natasha_count) => setBatchForm({ ...batchForm, natasha_count })}
            />
          </Section>

          <Section title="默认改写风格">
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
              rows={9}
            />
          </Section>
        </Panel>

        <Panel>
          <Section title="任务列表">
            <CaseTable
              cases={batchCases}
              rewriteStyles={rewriteStyles}
              onCaseChange={updateCase}
            />
          </Section>
          <Section title="执行">
            <ProgressStepper steps={workflowSteps} progress={progress} running={running} />
          </Section>
          {error && <StatusStrip type="danger">{error}</StatusStrip>}
          {lastResult && (
            <StatusStrip type="success">
              已完成：{lastResult.completed || lastResult.total || batchCases.length} 个任务
            </StatusStrip>
          )}
        </Panel>
      </div>
    </div>
  )
}
