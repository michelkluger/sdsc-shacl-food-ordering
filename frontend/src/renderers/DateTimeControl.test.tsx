/**
 * The date-time control, including the "Now" button.
 *
 * The pure conversions get their own tests because they are where the timezone bugs live: a
 * `datetime-local` input carries no offset, and a pickup time without one is ambiguous by an
 * hour twice a year.
 */

import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { DishForm } from '../DishForm'
import type { FormDefinition } from '../api'
import * as api from '../api'
import { translator } from '../i18n'
import type { Language } from '../i18n'
import { UiContext } from '../ui-context'
import { toInputValue, toIsoWithOffset } from './DateTimeControl'

const ISO_WITH_OFFSET = /^2026-09-05T18:30:00[+-]\d{2}:\d{2}$/

describe('toIsoWithOffset', () => {
  it('emits seconds and an explicit offset', () => {
    // Both matter: xsd:dateTime wants seconds, and a pickup time without an offset is
    // ambiguous by an hour twice a year.
    expect(toIsoWithOffset(new Date(2026, 8, 5, 18, 30, 0))).toMatch(ISO_WITH_OFFSET)
  })

  it('pads single-digit components', () => {
    expect(toIsoWithOffset(new Date(2026, 0, 2, 3, 4, 5))).toContain('2026-01-02T03:04:05')
  })

  it('round-trips through toInputValue', () => {
    expect(toInputValue(toIsoWithOffset(new Date(2026, 8, 5, 18, 30, 0)))).toBe('2026-09-05T18:30')
  })
})

describe('toInputValue', () => {
  it('renders a stored ISO string in the form the input requires', () => {
    expect(toInputValue('2026-09-05T18:30:00+02:00')).toMatch(/^2026-09-05T\d{2}:\d{2}$/)
  })

  it('returns empty for anything unparseable rather than throwing', () => {
    // The value may have been typed by hand. A blank input beats a blank page.
    for (const value of ['not-a-date', '', null, undefined, 42, {}]) {
      expect(toInputValue(value)).toBe('')
    }
  })
})

// ---------------------------------------------------------------------------
// The control, rendered by DishForm from a schema it has never seen before.
// ---------------------------------------------------------------------------

const DISH_WITH_A_DATETIME: FormDefinition = {
  dish: {
    slug: 'blorp-stew',
    name: 'Blorp Stew',
    description: 'Invented in this test file.',
    cuisine: 'Imaginary',
    basePrice: 10,
    currency: 'CHF',
    image: null,
    tags: [],
    diets: [],
    allergens: [],
  },
  schema: {
    type: 'object',
    properties: {
      collectAt: {
        type: 'string',
        format: 'date-time',
        title: 'Collect at',
        description: 'When you will come and get it.',
      },
    },
    additionalProperties: false,
  },
  uischema: {
    type: 'VerticalLayout',
    elements: [
      {
        type: 'Group',
        label: 'Pickup',
        elements: [{ type: 'Control', scope: '#/properties/collectAt', label: 'Collect at' }],
      },
    ],
  },
  '@context': {},
  shapeIri: 'https://sdsc.example/ns/food#BlorpStewOrderShape',
  language: 'en',
  availableLanguages: ['en', 'de', 'fr', 'it', 'rm'],
  pricing: { basePrice: 10, currency: 'CHF', surcharges: {}, multiplierField: null },
}

const renderIn = (language: Language = 'en') =>
  render(
    <UiContext.Provider value={{ language, t: translator(language) }}>
      <DishForm slug="blorp-stew" />
    </UiContext.Provider>,
  )

beforeEach(() => {
  vi.spyOn(api, 'getForm').mockResolvedValue(DISH_WITH_A_DATETIME)
})

afterEach(() => {
  vi.restoreAllMocks()
  vi.useRealTimers()
})

describe('the date-time control', () => {
  it('claims any field the server marks as a date-time', async () => {
    // Matched on `format: date-time`, not on the field being called `pickupTime`.
    renderIn()
    expect(await screen.findByLabelText(/Collect at/)).toHaveAttribute('type', 'datetime-local')
  })

  it('offers a button instead of making the user type a timestamp', async () => {
    renderIn()
    expect(await screen.findByRole('button', { name: 'Now' })).toBeInTheDocument()
  })

  it('fills in the current date and time when clicked', async () => {
    const user = userEvent.setup()
    renderIn()

    const before = new Date()
    await user.click(await screen.findByRole('button', { name: 'Now' }))

    const input = await screen.findByLabelText(/Collect at/)
    await waitFor(() => expect(input).not.toHaveValue(''))

    // Compared against the clock rather than a frozen time: fake timers and userEvent do not
    // combine cleanly here, and "within a minute of now" is the property that actually matters.
    const filled = new Date(String((input as HTMLInputElement).value))
    expect(Math.abs(filled.getTime() - before.getTime())).toBeLessThan(60_000)
  })

  it('submits an offset-qualified ISO string, not the raw input value', async () => {
    const submit = vi.spyOn(api, 'submitOrder').mockResolvedValue({
      orderId: 'urn:food:order:test',
      dish: 'blorp-stew',
      dishName: 'Blorp Stew',
      accepted: true,
      total: 10,
      currency: 'CHF',
      data: {},
    })
    const user = userEvent.setup()

    renderIn()
    await user.click(await screen.findByRole('button', { name: 'Now' }))
    await user.click(screen.getByRole('button', { name: 'Place order' }))

    await waitFor(() => expect(submit).toHaveBeenCalled())
    const payload = submit.mock.calls[0]?.[1] as Record<string, unknown>
    // Seconds and an offset, which is what xsd:dateTime wants and what a bare
    // `datetime-local` value would not have supplied.
    expect(String(payload.collectAt)).toMatch(/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}[+-]\d{2}:\d{2}$/)
  })

  it('clears back to absent rather than to an empty string', async () => {
    // An empty string would fail the xsd:dateTime constraint; absent is simply optional.
    const user = userEvent.setup()
    renderIn()

    await user.click(await screen.findByRole('button', { name: 'Now' }))
    await user.click(await screen.findByRole('button', { name: 'Clear' }))

    await waitFor(() => expect(screen.getByLabelText(/Collect at/)).toHaveValue(''))
    expect(screen.queryByRole('button', { name: 'Clear' })).not.toBeInTheDocument()
  })

  it('offers no clear button until there is something to clear', async () => {
    renderIn()
    await screen.findByRole('button', { name: 'Now' })
    expect(screen.queryByRole('button', { name: 'Clear' })).not.toBeInTheDocument()
  })

  it('translates the button', async () => {
    renderIn('rm')
    expect(await screen.findByRole('button', { name: 'Ussa' })).toBeInTheDocument()
  })
})
