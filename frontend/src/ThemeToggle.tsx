/**
 * The light / dark / system switch.
 *
 * A three-way segmented control rather than a two-state toggle, so "follow my system" stays
 * reachable after someone has picked one. Same shape as the language switcher beside it.
 */

import { THEMES } from './theme'
import type { Theme } from './theme'
import { useUi } from './ui-context'

const ICONS: Record<Theme, string> = {
  system: '◐',
  light: '☀',
  dark: '☾',
}

interface Props {
  current: Theme
  onChange: (theme: Theme) => void
}

export function ThemeToggle({ current, onChange }: Props) {
  const { t } = useUi()

  return (
    <div className="themes" role="group" aria-label={t('themeLabel')}>
      {THEMES.map((theme) => (
        <button
          key={theme}
          type="button"
          className={`theme${theme === current ? ' theme--on' : ''}`}
          aria-pressed={theme === current}
          // The glyph is decorative; the accessible name is the word.
          aria-label={t(theme === 'system' ? 'themeSystem' : theme === 'light' ? 'themeLight' : 'themeDark')}
          title={t(theme === 'system' ? 'themeSystem' : theme === 'light' ? 'themeLight' : 'themeDark')}
          onClick={() => onChange(theme)}
        >
          <span aria-hidden="true">{ICONS[theme]}</span>
        </button>
      ))}
    </div>
  )
}
