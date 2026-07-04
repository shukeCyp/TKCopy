import { useEffect, useState } from 'react'
import { AppShell } from './components/layout/AppShell.jsx'
import { SingleTaskView } from './views/SingleTaskView.jsx'
import { BatchView } from './views/BatchView.jsx'
import { SettingsView } from './views/SettingsView.jsx'
import { StyleLibraryView } from './views/StyleLibraryView.jsx'
import { LogsView } from './views/LogsView.jsx'

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

const DEFAULT_STYLE_ID = 'default'
const DEFAULT_REWRITE_STYLES = [
  {
    id: DEFAULT_STYLE_ID,
    name: '默认',
    prompt: DEFAULT_RECAP_STYLE_PROMPT,
  },
]

const DEFAULT_SETTINGS = {
  whisper_model: 'base',
  vad_model: '',
  vad: { threshold: 0.25, min_speech_ms: 10, min_silence_ms: 50 },
  demucs_model: 'htdemucs',
  frame_match: {
    engine: 'vmf',
    vmf_bin: '/Users/chaiyapeng/Documents/autocopy/.venv/bin/vmf',
    fps: 3.0,
    model: 'dinov2_vits14',
    device: 'cpu',
    batch_size: 64,
    inflight: 1,
    padding_seconds: 90.0,
  },
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
  rewrite_styles: DEFAULT_REWRITE_STYLES,
  selected_rewrite_style_id: DEFAULT_STYLE_ID,
  llm: { api_key: '', model: 'gemini-3.5-flash', base_url: 'https://yunwu.ai' },
  tts_provider: 'voxcpm',
  minimax: {
    api_key: '',
    group_id: '',
    voice_id: '',
    base_url: 'https://api.minimax.chat',
    speed: 1.2,
  },
  voxcpm: {
    base_url: 'https://swc0syb3hwdavikr-8808.container.x-gpu.com/',
    api_type: 'gradio',
    voice: 'Natasha',
    voice_refs: {
      Natasha: '/Users/chaiyapeng/Documents/VoxCPM/reference_audio/Natasha.mp3',
      Alex: '/Users/chaiyapeng/Documents/VoxCPM/reference_audio/Alex.mp3',
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
  jianying: {
    draft_folder: '/Users/chaiyapeng/Downloads/草稿/JianyingPro Drafts',
  },
}

const fallbackApi = {
  get_settings: async () => DEFAULT_SETTINGS,
  update_settings: async () => ({ ok: true }),
  run_workflow: async () => ({ ok: true, message: 'mock: workflow started' }),
  run_batch_workflow: async () => ({ ok: true, message: 'mock: batch workflow started' }),
  scan_batch_cases: async () => ({ ok: true, cases: [] }),
  select_file: async () => ({ path: '/mock/path/video.mp4' }),
  select_directory: async () => ({ path: '/mock/path' }),
}

const requiredApiMethods = [
  'get_settings',
  'update_settings',
  'run_workflow',
  'run_batch_workflow',
  'scan_batch_cases',
  'select_file',
  'select_directory',
]

const workflowSteps = [
  { key: 'TTS分离', label: 'TTS分离' },
  { key: '解说规划', label: '解说规划' },
  { key: '镜头匹配', label: 'VMF粗匹配 + 逐帧精匹配' },
  { key: '音频生成', label: 'VoxCPM音频生成' },
  { key: '导出剪映', label: '导出剪映草稿' },
]

function getApi() {
  const pywebviewApi = window.pywebview?.api

  if (!pywebviewApi) return fallbackApi

  return requiredApiMethods.every((method) => typeof pywebviewApi[method] === 'function')
    ? pywebviewApi
    : fallbackApi
}

function normalizeRewriteStyles(styles, fallbackPrompt = DEFAULT_RECAP_STYLE_PROMPT) {
  const sourceStyles = Array.isArray(styles) ? styles : []
  const normalized = sourceStyles.map((style, index) => {
    const id = String(style?.id || (index === 0 ? DEFAULT_STYLE_ID : `style_${index + 1}`)).trim()
    const name = String(style?.name || (id === DEFAULT_STYLE_ID ? '默认' : `风格 ${index + 1}`)).trim()
    return {
      id,
      name: name || (id === DEFAULT_STYLE_ID ? '默认' : `风格 ${index + 1}`),
      prompt: String(style?.prompt || ''),
    }
  })

  if (normalized.length === 0) {
    return [{ ...DEFAULT_REWRITE_STYLES[0], prompt: fallbackPrompt || DEFAULT_RECAP_STYLE_PROMPT }]
  }

  if (!normalized.some((style) => style.id === DEFAULT_STYLE_ID)) {
    normalized.unshift({
      ...DEFAULT_REWRITE_STYLES[0],
      prompt: fallbackPrompt || DEFAULT_RECAP_STYLE_PROMPT,
    })
  }

  return normalized
}

function getSelectedRewriteStyle(styles, selectedId) {
  const normalized = normalizeRewriteStyles(styles)
  return normalized.find((style) => style.id === selectedId) || normalized[0] || DEFAULT_REWRITE_STYLES[0]
}

function createRewriteStyleId(styles) {
  const existingIds = new Set((styles || []).map((style) => style.id))
  let index = (styles || []).length + 1
  let id = `style_${index}`
  while (existingIds.has(id)) {
    index += 1
    id = `style_${index}`
  }
  return id
}

function mergeSettings(settings) {
  const legacyRewriteStyle = settings?.rewrite_style || DEFAULT_SETTINGS.rewrite_style
  const rewriteStyles = normalizeRewriteStyles(settings?.rewrite_styles, legacyRewriteStyle)
  const selectedRewriteStyleId = rewriteStyles.some((style) => style.id === settings?.selected_rewrite_style_id)
    ? settings.selected_rewrite_style_id
    : rewriteStyles[0].id
  const activeStyle = getSelectedRewriteStyle(rewriteStyles, selectedRewriteStyleId)

  return {
    ...DEFAULT_SETTINGS,
    ...settings,
    vad: { ...DEFAULT_SETTINGS.vad, ...(settings?.vad || {}) },
    frame_match: { ...DEFAULT_SETTINGS.frame_match, ...(settings?.frame_match || {}) },
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
    jianying: { ...DEFAULT_SETTINGS.jianying, ...(settings?.jianying || {}) },
    rewrite_style: activeStyle.prompt || legacyRewriteStyle,
    rewrite_styles: rewriteStyles,
    selected_rewrite_style_id: selectedRewriteStyleId,
  }
}

function logLine(title, detail = '') {
  return {
    id: `${Date.now()}-${Math.random()}`,
    time: new Date().toLocaleTimeString(),
    title,
    detail,
  }
}

function progressText(detail) {
  if (!detail) return ''
  if (typeof detail === 'string') return detail
  if (detail.event === 'case_started') return `批量 ${detail.index}/${detail.total}: ${detail.case_id} 开始`
  if (detail.event === 'case_step') return `批量 ${detail.index}/${detail.total}: ${detail.case_id} - ${detail.step}`
  if (detail.event === 'case_completed') return `批量 ${detail.index}/${detail.total}: ${detail.case_id} 完成`
  if (detail.event === 'case_failed') return `批量 ${detail.index}/${detail.total}: ${detail.case_id} 失败`
  if (detail.event === 'batch_finished') return '批量完成'
  return detail.step || detail.event || JSON.stringify(detail)
}

export default function App() {
  const [activeView, setActiveView] = useState('single')
  const [settings, setSettings] = useState(DEFAULT_SETTINGS)
  const [viralVideo, setViralVideo] = useState('')
  const [sourceVideo, setSourceVideo] = useState('')
  const [outputDir, setOutputDir] = useState('output')
  const [rewriteStyle, setRewriteStyle] = useState('')
  const [selectedStyleId, setSelectedStyleId] = useState(DEFAULT_STYLE_ID)
  const [batchRootDir, setBatchRootDir] = useState('/Users/chaiyapeng/Downloads/对标')
  const [batchOutputDir, setBatchOutputDir] = useState('output')
  const [voiceSplitCount, setVoiceSplitCount] = useState(5)
  const [batchCases, setBatchCases] = useState([])
  const [progress, setProgress] = useState('')
  const [running, setRunning] = useState(false)
  const [error, setError] = useState('')
  const [settingsStatus, setSettingsStatus] = useState('')
  const [logs, setLogs] = useState([])
  const [lastResult, setLastResult] = useState(null)

  const appendLog = (title, detail = '') => {
    setLogs((current) => [logLine(title, detail), ...current].slice(0, 200))
  }

  useEffect(() => {
    const loadSettings = () => {
      getApi().get_settings()
        .then((loadedSettings) => {
          const nextSettings = mergeSettings(loadedSettings)
          const activeStyle = getSelectedRewriteStyle(
            nextSettings.rewrite_styles,
            nextSettings.selected_rewrite_style_id,
          )
          setSettings(nextSettings)
          setSelectedStyleId(activeStyle.id)
          setRewriteStyle(activeStyle.prompt || nextSettings.rewrite_style || '')
        })
        .catch((e) => setError('加载配置失败: ' + e.message))
    }

    const onProgress = (e) => {
      const text = progressText(e.detail)
      setProgress(text)
      appendLog('步骤', text)
    }
    const onBatchProgress = (e) => {
      const text = progressText(e.detail)
      setProgress(text)
      appendLog('批量', text)
    }
    const onComplete = (e) => {
      setRunning(false)
      setProgress('完成')
      setLastResult(e.detail || null)
      appendLog('完成', resultSummary(e.detail))
    }
    const onError = (e) => {
      const message = typeof e.detail === 'string' ? e.detail : JSON.stringify(e.detail)
      setRunning(false)
      setError(message)
      appendLog('错误', message)
    }

    const onPywebviewReady = () => {
      loadSettings()
    }

    loadSettings()
    window.addEventListener('progress', onProgress)
    window.addEventListener('batch_progress', onBatchProgress)
    window.addEventListener('complete', onComplete)
    window.addEventListener('error', onError)
    window.addEventListener('pywebviewready', onPywebviewReady)

    return () => {
      window.removeEventListener('progress', onProgress)
      window.removeEventListener('batch_progress', onBatchProgress)
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

  const selectDirectory = async (setter) => {
    try {
      const result = await getApi().select_directory()
      if (result.path) setter(result.path)
    } catch (e) {
      setError('选择目录失败: ' + e.message)
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
    appendLog('单集任务', `${viralVideo} -> ${sourceVideo}`)

    try {
      await getApi().run_workflow({
        viral_video: viralVideo,
        source_video: sourceVideo,
        output_dir: outputDir,
        rewrite_style: rewriteStyle,
        target_language: 'English',
      })
    } catch (e) {
      setRunning(false)
      setError('启动失败: ' + e.message)
    }
  }

  const scanBatch = async () => {
    if (!batchRootDir) {
      setError('请选择批量目录')
      return
    }

    setError('')
    setProgress('扫描批量目录...')
    appendLog('扫描批量目录', batchRootDir)
    try {
      const result = await getApi().scan_batch_cases({
        root_dir: batchRootDir,
        voice_split_count: voiceSplitCount,
      })
      setBatchCases(result.cases || [])
      appendLog('扫描完成', `${result.cases?.length || 0} 个目录`)
    } catch (e) {
      setError('扫描失败: ' + e.message)
      appendLog('扫描失败', e.message)
    }
  }

  const runBatchWorkflow = async () => {
    const enabledCases = batchCases.filter((item) => item.enabled)
    if (!batchRootDir || enabledCases.length === 0) {
      setError('请先扫描并保留至少一个可执行案例')
      return
    }

    setError('')
    setRunning(true)
    setProgress('批量启动...')
    appendLog('批量任务', `${enabledCases.length} 个案例`)
    try {
      await getApi().run_batch_workflow({
        root_dir: batchRootDir,
        output_dir: batchOutputDir,
        rewrite_style: rewriteStyle,
        target_language: 'English',
        voice_split_count: voiceSplitCount,
        cases: enabledCases,
      })
    } catch (e) {
      setRunning(false)
      setError('批量启动失败: ' + e.message)
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

  const selectRewriteStyle = (styleId) => {
    const styles = normalizeRewriteStyles(settings.rewrite_styles, settings.rewrite_style)
    const activeStyle = getSelectedRewriteStyle(styles, styleId)

    setSelectedStyleId(activeStyle.id)
    setRewriteStyle(activeStyle.prompt || '')
    setSettings((current) => ({
      ...current,
      rewrite_style: activeStyle.prompt || '',
      rewrite_styles: styles,
      selected_rewrite_style_id: activeStyle.id,
    }))
  }

  const updateCurrentRewriteStyle = (prompt) => {
    setRewriteStyle(prompt)
    setSettings((current) => {
      const styles = normalizeRewriteStyles(current.rewrite_styles, prompt).map((style) => (
        style.id === selectedStyleId ? { ...style, prompt } : style
      ))
      return {
        ...current,
        rewrite_style: prompt,
        rewrite_styles: styles,
        selected_rewrite_style_id: selectedStyleId,
      }
    })
  }

  const saveSettings = async () => {
    setSettingsStatus('保存中...')
    setError('')

    try {
      const currentStyles = normalizeRewriteStyles(settings.rewrite_styles, rewriteStyle).map((style) => (
        style.id === selectedStyleId ? { ...style, prompt: rewriteStyle } : style
      ))
      const normalized = mergeSettings({
        ...settings,
        rewrite_style: rewriteStyle,
        rewrite_styles: currentStyles,
        selected_rewrite_style_id: selectedStyleId,
        tts_provider: 'voxcpm',
      })
      await getApi().update_settings('whisper_model', normalized.whisper_model)
      await getApi().update_settings('vad_model', normalized.vad_model)
      await getApi().update_settings('vad', normalized.vad)
      await getApi().update_settings('demucs_model', normalized.demucs_model)
      await getApi().update_settings('frame_match', normalized.frame_match)
      await getApi().update_settings('speaker', normalized.speaker)
      await getApi().update_settings('asr', normalized.asr)
      await getApi().update_settings('rewrite_style', normalized.rewrite_style)
      await getApi().update_settings('rewrite_styles', normalized.rewrite_styles)
      await getApi().update_settings('selected_rewrite_style_id', normalized.selected_rewrite_style_id)
      await getApi().update_settings('llm', normalized.llm)
      await getApi().update_settings('tts_provider', 'voxcpm')
      await getApi().update_settings('voxcpm', normalized.voxcpm)
      await getApi().update_settings('jianying', normalized.jianying)
      setSettings(normalized)
      setSelectedStyleId(normalized.selected_rewrite_style_id)
      setRewriteStyle(normalized.rewrite_style)
      setSettingsStatus('已保存')
      appendLog('设置', '已保存')
    } catch (e) {
      setSettingsStatus('')
      setError('保存配置失败: ' + e.message)
    }
  }

  const syncSettingsState = (nextSettings) => {
    const normalized = mergeSettings(nextSettings)
    setSettings(normalized)
    setSelectedStyleId(normalized.selected_rewrite_style_id)
    setRewriteStyle(normalized.rewrite_style)
  }

  const rewriteStyles = normalizeRewriteStyles(settings.rewrite_styles, rewriteStyle)
  const activeSettings = {
    ...settings,
    rewrite_style: rewriteStyle,
    rewrite_styles: rewriteStyles,
    selected_rewrite_style_id: selectedStyleId,
  }

  return (
    <AppShell
      activeView={activeView}
      running={running}
      progress={progress}
      onNavigate={setActiveView}
    >
      {activeView === 'single' && (
        <SingleTaskView
          form={{
            viral_video: viralVideo,
            source_video: sourceVideo,
            output_dir: outputDir,
          }}
          setForm={(nextForm) => {
            setViralVideo(nextForm.viral_video)
            setSourceVideo(nextForm.source_video)
            setOutputDir(nextForm.output_dir)
          }}
          settings={activeSettings}
          rewriteStyles={rewriteStyles}
          setSettings={syncSettingsState}
          running={running}
          progress={progress}
          error={error}
          lastResult={lastResult}
          onRewriteStyleChange={updateCurrentRewriteStyle}
          onStyleSelect={selectRewriteStyle}
          onPickFile={(field) => {
            const setters = { viral_video: setViralVideo, source_video: setSourceVideo }
            selectFile(setters[field])
          }}
          onPickDirectory={() => selectDirectory(setOutputDir)}
          onRun={runWorkflow}
          workflowSteps={workflowSteps}
        />
      )}

      {activeView === 'batch' && (
        <BatchView
          batchForm={{
            root_dir: batchRootDir,
            output_dir: batchOutputDir,
            natasha_count: voiceSplitCount,
          }}
          setBatchForm={(nextForm) => {
            setBatchRootDir(nextForm.root_dir)
            setBatchOutputDir(nextForm.output_dir)
            setVoiceSplitCount(nextForm.natasha_count)
          }}
          settings={activeSettings}
          setSettings={syncSettingsState}
          rewriteStyles={rewriteStyles}
          running={running}
          progress={progress}
          error={error}
          lastResult={lastResult}
          batchCases={batchCases}
          setBatchCases={setBatchCases}
          onRewriteStyleChange={updateCurrentRewriteStyle}
          onStyleSelect={selectRewriteStyle}
          onPickDirectory={(field) => {
            const setters = { batch_root_dir: setBatchRootDir, batch_output_dir: setBatchOutputDir }
            selectDirectory(setters[field])
          }}
          onScanBatch={scanBatch}
          onRunBatch={runBatchWorkflow}
          workflowSteps={workflowSteps}
        />
      )}

      {activeView === 'styles' && (
        <StyleLibraryView
          settings={activeSettings}
          setSettings={syncSettingsState}
          rewriteStyles={rewriteStyles}
          defaultStyleId={DEFAULT_STYLE_ID}
          createStyleId={() => createRewriteStyleId(rewriteStyles)}
          onSave={saveSettings}
        />
      )}

      {activeView === 'settings' && (
        <SettingsView
          settings={activeSettings}
          status={settingsStatus}
          error={error}
          onTopLevelChange={updateTopLevelSetting}
          onNestedChange={updateNestedSetting}
          onSave={saveSettings}
        />
      )}

      {activeView === 'logs' && (
        <LogsView logs={logs} progress={progress} error={error} lastResult={lastResult} />
      )}
    </AppShell>
  )
}

function resultSummary(result) {
  if (!result) return ''
  if (result.jianying_draft) return result.jianying_draft
  if (result.output_root) return result.output_root
  return JSON.stringify(result)
}
