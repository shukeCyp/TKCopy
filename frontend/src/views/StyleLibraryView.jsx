import {
  AddAction,
  Panel,
  SaveAction,
  Section,
  StatusStrip,
  StyleCard,
  Toolbar,
} from '../components/ui/index.jsx'

export function StyleLibraryView({
  settings,
  setSettings,
  rewriteStyles,
  defaultStyleId,
  createStyleId,
  onSave,
}) {
  const addStyle = () => {
    const nextStyle = {
      id: createStyleId(),
      name: `新风格 ${rewriteStyles.length + 1}`,
      prompt: settings.rewrite_style,
    }
    setSettings({
      ...settings,
      rewrite_styles: [...rewriteStyles, nextStyle],
      selected_rewrite_style_id: nextStyle.id,
      rewrite_style: nextStyle.prompt,
    })
  }

  const updateStyle = (id, patch) => {
    const nextStyles = rewriteStyles.map((style) =>
      style.id === id ? { ...style, ...patch } : style,
    )
    const activeStyle = nextStyles.find((style) => style.id === settings.selected_rewrite_style_id)
    setSettings({
      ...settings,
      rewrite_styles: nextStyles,
      rewrite_style: activeStyle?.prompt || settings.rewrite_style,
    })
  }

  const selectStyle = (style) => {
    setSettings({
      ...settings,
      selected_rewrite_style_id: style.id,
      rewrite_style: style.prompt,
    })
  }

  const deleteStyle = (id) => {
    if (id === defaultStyleId || rewriteStyles.length <= 1) return
    const nextStyles = rewriteStyles.filter((style) => style.id !== id)
    const nextActive =
      settings.selected_rewrite_style_id === id
        ? nextStyles.find((style) => style.id === defaultStyleId) || nextStyles[0]
        : nextStyles.find((style) => style.id === settings.selected_rewrite_style_id)
    setSettings({
      ...settings,
      rewrite_styles: nextStyles,
      selected_rewrite_style_id: nextActive?.id || defaultStyleId,
      rewrite_style: nextActive?.prompt || settings.rewrite_style,
    })
  }

  return (
    <div className="page-frame style-library-view">
      <Toolbar align="end">
        <AddAction onClick={addStyle} />
        <SaveAction onClick={onSave} />
      </Toolbar>

      <Panel>
        <Section title="改写风格库">
          <StyleLibrary
            styles={rewriteStyles}
            activeId={settings.selected_rewrite_style_id}
            defaultStyleId={defaultStyleId}
            onSelect={selectStyle}
            onUpdate={updateStyle}
            onDelete={deleteStyle}
          />
        </Section>
      </Panel>

      <StatusStrip>
        当前默认：{rewriteStyles.find((style) => style.id === settings.selected_rewrite_style_id)?.name || '默认'}
      </StatusStrip>
    </div>
  )
}

export function StyleLibrary({
  styles,
  activeId,
  defaultStyleId,
  onSelect,
  onUpdate,
  onDelete,
}) {
  return (
    <div className="style-grid">
      {styles.map((style) => (
        <StyleCard
          key={style.id}
          style={style}
          active={style.id === activeId}
          locked={style.id === defaultStyleId}
          onSelect={() => onSelect(style)}
          onChange={(patch) => onUpdate(style.id, patch)}
          onDelete={() => onDelete(style.id)}
        />
      ))}
    </div>
  )
}
