/**
 * The language switcher.
 *
 * Languages are named in themselves - Deutsch, Rumantsch - because a switcher labelled in a
 * language you cannot read is not much of a switcher. The short codes are for the compact
 * layout; the full endonym is the accessible name.
 */

import { LANGUAGES, LANGUAGE_NAMES, LANGUAGE_SHORT } from './i18n'
import type { Language } from './i18n'
import { useUi } from './ui-context'

interface Props {
  current: Language
  onChange: (language: Language) => void
}

export function LanguageSwitcher({ current, onChange }: Props) {
  const { t } = useUi()

  return (
    <div className="langs" role="group" aria-label={t('languageLabel')}>
      {LANGUAGES.map((language) => (
        <button
          key={language}
          type="button"
          lang={language}
          className={`lang${language === current ? ' lang--on' : ''}`}
          aria-pressed={language === current}
          aria-label={LANGUAGE_NAMES[language]}
          title={LANGUAGE_NAMES[language]}
          onClick={() => onChange(language)}
        >
          {LANGUAGE_SHORT[language]}
        </button>
      ))}
    </div>
  )
}
