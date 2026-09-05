/**
 * The whole application: pick a language, pick a dish, fill in the form the server generated.
 *
 * The dish list is fetched, never declared, and so is the language list. A dish added to the
 * backend as two data files, or a language added as one, appears here on the next load with a
 * working, fully constrained, fully translated form. That is the property the task asks to be
 * demonstrated, and it is the reason this file contains no dish names and no field names.
 */

import { useCallback, useEffect, useMemo, useState } from 'react'

import { ApiError, listDishes } from './api'
import type { DishSummary } from './api'
import { DishForm } from './DishForm'
import { LanguageSwitcher } from './LanguageSwitcher'
import { initialLanguage, rememberLanguage, translator } from './i18n'
import type { Language } from './i18n'
import { UiContext } from './ui-context'

type State =
  | { kind: 'loading' }
  | { kind: 'ready'; dishes: DishSummary[] }
  | { kind: 'failed'; title: string; detail: string }

export function App() {
  const [language, setLanguage] = useState<Language>(initialLanguage)
  const [state, setState] = useState<State>({ kind: 'loading' })
  const [selected, setSelected] = useState<string | null>(null)

  const t = useMemo(() => translator(language), [language])
  const ui = useMemo(() => ({ language, t }), [language, t])

  useEffect(() => {
    document.documentElement.lang = language
  }, [language])

  useEffect(() => {
    let cancelled = false

    listDishes(language)
      .then((dishes) => {
        if (cancelled) return
        setState({ kind: 'ready', dishes })
        setSelected((current) => current ?? dishes[0]?.slug ?? null)
      })
      .catch((error: unknown) => {
        if (cancelled) return
        const problem = error instanceof ApiError ? error.problem : null
        setState({
          kind: 'failed',
          title: problem?.title ?? t('menuFailed'),
          detail: problem?.status === 0 ? t('apiUnreachable') : (problem?.detail ?? t('menuFailed')),
        })
      })

    return () => {
      cancelled = true
    }
  }, [language, t])

  const changeLanguage = useCallback((next: Language) => {
    setLanguage(next)
    rememberLanguage(next)
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
            <LanguageSwitcher current={language} onChange={changeLanguage} />
          </div>
        </header>

        <main className="main">
          <section className="hero">
            <h1>{t('appTitle')}</h1>
            <p>{t('appLead')}</p>
          </section>

          {state.kind === 'loading' && (
            <div className="panel panel--placeholder" aria-busy="true">
              <span className="spinner" aria-hidden="true" />
              {t('loadingMenu')}
            </div>
          )}

          {state.kind === 'failed' && (
            <div className="panel notice notice--error" role="alert">
              <strong>{state.title}</strong>
              <p>{state.detail}</p>
            </div>
          )}

          {state.kind === 'ready' && (
            <div className="layout">
              <nav className="dishes" aria-label={t('chooseDish')}>
                <h2 className="dishes__title">{t('chooseDish')}</h2>
                {state.dishes.map((dish) => (
                  <button
                    key={dish.slug}
                    type="button"
                    className={`dish${dish.slug === selected ? ' dish--on' : ''}`}
                    aria-current={dish.slug === selected ? 'true' : undefined}
                    onClick={() => setSelected(dish.slug)}
                  >
                    <span className="dish__name">{dish.name}</span>
                    <span className="dish__meta">
                      <span className="dish__cuisine">{dish.cuisine}</span>
                      <span className="dish__price">
                        {t('from')} {dish.basePrice.toFixed(2)} {dish.currency}
                      </span>
                    </span>
                    {dish.tags.length > 0 && (
                      <span className="dish__tags">
                        {dish.tags.slice(0, 3).map((tag) => (
                          <span key={tag} className="tag">
                            {tag}
                          </span>
                        ))}
                      </span>
                    )}
                  </button>
                ))}
              </nav>

              {selected && <DishForm key={selected} slug={selected} />}
            </div>
          )}
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
