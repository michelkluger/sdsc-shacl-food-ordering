/**
 * The dish browser: where Meilisearch actually reaches the UI.
 *
 * Two claims worth holding to: the filter chips are built from the *facets the server returned*
 * rather than from a list written in the client, and a search outage degrades to the plain menu
 * instead of an empty page.
 */

import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { DishBrowser } from './DishBrowser'
import type { DishSummary, SearchResults } from './api'
import * as api from './api'
import { ApiError } from './api'
import { translator } from './i18n'
import { UiContext } from './ui-context'

const dish = (slug: string, name: string, extra: Partial<DishSummary> = {}): DishSummary => ({
  slug,
  name,
  description: 'Invented in this test file.',
  cuisine: 'Imaginary',
  basePrice: 10,
  currency: 'CHF',
  image: null,
  tags: [],
  diets: [],
  allergens: [],
  ...extra,
})

const BLORP = dish('blorp-stew', 'Blorp Stew', { diets: ['vegan-available'], allergens: ['glimmer'] })
const ZORP = dish('zorp-pie', 'Zorp Pie', { allergens: ['sparkle'] })

const results = (hits: DishSummary[]): SearchResults => ({
  query: '',
  hits,
  estimatedTotal: hits.length,
  // Facets the *server* computed. The filter chips must come from these, not from a
  // hardcoded list, so a new dish contributing a new diet produces a new chip for free.
  facets: {
    diets: { 'vegan-available': 1 },
    allergens: { glimmer: 1, sparkle: 1 },
    cuisine: { Imaginary: 2 },
    tags: {},
  },
})

const renderBrowser = (onSelect = vi.fn(), onDishes = vi.fn()) =>
  render(
    <UiContext.Provider value={{ language: 'en', t: translator('en') }}>
      <DishBrowser selected={null} onSelect={onSelect} onDishes={onDishes} />
    </UiContext.Provider>,
  )

beforeEach(() => {
  vi.spyOn(api, 'searchDishes').mockResolvedValue(results([BLORP, ZORP]))
})

afterEach(() => {
  vi.restoreAllMocks()
})

describe('browsing', () => {
  it('lists what the search endpoint returned', async () => {
    renderBrowser()
    expect(await screen.findByText('Blorp Stew')).toBeInTheDocument()
    expect(screen.getByText('Zorp Pie')).toBeInTheDocument()
  })

  it('tells the parent which dishes are on screen', async () => {
    const onDishes = vi.fn()
    renderBrowser(vi.fn(), onDishes)
    await waitFor(() => expect(onDishes).toHaveBeenCalledWith([BLORP, ZORP]))
  })

  it('selects a dish when one is clicked', async () => {
    const onSelect = vi.fn()
    const user = userEvent.setup()
    renderBrowser(onSelect)

    await user.click(await screen.findByText('Blorp Stew'))
    expect(onSelect).toHaveBeenCalledWith('blorp-stew')
  })

  it('says so when nothing matches', async () => {
    vi.spyOn(api, 'searchDishes').mockResolvedValue(results([]))
    renderBrowser()
    expect(await screen.findByText('No dishes match.')).toBeInTheDocument()
  })
})

describe('searching', () => {
  it('queries the server with what was typed', async () => {
    const search = vi.spyOn(api, 'searchDishes')
    const user = userEvent.setup()
    renderBrowser()
    await screen.findByText('Blorp Stew')

    await user.type(screen.getByRole('searchbox'), 'zorp')

    await waitFor(() =>
      expect(search).toHaveBeenLastCalledWith(expect.objectContaining({ q: 'zorp' }), 'en'),
    )
  })

  it('debounces rather than querying on every keystroke', async () => {
    const search = vi.spyOn(api, 'searchDishes')
    const user = userEvent.setup()
    renderBrowser()
    await screen.findByText('Blorp Stew')
    search.mockClear()

    await user.type(screen.getByRole('searchbox'), 'zorp')
    await waitFor(() => expect(search).toHaveBeenCalled())

    // Four characters typed; a debounced input must not have produced four requests.
    expect(search.mock.calls.length).toBeLessThan(4)
  })
})

describe('facet filters', () => {
  it('builds the chips from the facets the server returned', async () => {
    // Nothing in the client names a diet or an allergen; these come from the response.
    renderBrowser()
    expect(await screen.findByRole('button', { name: 'vegan-available' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'glimmer' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'sparkle' })).toBeInTheDocument()
  })

  it('sends a chosen diet to the server', async () => {
    const search = vi.spyOn(api, 'searchDishes')
    const user = userEvent.setup()
    renderBrowser()

    await user.click(await screen.findByRole('button', { name: 'vegan-available' }))
    await waitFor(() =>
      expect(search).toHaveBeenLastCalledWith(
        expect.objectContaining({ diet: 'vegan-available' }),
        'en',
      ),
    )
  })

  it('accumulates allergen exclusions rather than replacing them', async () => {
    const search = vi.spyOn(api, 'searchDishes')
    const user = userEvent.setup()
    renderBrowser()

    await user.click(await screen.findByRole('button', { name: 'glimmer' }))
    await user.click(await screen.findByRole('button', { name: 'sparkle' }))

    await waitFor(() =>
      expect(search).toHaveBeenLastCalledWith(
        expect.objectContaining({ allergenFree: ['glimmer', 'sparkle'] }),
        'en',
      ),
    )
  })

  it('toggles a filter back off', async () => {
    const user = userEvent.setup()
    renderBrowser()

    const chip = await screen.findByRole('button', { name: 'vegan-available' })
    await user.click(chip)
    await waitFor(() => expect(chip).toHaveAttribute('aria-pressed', 'true'))

    await user.click(chip)
    await waitFor(() => expect(chip).toHaveAttribute('aria-pressed', 'false'))
  })

  it('clears every filter at once', async () => {
    const user = userEvent.setup()
    renderBrowser()

    await user.click(await screen.findByRole('button', { name: 'vegan-available' }))
    await user.click(await screen.findByRole('button', { name: 'Clear filters' }))

    await waitFor(() =>
      expect(screen.getByRole('button', { name: 'vegan-available' })).toHaveAttribute(
        'aria-pressed',
        'false',
      ),
    )
    expect(screen.getByRole('searchbox')).toHaveValue('')
  })
})

describe('when search is unavailable', () => {
  const unavailable = new ApiError(
    {
      type: 'https://sdsc.example/problems/search-unavailable',
      title: 'Search is unavailable',
      status: 503,
      detail: 'Meilisearch is unreachable.',
    },
    503,
  )

  it('falls back to the plain menu instead of showing an empty page', async () => {
    // The SearchPort degradation, made visible: the menu still browses when the search engine
    // is down, and the API contract says ordering is unaffected.
    vi.spyOn(api, 'searchDishes').mockRejectedValue(unavailable)
    const listDishes = vi.spyOn(api, 'listDishes').mockResolvedValue([BLORP, ZORP])

    renderBrowser()

    expect(await screen.findByText('Blorp Stew')).toBeInTheDocument()
    expect(listDishes).toHaveBeenCalled()
  })

  it('says why the filters are gone rather than silently dropping them', async () => {
    vi.spyOn(api, 'searchDishes').mockRejectedValue(unavailable)
    vi.spyOn(api, 'listDishes').mockResolvedValue([BLORP])

    renderBrowser()

    expect(
      await screen.findByText('Search is unavailable; showing the whole menu.'),
    ).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'vegan-available' })).not.toBeInTheDocument()
  })

  it('reports a real failure when even the plain menu cannot be fetched', async () => {
    vi.spyOn(api, 'searchDishes').mockRejectedValue(unavailable)
    vi.spyOn(api, 'listDishes').mockRejectedValue(
      new ApiError({ type: 'about:blank', title: 'x', status: 0, detail: 'down' }, 0),
    )

    renderBrowser()
    const alert = await screen.findByRole('alert')
    expect(within(alert).getByText(/not reachable/i)).toBeInTheDocument()
  })
})
