import {
  ClipboardList,
  Library,
  ListChecks,
  ScrollText,
  Settings,
} from 'lucide-react'

const navItems = [
  { id: 'single', label: '单集任务', icon: ClipboardList },
  { id: 'batch', label: '批量任务', icon: ListChecks },
  { id: 'styles', label: '改写风格库', icon: Library },
  { id: 'settings', label: '设置', icon: Settings },
  { id: 'logs', label: '日志', icon: ScrollText },
]

export function AppShell({ activeView, running, progress, onNavigate, children }) {
  const progressText = typeof progress === 'string' ? progress : progress?.message || progress?.step

  return (
    <div className="app-shell">
      <aside className="side-rail">
        <div className="rail-brand">
          <div className="rail-mark">TK</div>
          <div>
            <strong>TKCopy</strong>
            <span>剪映解说工作台</span>
          </div>
        </div>

        <nav className="rail-nav" aria-label="主导航">
          {navItems.map((item) => (
            <button
              key={item.id}
              className={`rail-item ${activeView === item.id ? 'is-active' : ''}`.trim()}
              onClick={() => onNavigate(item.id)}
              aria-current={activeView === item.id ? 'page' : undefined}
            >
              <item.icon size={18} strokeWidth={2.15} />
              <span>{item.label}</span>
            </button>
          ))}
        </nav>

        <div className="rail-status">
          <span className={`status-dot ${running ? 'is-running' : ''}`} />
          <div>
            <strong>{running ? '流程运行中' : '待命'}</strong>
            <span>{progressText || '静态前端已就绪'}</span>
          </div>
        </div>
      </aside>

      <main className="workspace">{children}</main>
    </div>
  )
}
