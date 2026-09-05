/**
 * The whole application: pick a language, pick a dish, fill in the form the server generated.
 *
 * The dish list is fetched, never declared, and so is the language list. A dish added to the
 * backend as two data files, or a language added as one, appears here on the next load with a
 * working, fully constrained, fully translated form. That is the property the task asks to be
 * demonstrated, and it is the reason this file contains no dish names and no field names.
 */

import { useCallback, useEffect, useMemo, useState } from 'react'

import type { DishSummary } from './api'
import { DishBrowser } from './DishBrowser'
import { DishForm } from './DishForm'
import { LanguageSwitcher } from './LanguageSwitcher'
import { ThemeToggle } from './ThemeToggle'
import { initialLanguage, rememberLanguage, translator } from './i18n'
import type { Language } from './i18n'
import { applyTheme, initialTheme, rememberTheme } from './theme'
import type { Theme } from './theme'
import { UiContext } from './ui-context'

export function App() {
  const [language, setLanguage] = useState<Language>(initialLanguage)
  const [theme, setTheme] = useState<Theme>(initialTheme)
  const [selected, setSelected] = useState<string | null>(null)

  const t = useMemo(() => translator(language), [language])
  const ui = useMemo(() => ({ language, t }), [language, t])

  useEffect(() => {
    document.documentElement.lang = language
  }, [language])

  useEffect(() => {
    applyTheme(theme)
  }, [theme])

  // The browser owns fetching; this only keeps a valid dish selected as results change, so a
  // filter that excludes the current dish moves the form to the first result rather than
  // leaving a form on screen for something no longer in the list.
  const handleDishes = useCallback((dishes: DishSummary[]) => {
    setSelected((current) => {
      if (current && dishes.some((dish) => dish.slug === current)) return current
      return dishes[0]?.slug ?? null
    })
  }, [])

  const changeLanguage = useCallback((next: Language) => {
    setLanguage(next)
    rememberLanguage(next)
  }, [])

  const changeTheme = useCallback((next: Theme) => {
    setTheme(next)
    rememberTheme(next)
  }, [])

  return (
    <UiContext.Provider value={ui}>
      <div className="shell">
        <header className="masthead">
          <div className="masthead__inner">
            <a className="brand" href="/">
              <span className="brand__mark" aria-hidden="true" />
              <span className="brand__name">Ordes</span>
              <span className="brand__sub">SHACL-driven ordering</span>
            </a>
            <div className="masthead__controls">
              <ThemeToggle current={theme} onChange={changeTheme} />
              <LanguageSwitcher current={language} onChange={changeLanguage} />
            </div>
          </div>
        </header>

        <main className="main">
          <section className="hero">
            <h1>{t('appTitle')}</h1>
            <p>{t('appLead')}</p>
          </section>

          <div className="layout">
            <DishBrowser selected={selected} onSelect={setSelected} onDishes={handleDishes} />
            {selected && <DishForm key={selected} slug={selected} />}
          </div>
        </main>

        <footer className="footer">
          <p>
            Forms and validation generated from JSON-LD and SHACL. Swiss Data Science Center task
            prototype.
          </p>
        </footer>
      </div>
    </UiContext.Provider>
  )
}
