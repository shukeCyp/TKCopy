import { Save } from 'lucide-react'
import {
  Button,
  Checkbox,
  Field,
  NumberInput,
  Panel,
  Section,
  Select,
  StatusStrip,
  TextInput,
  Toolbar,
} from '../components/ui/index.jsx'

export function SettingsView({ settings, status, error, onTopLevelChange, onNestedChange, onSave }) {
  return (
    <div className="page-frame settings-view">
      <Toolbar align="end">
        <Button icon={Save} onClick={onSave}>
          保存设置
        </Button>
      </Toolbar>

      <Panel>
        <div className="settings-sections">
          <Section className="settings-card" title="阶段1 TTS分离">
            <div className="form-grid compact">
              <Field label="Whisper 模型" wide>
                <TextInput
                  value={settings.whisper_model || ''}
                  onChange={(value) => onTopLevelChange('whisper_model', value)}
                />
              </Field>
              <Field label="VAD 模型" wide>
                <TextInput
                  value={settings.vad_model || ''}
                  onChange={(value) => onTopLevelChange('vad_model', value)}
                />
              </Field>
              <NumberInput
                label="VAD 阈值"
                step="0.01"
                value={settings.vad?.threshold ?? 0.25}
                onChange={(value) => onNestedChange('vad', 'threshold', value)}
              />
              <NumberInput
                label="最短语音 ms"
                value={settings.vad?.min_speech_ms ?? 10}
                onChange={(value) => onNestedChange('vad', 'min_speech_ms', value)}
              />
              <NumberInput
                label="最短静音 ms"
                value={settings.vad?.min_silence_ms ?? 50}
                onChange={(value) => onNestedChange('vad', 'min_silence_ms', value)}
              />
              <NumberInput
                label="时间偏移 ms"
                value={settings.asr?.timing_offset_ms ?? 820}
                onChange={(value) => onNestedChange('asr', 'timing_offset_ms', value)}
              />
              <Field label="ASR 语言">
                <TextInput
                  value={settings.asr?.language || 'en'}
                  onChange={(value) => onNestedChange('asr', 'language', value)}
                />
              </Field>
              <NumberInput
                label="ASR 最大字符"
                value={settings.asr?.max_len ?? 50}
                onChange={(value) => onNestedChange('asr', 'max_len', value)}
              />
              <Checkbox
                label="主讲人筛选"
                checked={Boolean(settings.speaker?.enabled)}
                onChange={(value) => onNestedChange('speaker', 'enabled', value)}
              />
              <Checkbox
                label="ASR 按词切分"
                checked={Boolean(settings.asr?.split_on_word)}
                onChange={(value) => onNestedChange('asr', 'split_on_word', value)}
              />
            </div>
          </Section>

          <Section className="settings-card" title="阶段2 解说规划">
            <div className="form-grid compact">
              <Field label="API Key">
                <TextInput
                  type="password"
                  value={settings.llm?.api_key || ''}
                  onChange={(value) => onNestedChange('llm', 'api_key', value)}
                />
              </Field>
              <Field label="模型">
                <TextInput
                  value={settings.llm?.model || ''}
                  onChange={(value) => onNestedChange('llm', 'model', value)}
                />
              </Field>
              <Field label="Base URL" wide>
                <TextInput
                  value={settings.llm?.base_url || ''}
                  onChange={(value) => onNestedChange('llm', 'base_url', value)}
                />
              </Field>
            </div>
          </Section>

          <Section className="settings-card" title="阶段3 画面匹配">
            <div className="form-grid compact">
              <Field label="匹配引擎">
                <Select
                  value={settings.frame_match?.engine || 'vmf'}
                  onChange={(value) => onNestedChange('frame_match', 'engine', value)}
                  options={[
                    { value: 'vmf', label: 'VMF + 精匹配' },
                    { value: 'internal', label: '内部匹配' },
                  ]}
                />
              </Field>
              <Field label="VMF 路径" wide>
                <TextInput
                  value={settings.frame_match?.vmf_bin || ''}
                  onChange={(value) => onNestedChange('frame_match', 'vmf_bin', value)}
                />
              </Field>
              <NumberInput
                label="粗匹配 FPS"
                step="0.5"
                value={settings.frame_match?.fps ?? 3}
                onChange={(value) => onNestedChange('frame_match', 'fps', value)}
              />
              <NumberInput
                label="Batch Size"
                value={settings.frame_match?.batch_size ?? 64}
                onChange={(value) => onNestedChange('frame_match', 'batch_size', value)}
              />
              <NumberInput
                label="Inflight"
                value={settings.frame_match?.inflight ?? 1}
                onChange={(value) => onNestedChange('frame_match', 'inflight', value)}
              />
              <NumberInput
                label="Padding 秒"
                value={settings.frame_match?.padding_seconds ?? 90}
                onChange={(value) => onNestedChange('frame_match', 'padding_seconds', value)}
              />
            </div>
          </Section>

          <Section className="settings-card" title="阶段4 语音生成">
            <div className="form-grid compact">
              <Field label="云端链接" wide>
                <TextInput
                  value={settings.voxcpm?.base_url || ''}
                  onChange={(value) => onNestedChange('voxcpm', 'base_url', value)}
                />
              </Field>
              <Field label="API">
                <Select
                  value={settings.voxcpm?.api_type || 'gradio'}
                  onChange={(value) => onNestedChange('voxcpm', 'api_type', value)}
                  options={[
                    { value: 'gradio', label: 'Gradio' },
                    { value: 'synthesize', label: '/synthesize' },
                  ]}
                />
              </Field>
              <Field label="默认声音">
                <Select
                  value={settings.voxcpm?.voice || 'Natasha'}
                  onChange={(value) => onNestedChange('voxcpm', 'voice', value)}
                  options={[
                    { value: 'Natasha', label: 'Natasha' },
                    { value: 'Alex', label: 'Alex' },
                  ]}
                />
              </Field>
              <VoiceRefField settings={settings} voice="Natasha" onNestedChange={onNestedChange} />
              <VoiceRefField settings={settings} voice="Alex" onNestedChange={onNestedChange} />
              <NumberInput
                label="Steps"
                value={settings.voxcpm?.inference_timesteps ?? 10}
                onChange={(value) => onNestedChange('voxcpm', 'inference_timesteps', value)}
              />
              <NumberInput
                label="CFG"
                step="0.1"
                value={settings.voxcpm?.cfg_value ?? 2.0}
                onChange={(value) => onNestedChange('voxcpm', 'cfg_value', value)}
              />
              <NumberInput
                label="Seed"
                value={settings.voxcpm?.seed ?? 42}
                onChange={(value) => onNestedChange('voxcpm', 'seed', value)}
              />
              <NumberInput
                label="Timeout 秒"
                value={settings.voxcpm?.timeout ?? 900}
                onChange={(value) => onNestedChange('voxcpm', 'timeout', value)}
              />
              <Field label="控制词" wide>
                <TextInput
                  value={settings.voxcpm?.control || ''}
                  onChange={(value) => onNestedChange('voxcpm', 'control', value)}
                />
              </Field>
              <Checkbox
                label="Normalize"
                checked={Boolean(settings.voxcpm?.do_normalize)}
                onChange={(value) => onNestedChange('voxcpm', 'do_normalize', value)}
              />
              <Checkbox
                label="Denoise"
                checked={Boolean(settings.voxcpm?.denoise)}
                onChange={(value) => onNestedChange('voxcpm', 'denoise', value)}
              />
            </div>
          </Section>

          <Section className="settings-card" title="阶段5 剪映草稿">
            <Field label="草稿目录" wide>
              <TextInput
                value={settings.jianying?.draft_folder || ''}
                onChange={(value) => onNestedChange('jianying', 'draft_folder', value)}
              />
            </Field>
          </Section>
        </div>
      </Panel>

      {error && <StatusStrip type="danger">{error}</StatusStrip>}
      {status && !error && <StatusStrip>{status}</StatusStrip>}
    </div>
  )
}

function VoiceRefField({ settings, voice, onNestedChange }) {
  return (
    <Field label={`${voice} 参考音频`} wide>
      <TextInput
        value={settings.voxcpm?.voice_refs?.[voice] || ''}
        onChange={(value) =>
          onNestedChange('voxcpm', 'voice_refs', {
            ...(settings.voxcpm?.voice_refs || {}),
            [voice]: value,
          })
        }
      />
    </Field>
  )
}
