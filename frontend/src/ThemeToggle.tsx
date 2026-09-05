/**
 * The light / dark / system switch.
 *
 * A three-way segmented control rather than a two-state toggle, so "follow my system" stays
 * reachable after someone has picked one. Same shape as the language switcher beside it.
 */

import { ContrastIcon, MoonIcon, SunIcon } from './Icon'
import type { IconComponent } from './Icon'
import { THEMES } from './theme'
import type { Theme } from './theme'
import { useUi } from './ui-context'

const ICONS: Record<Theme, IconComponent> = {
  system: ContrastIcon,
  light: SunIcon,
  dark: MoonIcon,
}

const LABEL_KEYS = {
  system: 'themeSystem',
  light: 'themeLight',
  dark: 'themeDark',
} as const

interface Props {
  current: Theme
  onChange: (theme: Theme) => void
}

export function ThemeToggle({ current, onChange }: Props) {
  const { t } = useUi()

  return (
    <div className="themes" role="group" aria-label={t('themeLabel')}>
      {THEMES.map((theme) => {
        const Glyph = ICONS[theme]
        const name = t(LABEL_KEYS[theme])
        return (
          <button
            key={theme}
            type="button"
            className={`theme${theme === current ? ' theme--on' : ''}`}
            aria-pressed={theme === current}
            // The icon is decorative; the accessible name is the word.
            aria-label={name}
            title={name}
            onClick={() => onChange(theme)}
          >
            <Glyph />
          </button>
        )
      })}
    </div>
  )
}
