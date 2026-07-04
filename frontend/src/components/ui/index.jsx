import { useId } from 'react'
import {
  CheckCircle2,
  Circle,
  FolderOpen,
  Pencil,
  Plus,
  Save,
  Search,
  Trash2,
} from 'lucide-react'

export function Button({
  children,
  icon: Icon,
  variant = 'primary',
  className = '',
  ...props
}) {
  return (
    <button className={`ui-button ui-button-${variant} ${className}`.trim()} {...props}>
      {Icon && <Icon size={16} strokeWidth={2.2} />}
      <span>{children}</span>
    </button>
  )
}

export function IconButton({ icon: Icon, label, variant = 'ghost', className = '', ...props }) {
  return (
    <button
      className={`ui-icon-button ui-icon-button-${variant} ${className}`.trim()}
      aria-label={label}
      title={label}
      {...props}
    >
      {Icon && <Icon size={16} strokeWidth={2.2} />}
    </button>
  )
}

export function Panel({ children, className = '' }) {
  return <section className={`ui-panel ${className}`.trim()}>{children}</section>
}

export function Section({ title, description, actions, children, className = '' }) {
  return (
    <section className={`ui-section ${className}`.trim()}>
      {(title || description || actions) && (
        <div className="ui-section-head">
          <div>
            {title && <div className="ui-section-title">{title}</div>}
            {description && <div className="ui-section-description">{description}</div>}
          </div>
          {actions && <div className="ui-section-actions">{actions}</div>}
        </div>
      )}
      <div className="ui-section-body">{children}</div>
    </section>
  )
}

export function Toolbar({ children, align = 'between' }) {
  return <div className={`ui-toolbar ui-toolbar-${align}`}>{children}</div>
}

export function Field({ label, description, children, wide = false, className = '' }) {
  return (
    <label className={`ui-field ${wide ? 'ui-field-wide' : ''} ${className}`.trim()}>
      <span className="ui-field-label">{label}</span>
      {description && <span className="ui-field-description">{description}</span>}
      {children}
    </label>
  )
}

export function TextInput({ className = '', onChange, ...props }) {
  return (
    <input
      className={`ui-input ${className}`.trim()}
      onChange={(event) => onChange?.(event.target.value, event)}
      {...props}
    />
  )
}

export function TextArea({ className = '', onChange, ...props }) {
  return (
    <textarea
      className={`ui-textarea ${className}`.trim()}
      onChange={(event) => onChange?.(event.target.value, event)}
      {...props}
    />
  )
}

export function Select({ options, children, className = '', onChange, ...props }) {
  return (
    <select
      className={`ui-select ${className}`.trim()}
      onChange={(event) => onChange?.(event.target.value, event)}
      {...props}
    >
      {children ||
        options?.map((option) => (
          <option key={option.value} value={option.value}>
            {option.label}
          </option>
        ))}
    </select>
  )
}

export function Checkbox({ label, checked, onChange, className = '', ...props }) {
  return (
    <label className={`ui-checkbox ${className}`.trim()}>
      <input
        type="checkbox"
        checked={checked}
        onChange={(event) => onChange?.(event.target.checked, event)}
        {...props}
      />
      <span>{label}</span>
    </label>
  )
}

export function NumberInput({ label, value, min, max, step = '1', onChange }) {
  return (
    <Field label={label}>
      <TextInput
        type="number"
        min={min}
        max={max}
        step={step}
        value={value}
        onChange={(nextValue) => onChange(Number(nextValue))}
      />
    </Field>
  )
}

export function PathPicker({
  label,
  value,
  onChange,
  onSelect,
  buttonLabel = '选择',
  placeholder,
  disabled = false,
  wide = true,
}) {
  return (
    <Field label={label} wide={wide}>
      <div className="ui-path-row">
        <TextInput
          value={value}
          onChange={onChange}
          placeholder={placeholder}
          disabled={disabled}
        />
        <Button icon={FolderOpen} variant="secondary" onClick={onSelect} disabled={disabled}>
          {buttonLabel}
        </Button>
      </div>
    </Field>
  )
}

export function StatusStrip({ type = 'neutral', children }) {
  return <div className={`status-strip status-strip-${type}`}>{children}</div>
}

export function ProgressStepper({ steps, progress, running }) {
  const progressKey = typeof progress === 'string' ? progress : progress?.step || progress?.key
  const progressMessage = typeof progress === 'string' ? progress : progress?.message
  const activeIndex = Math.max(
    0,
    steps.findIndex((step) => (step.id || step.key) === progressKey),
  )

  return (
    <div className="progress-stepper">
      {steps.map((step, index) => {
        const complete = Boolean(progress) && index < activeIndex
        const active = Boolean(progress) && index === activeIndex
        const Icon = complete ? CheckCircle2 : Circle

        return (
          <div
            key={step.id || step.key}
            className={`progress-step ${complete ? 'is-complete' : ''} ${active ? 'is-active' : ''}`.trim()}
          >
            <div className="progress-step-marker">
              <Icon size={15} strokeWidth={2.4} />
            </div>
            <div className="progress-step-copy">
              <span>{step.label}</span>
              {active && progressMessage && <small>{progressMessage}</small>}
              {active && running && !progressMessage && <small>执行中</small>}
            </div>
          </div>
        )
      })}
    </div>
  )
}

export function ResultSummary({ result }) {
  if (!result) {
    return <div className="empty-state">暂无结果</div>
  }

  const draftName = result.draft_name || result.draft || result.capcut_draft || '已生成'

  return (
    <div className="result-summary">
      <div className="result-kpi">
        <span>草稿</span>
        <strong>{draftName}</strong>
      </div>
      <pre>{JSON.stringify(result, null, 2)}</pre>
    </div>
  )
}

export function LogList({ logs }) {
  if (!logs.length) {
    return <div className="empty-state">暂无日志</div>
  }

  return (
    <div className="log-list">
      {logs.map((line, index) => (
        <div key={`${index}-${line}`} className="log-row">
          {line}
        </div>
      ))}
    </div>
  )
}

export function CaseTable({ cases, rewriteStyles, onCaseChange }) {
  if (!cases.length) {
    return <div className="empty-state">选择批量目录后，会在这里展示待处理视频对。</div>
  }

  return (
    <div className="case-table">
      <div className="case-table-head">
        <span>启用</span>
        <span>爆款视频</span>
        <span>原片</span>
        <span>配音</span>
        <span>风格</span>
      </div>
      {cases.map((item, index) => (
        <div className="case-table-row" key={`${item.viral_video}-${item.source_video}-${index}`}>
          <Checkbox
            label=""
            checked={item.enabled !== false}
            onChange={(checked) => onCaseChange(index, { enabled: checked })}
          />
          <span title={item.viral_video}>{shortPath(item.viral_video)}</span>
          <span title={item.source_video}>{shortPath(item.source_video)}</span>
          <Select
            value={item.voice || 'auto'}
            onChange={(voice) => onCaseChange(index, { voice })}
            options={[
              { value: 'auto', label: '自动' },
              { value: 'Natasha', label: 'Natasha' },
              { value: 'Alex', label: 'Alex' },
            ]}
          />
          <Select
            value={item.rewrite_style_id || 'default'}
            onChange={(rewrite_style_id) => onCaseChange(index, { rewrite_style_id })}
          >
            {rewriteStyles.map((style) => (
              <option key={style.id} value={style.id}>
                {style.name}
              </option>
            ))}
          </Select>
        </div>
      ))}
    </div>
  )
}

export function StyleCard({
  style,
  active,
  locked,
  onSelect,
  onChange,
  onDelete,
}) {
  const nameId = useId()
  const promptId = useId()

  return (
    <article className={`style-card ${active ? 'is-active' : ''}`.trim()}>
      <div className="style-card-head">
        <button className="style-select-button" onClick={onSelect}>
          <span>{style.name || '未命名风格'}</span>
          {active && <small>默认</small>}
        </button>
        <div className="style-card-actions">
          <IconButton icon={Pencil} label="设为默认" onClick={onSelect} />
          <IconButton icon={Trash2} label="删除风格" onClick={onDelete} disabled={locked} />
        </div>
      </div>
      <label htmlFor={nameId} className="style-card-label">
        命名
      </label>
      <TextInput
        id={nameId}
        value={style.name}
        onChange={(name) => onChange({ name })}
        placeholder="风格名称"
      />
      <label htmlFor={promptId} className="style-card-label">
        提示词
      </label>
      <TextArea
        id={promptId}
        value={style.prompt}
        onChange={(prompt) => onChange({ prompt })}
        placeholder="描述改写口吻、结构、节奏和禁忌"
        rows={7}
      />
    </article>
  )
}

export function SaveAction(props) {
  return (
    <Button icon={Save} {...props}>
      保存
    </Button>
  )
}

export function AddAction(props) {
  return (
    <Button icon={Plus} variant="secondary" {...props}>
      新增
    </Button>
  )
}

export function SearchAction(props) {
  return (
    <Button icon={Search} variant="secondary" {...props}>
      扫描
    </Button>
  )
}

export function shortPath(path) {
  if (!path) return '未选择'
  const parts = path.split('/')
  return parts.slice(-3).join('/')
}
