/**
 * The whole application: pick a dish, fill in the form the server generated for it.
 *
 * The dish list is fetched, never declared. A dish added to the backend as two data files shows
 * up here on the next page load with a working, fully constrained form - which is the property
 * the task asks to be demonstrated.
 */

import { useEffect, useState } from 'react'

import { ApiError, listDishes } from './api'
import type { DishSummary } from './api'
import { DishForm } from './DishForm'

type State =
  | { kind: 'loading' }
  | { kind: 'ready'; dishes: DishSummary[] }
  | { kind: 'failed'; title: string; detail: string }

export function App() {
  const [state, setState] = useState<State>({ kind: 'loading' })
  const [selected, setSelected] = useState<string | null>(null)

  useEffect(() => {
    listDishes()
      .then((dishes) => {
        setState({ kind: 'ready', dishes })
        setSelected((current) => current ?? dishes[0]?.slug ?? null)
      })
      .catch((error: unknown) => {
        const problem = error instanceof ApiError ? error.problem : null
        setState({
          kind: 'failed',
          title: problem?.title ?? 'Could not load the menu',
          detail:
            problem?.status === 0
              ? 'The API is not reachable. Is the backend running?'
              : (problem?.detail ?? 'Something went wrong.'),
        })
      })
  }, [])

  return (
    <main className="app">
      <header className="app__header">
        <h1>Order food</h1>
        <p>
          Every field below is generated on the server from a SHACL shape. This page contains no
          form definitions and no dish-specific logic.
        </p>
      </header>

      {state.kind === 'loading' && <p className="notice">Loading the menu…</p>}

      {state.kind === 'failed' && (
        <div className="notice notice--error" role="alert">
          <strong>{state.title}</strong>
          <p>{state.detail}</p>
        </div>
      )}

      {state.kind === 'ready' && (
        <>
          <nav className="dishes" aria-label="Choose a dish">
            {state.dishes.map((dish) => (
              <button
                key={dish.slug}
                type="button"
                className={dish.slug === selected ? 'dish dish--selected' : 'dish'}
                aria-pressed={dish.slug === selected}
                onClick={() => setSelected(dish.slug)}
              >
                <span className="dish__name">{dish.name}</span>
                <span className="dish__cuisine">{dish.cuisine}</span>
                <span className="dish__price">
                  {dish.basePrice.toFixed(2)} {dish.currency}
                </span>
              </button>
            ))}
          </nav>

          {selected && <DishForm key={selected} slug={selected} />}
        </>
      )}
    </main>
  )
}
