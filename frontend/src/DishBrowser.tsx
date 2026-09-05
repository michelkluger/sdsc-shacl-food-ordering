/**
 * Browse the menu: search by text, filter by diet and by allergen, pick a dish.
 *
 * This is where Meilisearch reaches the UI. Queries go to `/api/search`, and the filter chips
 * are built from the **facet counts that response returns** rather than from a list written
 * here — so a new dish contributing a new diet or allergen produces a new filter with nothing
 * added to this file, the same property the rest of the system has.
 *
 * If search is unavailable the component falls back to `/api/dishes` and hides the filters,
 * saying so quietly. That is the `SearchPort` degradation made visible: the menu still browses
 * and orders still submit when the search engine is down.
 */

import { useEffect, useMemo, useRef, useState } from 'react'

import { ApiError, listDishes, searchDishes } from './api'
import type { DishSummary, Facets } from './api'
import { useUi } from './ui-context'

/** Long enough not to query on every keystroke, short enough to feel immediate. */
const DEBOUNCE_MS = 250

interface Props {
  selected: string | null
  onSelect: (slug: string) => void
  onDishes: (dishes: DishSummary[]) => void
}

type Status =
  | { kind: 'loading' }
  | { kind: 'ready'; dishes: DishSummary[]; facets: Facets; degraded: boolean }
  | { kind: 'failed'; title: string; detail: string }

/** Facet values worth offering, in the order they should appear. */
function facetValues(facets: Facets, attribute: string): string[] {
  return Object.keys(facets[attribute] ?? {}).sort()
}

export function DishBrowser({ selected, onSelect, onDishes }: Props) {
  const { t, language } = useUi()
  const [query, setQuery] = useState('')
  const [diet, setDiet] = useState<string | null>(null)
  const [allergenFree, setAllergenFree] = useState<string[]>([])
  const [status, setStatus] = useState<Status>({ kind: 'loading' })

  // The parent is told about each result set, but `onDishes` must not be a dependency of the
  // query effect below - a caller that rebuilt the callback each render would re-query on every
  // render. Held in a ref, updated in its own effect rather than during render.
  const report = useRef(onDishes)
  useEffect(() => {
    report.current = onDishes
  }, [onDishes])

  useEffect(() => {
    let cancelled = false
    const timer = setTimeout(() => {
      void (async () => {
        try {
          const results = await searchDishes(
            // `exactOptionalPropertyTypes` is on, so an unset filter is an absent key rather
            // than an explicit `undefined`.
            { q: query, allergenFree, ...(diet ? { diet } : {}) },
            language,
          )
          if (cancelled) return
          setStatus({ kind: 'ready', dishes: results.hits, facets: results.facets, degraded: false })
          report.current(results.hits)
        } catch (error: unknown) {
          if (cancelled) return

          // 503 means Meilisearch is down, not that the menu is gone. Fall back to the plain
          // listing so someone can still find a dish and order it.
          let reportable = error
          if (error instanceof ApiError && error.status === 503) {
            try {
              const dishes = await listDishes(language)
              if (cancelled) return
              setStatus({ kind: 'ready', dishes, facets: {}, degraded: true })
              report.current(dishes)
              return
            } catch (fallbackError: unknown) {
              if (cancelled) return
              // The fallback's failure is the one worth showing: if the whole API is down,
              // "search is unavailable" would send the reader after the wrong problem.
              reportable = fallbackError
            }
          }

          const problem = reportable instanceof ApiError ? reportable.problem : null
          setStatus({
            kind: 'failed',
            title: problem?.title ?? t('menuFailed'),
            detail: problem?.status === 0 ? t('apiUnreachable') : (problem?.detail ?? t('menuFailed')),
          })
        }
      })()
    }, DEBOUNCE_MS)

    return () => {
      cancelled = true
      clearTimeout(timer)
    }
  }, [query, diet, allergenFree, language, t])

  const diets = useMemo(
    () => (status.kind === 'ready' ? facetValues(status.facets, 'diets') : []),
    [status],
  )
  const allergens = useMemo(
    () => (status.kind === 'ready' ? facetValues(status.facets, 'allergens') : []),
    [status],
  )

  const toggleAllergen = (allergen: string) =>
    setAllergenFree((current) =>
      current.includes(allergen)
        ? current.filter((item) => item !== allergen)
        : [...current, allergen],
    )

  const hasFilters = Boolean(query || diet || allergenFree.length)

  return (
    <nav className="browser" aria-label={t('chooseDish')}>
      <h2 className="browser__title">{t('chooseDish')}</h2>

      <div className="browser__search">
        <input
          type="search"
          className="browser__input"
          placeholder={t('searchPlaceholder')}
          aria-label={t('searchPlaceholder')}
          value={query}
          onChange={(event) => setQuery(event.target.value)}
        />
      </div>

      {status.kind === 'ready' && !status.degraded && (diets.length > 0 || allergens.length > 0) && (
        <div className="browser__filters">
          {diets.length > 0 && (
            <div className="facet">
              <span className="facet__name">{t('diet')}</span>
              <div className="facet__values">
                {diets.map((value) => (
                  <button
                    key={value}
                    type="button"
                    className={`facet__chip${diet === value ? ' facet__chip--on' : ''}`}
                    aria-pressed={diet === value}
                    onClick={() => setDiet(diet === value ? null : value)}
                  >
                    {value}
                  </button>
                ))}
              </div>
            </div>
          )}

          {allergens.length > 0 && (
            <div className="facet">
              <span className="facet__name">{t('withoutAllergen')}</span>
              <div className="facet__values">
                {allergens.map((value) => (
                  <button
                    key={value}
                    type="button"
                    className={`facet__chip${allergenFree.includes(value) ? ' facet__chip--on' : ''}`}
                    aria-pressed={allergenFree.includes(value)}
                    onClick={() => toggleAllergen(value)}
                  >
                    {value}
                  </button>
                ))}
              </div>
            </div>
          )}

          {hasFilters && (
            <button
              type="button"
              className="browser__reset"
              onClick={() => {
                setQuery('')
                setDiet(null)
                setAllergenFree([])
              }}
            >
              {t('clearFilters')}
            </button>
          )}
        </div>
      )}

      {status.kind === 'ready' && status.degraded && (
        <p className="browser__degraded">{t('searchUnavailable')}</p>
      )}

      {status.kind === 'loading' && (
        <p className="browser__note" aria-busy="true">
          {t('loadingMenu')}
        </p>
      )}

      {status.kind === 'failed' && (
        <div className="notice notice--error" role="alert">
          <strong>{status.title}</strong>
          <p>{status.detail}</p>
        </div>
      )}

      {status.kind === 'ready' && status.dishes.length === 0 && (
        <p className="browser__note">{t('noDishesFound')}</p>
      )}

      {status.kind === 'ready' &&
        status.dishes.map((dish) => (
          <button
            key={dish.slug}
            type="button"
            className={`dish${dish.slug === selected ? ' dish--on' : ''}`}
            aria-current={dish.slug === selected ? 'true' : undefined}
            onClick={() => onSelect(dish.slug)}
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
  )
}
