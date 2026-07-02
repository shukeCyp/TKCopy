import { useEffect, useId, useState } from 'react'

const DEFAULT_RECAP_STYLE_PROMPT = `Write in fast-paced English short-form TV/movie recap style.

Use short, clear, conversational sentences. Most sentences should be 6-12 words.
Start directly with the main conflict, mystery, danger, or unusual action. Do not add greetings, introductions, or background explanation.
Narrate events in a clean chronological order, but make every beat feel like it is moving toward a new complication.
Each beat should contain a simple mini-arc: what happened, why it matters, and what new twist or reaction follows.

Use natural transition phrases such as:
- But...
- When...
- After...
- Before long...
- Suddenly...
- Meanwhile...
- That's when...
- To his surprise...
- At the same time...
- With this lead...

Use mild suspense and forward momentum. Phrases like "he had no idea", "something unexpected happened", "the plan was about to unfold", or "the truth was finally revealed" are allowed when appropriate.

Keep the tone objective but engaging. Do not over-hype. Do not use Chinese short-video exaggeration. Do not add fake jokes, internet slang, or dramatic clickbait unless the scene itself is comedic.
For comedy scenes, allow light sarcasm or dry humor, but still prioritize clear plot progression.
For crime or medical scenes, keep the tone serious, direct, and procedural.

Make the narration TTS-friendly:
- Avoid long clauses.
- Avoid complicated names repeated too often.
- Use punctuation to create natural pauses.
- Keep each beat concise enough to be spoken smoothly at 1.2x speed.

Do not translate line by line from the source subtitles.
Do not copy the sample wording.
Extract only the pacing, sentence shape, transition style, and narrative structure.`

const DEFAULT_SETTINGS = {
  whisper_model: 'base',
  vad_model: '',
  vad: { threshold: 0.25, min_speech_ms: 10, min_silence_ms: 50 },
  demucs_model: 'htdemucs',
  speaker: {
    enabled: true,
    similarity_threshold: 0.82,
    pyannote_model: 'pyannote/wespeaker-voxceleb-resnet34-LM',
    hf_token: '',
  },
  asr: {
    language: 'en',
    prompt: '',
    max_len: 50,
    split_on_word: true,
    speaker_threshold: 0.3,
    timing_offset_ms: 820,
  },
  rewrite_style: DEFAULT_RECAP_STYLE_PROMPT,
  llm: { api_key: '', model: 'gemini-3.5-flash', base_url: 'https://yunwu.ai' },
  tts_provider: 'minimax',
  minimax: {
    api_key: '',
    group_id: '',
    voice_id: '',
    base_url: 'https://api.minimax.chat',
    speed: 1.2,
  },
  voxcpm: {
    base_url: '',
    api_type: 'synthesize',
    voice: 'Natasha',
    voice_refs: {
      Natasha: '',
      Alex: '',
    },
    control: '',
    seed: 42,
    cfg_value: 2.0,
    inference_timesteps: 10,
    do_normalize: false,
    denoise: false,
    audio_format: 'wav',
    timeout: 900,
  },
}

const fallbackApi = {
  get_settings: async () => DEFAULT_SETTINGS,
  update_settings: async () => ({ ok: true }),
  run_workflow: async () => ({ ok: true, message: 'mock: workflow started' }),
  select_file: async () => ({ path: '/mock/path/video.mp4' }),
}

const requiredApiMethods = ['get_settings', 'update_settings', 'run_workflow', 'select_file']

function getApi() {
  const pywebviewApi = window.pywebview?.api

  if (!pywebviewApi) return fallbackApi

  return requiredApiMethods.every((method) => typeof pywebviewApi[method] === 'function')
    ? pywebviewApi
    : fallbackApi
}

const steps = ['TTS分离', '解说规划', '镜头匹配', '音频生成', '导出剪映']

function mergeSettings(settings) {
  return {
    ...DEFAULT_SETTINGS,
    ...settings,
    vad: { ...DEFAULT_SETTINGS.vad, ...(settings?.vad || {}) },
    speaker: { ...DEFAULT_SETTINGS.speaker, ...(settings?.speaker || {}) },
    asr: { ...DEFAULT_SETTINGS.asr, ...(settings?.asr || {}) },
    llm: { ...DEFAULT_SETTINGS.llm, ...(settings?.llm || {}) },
    minimax: { ...DEFAULT_SETTINGS.minimax, ...(settings?.minimax || {}) },
    voxcpm: {
      ...DEFAULT_SETTINGS.voxcpm,
      ...(settings?.voxcpm || {}),
      voice_refs: {
        ...DEFAULT_SETTINGS.voxcpm.voice_refs,
        ...(settings?.voxcpm?.voice_refs || {}),
      },
    },
  }
}

export default function App() {
  const [activeView, setActiveView] = useState('task')
  const [settings, setSettings] = useState(DEFAULT_SETTINGS)
  const [viralVideo, setViralVideo] = useState('')
  const [sourceVideo, setSourceVideo] = useState('')
  const [outputDir, setOutputDir] = useState('output')
  const [rewriteStyle, setRewriteStyle] = useState('')
  const [progress, setProgress] = useState('')
  const [running, setRunning] = useState(false)
  const [error, setError] = useState('')
  const [settingsStatus, setSettingsStatus] = useState('')

  useEffect(() => {
    const loadSettings = () => {
      getApi().get_settings()
      .then((loadedSettings) => {
        const nextSettings = mergeSettings(loadedSettings)
        setSettings(nextSettings)
        setRewriteStyle(nextSettings.rewrite_style || '')
      })
      .catch((e) => setError('加载配置失败: ' + e.message))
    }

    const onProgress = (e) => setProgress(e.detail)
    const onComplete = () => {
      setRunning(false)
      setProgress('完成')
    }
    const onError = (e) => {
      setRunning(false)
      setError(e.detail)
    }

    const onPywebviewReady = () => {
      loadSettings()
    }

    loadSettings()
    window.addEventListener('progress', onProgress)
    window.addEventListener('complete', onComplete)
    window.addEventListener('error', onError)
    window.addEventListener('pywebviewready', onPywebviewReady)

    return () => {
      window.removeEventListener('progress', onProgress)
      window.removeEventListener('complete', onComplete)
      window.removeEventListener('error', onError)
      window.removeEventListener('pywebviewready', onPywebviewReady)
    }
  }, [])

  const selectFile = async (setter) => {
    try {
      const result = await getApi().select_file()
      if (result.path) setter(result.path)
    } catch (e) {
      setError('选择文件失败: ' + e.message)
    }
  }

  const runWorkflow = async () => {
    if (!viralVideo || !sourceVideo) {
      setError('请选择爆款视频和源电影')
      return
    }

    setError('')
    setRunning(true)
    setProgress('启动...')

    try {
      await getApi().run_workflow({
        viral_video: viralVideo,
        source_video: sourceVideo,
        output_dir: outputDir,
        rewrite_style: rewriteStyle,
      })
    } catch (e) {
      setRunning(false)
      setError('启动失败: ' + e.message)
    }
  }

  const updateTopLevelSetting = (key, value) => {
    setSettings((current) => ({ ...current, [key]: value }))
  }

  const updateNestedSetting = (section, key, value) => {
    setSettings((current) => ({
      ...current,
      [section]: {
        ...current[section],
        [key]: value,
      },
    }))
  }

  const saveSettings = async () => {
    setSettingsStatus('保存中...')
    setError('')

    try {
      const normalized = mergeSettings(settings)
      await getApi().update_settings('whisper_model', normalized.whisper_model)
      await getApi().update_settings('vad_model', normalized.vad_model)
      await getApi().update_settings('vad', normalized.vad)
      await getApi().update_settings('demucs_model', normalized.demucs_model)
      await getApi().update_settings('speaker', normalized.speaker)
      await getApi().update_settings('asr', normalized.asr)
      await getApi().update_settings('rewrite_style', normalized.rewrite_style)
      await getApi().update_settings('llm', normalized.llm)
      await getApi().update_settings('tts_provider', normalized.tts_provider)
      await getApi().update_settings('minimax', normalized.minimax)
      await getApi().update_settings('voxcpm', normalized.voxcpm)
      setSettings(normalized)
      setRewriteStyle(normalized.rewrite_style)
      setSettingsStatus('已保存')
    } catch (e) {
      setSettingsStatus('')
      setError('保存配置失败: ' + e.message)
    }
  }

  return (
    <div className="app-shell">
      <aside className="drawer">
        <div className="brand">
          <div className="brand-mark">TK</div>
          <div>
            <div className="brand-name">TKCopy</div>
            <div className="brand-subtitle">复刻工作流</div>
          </div>
        </div>

        <nav className="drawer-nav" aria-label="主导航">
          <button
            className={activeView === 'task' ? 'nav-item active' : 'nav-item'}
            onClick={() => setActiveView('task')}
          >
            任务
          </button>
          <button
            className={activeView === 'settings' ? 'nav-item active' : 'nav-item'}
            onClick={() => setActiveView('settings')}
          >
            设置
          </button>
        </nav>

        <div className="drawer-status">
          <span className={running ? 'status-dot running' : 'status-dot'} />
          <span>{running ? progress || '执行中' : progress || '空闲'}</span>
        </div>
      </aside>

      <main className="main-panel">
        {activeView === 'task' ? (
          <TaskView
            viralVideo={viralVideo}
            sourceVideo={sourceVideo}
            outputDir={outputDir}
            rewriteStyle={rewriteStyle}
            running={running}
            progress={progress}
            error={error}
            onSelectViral={() => selectFile(setViralVideo)}
            onSelectSource={() => selectFile(setSourceVideo)}
            onViralChange={setViralVideo}
            onSourceChange={setSourceVideo}
            onOutputDirChange={setOutputDir}
            onRewriteStyleChange={setRewriteStyle}
            onRun={runWorkflow}
          />
        ) : (
          <SettingsView
            settings={settings}
            status={settingsStatus}
            error={error}
            onTopLevelChange={updateTopLevelSetting}
            onNestedChange={updateNestedSetting}
            onSave={saveSettings}
          />
        )}
      </main>
    </div>
  )
}

function TaskView({
  viralVideo,
  sourceVideo,
  outputDir,
  rewriteStyle,
  running,
  progress,
  error,
  onSelectViral,
  onSelectSource,
  onViralChange,
  onSourceChange,
  onOutputDirChange,
  onRewriteStyleChange,
  onRun,
}) {
  const activeStepIndex = Math.max(0, steps.indexOf(progress))

  return (
    <section className="view">
      <header className="view-header">
        <div>
          <h1>复刻任务</h1>
          <p>选择输入视频、输出位置和文案风格。</p>
        </div>
        <button className="primary-button" onClick={onRun} disabled={running || !viralVideo || !sourceVideo}>
          {running ? '执行中' : '开始执行'}
        </button>
      </header>

      <div className="form-grid">
        <FileField label="爆款视频" value={viralVideo} onChange={onViralChange} onSelect={onSelectViral} />
        <FileField label="源电影" value={sourceVideo} onChange={onSourceChange} onSelect={onSelectSource} />

        <label className="field">
          <span>输出目录</span>
          <input value={outputDir} onChange={(e) => onOutputDirChange(e.target.value)} />
        </label>

        <label className="field">
          <span>改写风格</span>
          <textarea value={rewriteStyle} onChange={(e) => onRewriteStyleChange(e.target.value)} placeholder="可选" />
        </label>
      </div>

      <section className="progress-panel">
        <div className="section-title">执行进度</div>
        <div className="steps">
          {steps.map((step, index) => (
            <div
              className={
                progress === '完成' || (running && index <= activeStepIndex)
                  ? 'step active'
                  : 'step'
              }
              key={step}
            >
              {step}
            </div>
          ))}
        </div>
      </section>

      {error && <div className="alert error">{error}</div>}
      {progress && !error && <div className="alert neutral">{progress}</div>}
    </section>
  )
}

function FileField({ label, value, onChange, onSelect }) {
  const inputId = useId()

  return (
    <div className="field">
      <label htmlFor={inputId}>{label}</label>
      <div className="file-row">
        <input id={inputId} value={value} onChange={(e) => onChange(e.target.value)} />
        <button className="secondary-button" type="button" onClick={onSelect}>
          选择
        </button>
      </div>
    </div>
  )
}

function SettingsView({ settings, status, error, onTopLevelChange, onNestedChange, onSave }) {
  return (
    <section className="view">
      <header className="view-header">
        <div>
          <h1>设置</h1>
          <p>配置转录、改写和语音生成服务。</p>
        </div>
        <button className="primary-button" onClick={onSave}>
          保存设置
        </button>
      </header>

      <div className="settings-sections">
        <section className="settings-section">
          <h2>Whisper</h2>
          <label className="field">
            <span>模型路径</span>
            <input
              value={settings.whisper_model || ''}
              onChange={(e) => onTopLevelChange('whisper_model', e.target.value)}
            />
          </label>
          <label className="field">
            <span>VAD 模型路径</span>
            <input
              value={settings.vad_model || ''}
              onChange={(e) => onTopLevelChange('vad_model', e.target.value)}
            />
          </label>
          <div className="form-grid compact">
            <label className="field">
              <span>VAD 阈值</span>
              <input
                type="number"
                step="0.01"
                value={settings.vad?.threshold ?? 0.25}
                onChange={(e) => onNestedChange('vad', 'threshold', Number(e.target.value))}
              />
            </label>
            <label className="field">
              <span>最短语音 ms</span>
              <input
                type="number"
                value={settings.vad?.min_speech_ms ?? 10}
                onChange={(e) => onNestedChange('vad', 'min_speech_ms', Number(e.target.value))}
              />
            </label>
            <label className="field">
              <span>最短静音 ms</span>
              <input
                type="number"
                value={settings.vad?.min_silence_ms ?? 50}
                onChange={(e) => onNestedChange('vad', 'min_silence_ms', Number(e.target.value))}
              />
            </label>
            <label className="field">
              <span>Demucs 模型</span>
              <input
                value={settings.demucs_model || 'htdemucs'}
                onChange={(e) => onTopLevelChange('demucs_model', e.target.value)}
              />
            </label>
            <label className="field">
              <span>主讲人阈值</span>
              <input
                type="number"
                step="0.01"
                value={settings.speaker?.similarity_threshold ?? 0.82}
                onChange={(e) => onNestedChange('speaker', 'similarity_threshold', Number(e.target.value))}
              />
            </label>
            <label className="field">
              <span>ASR 语言</span>
              <input
                value={settings.asr?.language || 'en'}
                onChange={(e) => onNestedChange('asr', 'language', e.target.value)}
              />
            </label>
            <label className="field">
              <span>行级主讲人阈值</span>
              <input
                type="number"
                step="0.01"
                value={settings.asr?.speaker_threshold ?? 0.3}
                onChange={(e) => onNestedChange('asr', 'speaker_threshold', Number(e.target.value))}
              />
            </label>
            <label className="field">
              <span>ASR 最大字符</span>
              <input
                type="number"
                value={settings.asr?.max_len ?? 50}
                onChange={(e) => onNestedChange('asr', 'max_len', Number(e.target.value))}
              />
            </label>
            <label className="field">
              <span>时间偏移 ms</span>
              <input
                type="number"
                value={settings.asr?.timing_offset_ms ?? 820}
                onChange={(e) => onNestedChange('asr', 'timing_offset_ms', Number(e.target.value))}
              />
            </label>
            <label className="field wide">
              <span>Pyannote 模型</span>
              <input
                value={settings.speaker?.pyannote_model || ''}
                onChange={(e) => onNestedChange('speaker', 'pyannote_model', e.target.value)}
              />
            </label>
            <label className="field wide">
              <span>HF Token</span>
              <input
                type="password"
                value={settings.speaker?.hf_token || ''}
                onChange={(e) => onNestedChange('speaker', 'hf_token', e.target.value)}
              />
            </label>
            <label className="field wide">
              <span>ASR Prompt</span>
              <input
                value={settings.asr?.prompt || ''}
                onChange={(e) => onNestedChange('asr', 'prompt', e.target.value)}
              />
            </label>
          </div>
          <label className="checkbox-field">
            <input
              type="checkbox"
              checked={Boolean(settings.speaker?.enabled)}
              onChange={(e) => onNestedChange('speaker', 'enabled', e.target.checked)}
            />
            <span>主讲人筛选</span>
          </label>
          <label className="checkbox-field">
            <input
              type="checkbox"
              checked={Boolean(settings.asr?.split_on_word)}
              onChange={(e) => onNestedChange('asr', 'split_on_word', e.target.checked)}
            />
            <span>ASR 按词切分</span>
          </label>
          <label className="field wide">
            <span>默认改写风格</span>
            <textarea
              value={settings.rewrite_style || ''}
              onChange={(e) => onTopLevelChange('rewrite_style', e.target.value)}
            />
          </label>
        </section>

        <section className="settings-section">
          <h2>LLM</h2>
          <div className="form-grid compact">
            <label className="field">
              <span>API Key</span>
              <input
                type="password"
                value={settings.llm?.api_key || ''}
                onChange={(e) => onNestedChange('llm', 'api_key', e.target.value)}
              />
            </label>
            <label className="field">
              <span>模型</span>
              <input
                value={settings.llm?.model || ''}
                onChange={(e) => onNestedChange('llm', 'model', e.target.value)}
              />
            </label>
            <label className="field wide">
              <span>Base URL</span>
              <input
                value={settings.llm?.base_url || ''}
                onChange={(e) => onNestedChange('llm', 'base_url', e.target.value)}
              />
            </label>
          </div>
        </section>

        <section className="settings-section">
          <h2>TTS</h2>
          <div className="form-grid compact">
            <label className="field">
              <span>服务</span>
              <select
                value={settings.tts_provider || 'minimax'}
                onChange={(e) => onTopLevelChange('tts_provider', e.target.value)}
              >
                <option value="minimax">Minimax</option>
                <option value="voxcpm">VoxCPM</option>
              </select>
            </label>
            <label className="field wide">
              <span>VoxCPM Base URL</span>
              <input
                value={settings.voxcpm?.base_url || ''}
                onChange={(e) => onNestedChange('voxcpm', 'base_url', e.target.value)}
                placeholder="http://127.0.0.1:8808"
              />
            </label>
            <label className="field">
              <span>VoxCPM API</span>
              <select
                value={settings.voxcpm?.api_type || 'synthesize'}
                onChange={(e) => onNestedChange('voxcpm', 'api_type', e.target.value)}
              >
                <option value="synthesize">/synthesize</option>
                <option value="gradio">Gradio</option>
              </select>
            </label>
            <label className="field">
              <span>VoxCPM 声音</span>
              <select
                value={settings.voxcpm?.voice || 'Natasha'}
                onChange={(e) => onNestedChange('voxcpm', 'voice', e.target.value)}
              >
                <option value="Natasha">Natasha 女声</option>
                <option value="Alex">Alex 男声</option>
              </select>
            </label>
            <label className="field wide">
              <span>Natasha 参考音频</span>
              <input
                value={settings.voxcpm?.voice_refs?.Natasha || ''}
                onChange={(e) => onNestedChange('voxcpm', 'voice_refs', {
                  ...(settings.voxcpm?.voice_refs || {}),
                  Natasha: e.target.value,
                })}
                placeholder="/Users/.../Natasha.mp3"
              />
            </label>
            <label className="field wide">
              <span>Alex 参考音频</span>
              <input
                value={settings.voxcpm?.voice_refs?.Alex || ''}
                onChange={(e) => onNestedChange('voxcpm', 'voice_refs', {
                  ...(settings.voxcpm?.voice_refs || {}),
                  Alex: e.target.value,
                })}
                placeholder="/Users/.../Alex.mp3"
              />
            </label>
            <label className="field">
              <span>Seed</span>
              <input
                type="number"
                value={settings.voxcpm?.seed ?? 42}
                onChange={(e) => onNestedChange('voxcpm', 'seed', Number(e.target.value))}
              />
            </label>
            <label className="field">
              <span>CFG</span>
              <input
                type="number"
                step="0.1"
                value={settings.voxcpm?.cfg_value ?? 2.0}
                onChange={(e) => onNestedChange('voxcpm', 'cfg_value', Number(e.target.value))}
              />
            </label>
            <label className="field">
              <span>Steps</span>
              <input
                type="number"
                value={settings.voxcpm?.inference_timesteps ?? 10}
                onChange={(e) => onNestedChange('voxcpm', 'inference_timesteps', Number(e.target.value))}
              />
            </label>
            <label className="field">
              <span>Timeout 秒</span>
              <input
                type="number"
                value={settings.voxcpm?.timeout ?? 900}
                onChange={(e) => onNestedChange('voxcpm', 'timeout', Number(e.target.value))}
              />
            </label>
            <label className="field wide">
              <span>VoxCPM 控制词</span>
              <input
                value={settings.voxcpm?.control || ''}
                onChange={(e) => onNestedChange('voxcpm', 'control', e.target.value)}
                placeholder="可选，例如 calm, fast-paced"
              />
            </label>
            <label className="checkbox-field">
              <input
                type="checkbox"
                checked={!!settings.voxcpm?.do_normalize}
                onChange={(e) => onNestedChange('voxcpm', 'do_normalize', e.target.checked)}
              />
              <span>VoxCPM Normalize</span>
            </label>
            <label className="checkbox-field">
              <input
                type="checkbox"
                checked={!!settings.voxcpm?.denoise}
                onChange={(e) => onNestedChange('voxcpm', 'denoise', e.target.checked)}
              />
              <span>VoxCPM Denoise</span>
            </label>
          </div>
        </section>

        <section className="settings-section">
          <h2>Minimax</h2>
          <div className="form-grid compact">
            <label className="field">
              <span>API Key</span>
              <input
                type="password"
                value={settings.minimax?.api_key || ''}
                onChange={(e) => onNestedChange('minimax', 'api_key', e.target.value)}
              />
            </label>
            <label className="field">
              <span>Group ID</span>
              <input
                value={settings.minimax?.group_id || ''}
                onChange={(e) => onNestedChange('minimax', 'group_id', e.target.value)}
              />
            </label>
            <label className="field">
              <span>Voice ID</span>
              <input
                value={settings.minimax?.voice_id || ''}
                onChange={(e) => onNestedChange('minimax', 'voice_id', e.target.value)}
              />
            </label>
            <label className="field">
              <span>Base URL</span>
              <input
                value={settings.minimax?.base_url || ''}
                onChange={(e) => onNestedChange('minimax', 'base_url', e.target.value)}
              />
            </label>
          </div>
        </section>
      </div>

      {error && <div className="alert error">{error}</div>}
      {status && !error && <div className="alert neutral">{status}</div>}
    </section>
  )
}
