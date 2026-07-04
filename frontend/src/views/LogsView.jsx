import { LogList, Panel, ResultSummary, Section, StatusStrip } from '../components/ui/index.jsx'

export function LogsView({ logs, progress, error, lastResult }) {
  const lines = logs.map((item) => `${item.time}  ${item.title}${item.detail ? `  ${item.detail}` : ''}`)

  return (
    <div className="page-frame logs-view">
      {progress && <StatusStrip>{progress}</StatusStrip>}
      {error && <StatusStrip type="danger">{error}</StatusStrip>}

      <div className="workbench-grid">
        <Panel>
          <Section title="运行记录">
            <LogList logs={lines} />
          </Section>
        </Panel>

        <Panel>
          <Section title="结果">
            <ResultSummary result={lastResult} />
          </Section>
        </Panel>
      </div>
    </div>
  )
}
