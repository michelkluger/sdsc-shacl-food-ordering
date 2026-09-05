/**
 * The frontend's central claim, under test: this client can render a dish it has never heard of.
 *
 * Every schema below is invented in the test - "Blorp Stew" is not in the backend catalogue and
 * never will be. If the component or the custom renderers could only handle the real dishes,
 * these tests would fail, which is exactly what makes them worth having.
 */

import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { DishForm } from './DishForm'
import type { FormDefinition, OrderReceipt, Violation } from './api'
import * as api from './api'
import { ApiError } from './api'
import { translator } from './i18n'
import type { Language } from './i18n'
import { UiContext } from './ui-context'

const INVENTED_DISH: FormDefinition = {
  dish: {
    slug: 'blorp-stew',
    name: 'Blorp Stew',
    description: 'A dish that exists only in this test file.',
    cuisine: 'Imaginary',
    basePrice: 10,
    currency: 'CHF',
    image: null,
    tags: [],
    diets: [],
    allergens: ['glimmer'],
  },
  schema: {
    type: 'object',
    properties: {
      thickness: {
        type: 'string',
        title: 'Thickness',
        oneOf: [
          { const: 'thin', title: 'Thin' },
          { const: 'thick', title: 'Thick' },
        ],
      },
      blorpCount: { type: 'integer', title: 'Blorp count', minimum: 1, maximum: 4, default: 1 },
      garnishes: {
        type: 'array',
        title: 'Garnishes',
        maxItems: 2,
        items: {
          type: 'string',
          oneOf: [
            { const: 'sprig', title: 'Sprig' },
            { const: 'zest', title: 'Zest' },
            { const: 'dust', title: 'Dust' },
          ],
        },
      },
    },
    required: ['thickness', 'blorpCount'],
    additionalProperties: false,
  },
  uischema: {
    type: 'VerticalLayout',
    elements: [
      {
        type: 'Group',
        label: 'Your stew',
        elements: [
          { type: 'Control', scope: '#/properties/thickness', label: 'Thickness' },
          { type: 'Control', scope: '#/properties/blorpCount', label: 'Blorp count' },
          { type: 'Control', scope: '#/properties/garnishes', label: 'Garnishes' },
        ],
      },
    ],
  },
  '@context': { thickness: { '@id': 'https://sdsc.example/ns/food#thickness' } },
  shapeIri: 'https://sdsc.example/ns/food#BlorpStewOrderShape',
  language: 'en',
  availableLanguages: ['en', 'de', 'fr', 'it', 'rm'],
  pricing: {
    basePrice: 10,
    currency: 'CHF',
    surcharges: {
      thickness: { thin: 0, thick: 2.5 },
      garnishes: { sprig: 1, zest: 1.5, dust: 0 },
    },
    multiplierField: 'blorpCount',
  },
}

function violation(overrides: Partial<Violation> = {}): Violation {
  return {
    pointer: '/blorpCount',
    field: 'blorpCount',
    path: 'https://sdsc.example/ns/food#blorpCount',
    constraint: 'MaxInclusiveConstraintComponent',
    severity: 'violation',
    message: 'No more than four blorps.',
    value: 9,
    ...overrides,
  }
}

function rejection(violations: Violation[]): ApiError {
  return new ApiError(
    {
      type: 'https://sdsc.example/problems/shacl-validation',
      title: "The order does not satisfy the dish's constraints",
      status: 422,
      detail: `${violations.length} constraint violations found by SHACL validation.`,
      violations,
    },
    422,
  )
}

const receipt: OrderReceipt = {
  orderId: 'urn:food:order:test',
  dish: 'blorp-stew',
  dishName: 'Blorp Stew',
  accepted: true,
  total: 12.5,
  currency: 'CHF',
  data: {},
}

/** Renders the form inside the UI context, the way `App` mounts it. */
const renderIn = (language: Language, slug = 'blorp-stew') =>
  render(
    <UiContext.Provider value={{ language, t: translator(language) }}>
      <DishForm slug={slug} />
    </UiContext.Provider>,
  )

const renderForm = (language: Language = 'en') => renderIn(language)

beforeEach(() => {
  vi.spyOn(api, 'getForm').mockResolvedValue(INVENTED_DISH)
})

afterEach(() => {
  vi.restoreAllMocks()
})

describe('rendering an unknown dish', () => {
  it('renders a dish it has never seen, from the schema alone', async () => {
    renderForm()

    expect(await screen.findByRole('heading', { name: 'Blorp Stew' })).toBeInTheDocument()
    expect(await screen.findByText('Your stew')).toBeInTheDocument()
    expect(await screen.findByText('Thickness')).toBeInTheDocument()
    expect(await screen.findByText('Garnishes')).toBeInTheDocument()
  })

  it('names the shape it was generated from', async () => {
    renderForm()
    expect(await screen.findByText('BlorpStewOrderShape')).toBeInTheDocument()
  })

  it('shows the allergens the catalogue declares', async () => {
    renderForm()
    expect(await screen.findByText(/glimmer/)).toBeInTheDocument()
  })
})

describe('option cards, for short enumerations', () => {
  it('renders every option as a visible choice rather than hiding them in a dropdown', async () => {
    renderForm()
    const group = await screen.findByRole('radiogroup', { name: /Thickness/ })

    expect(within(group).getByRole('radio', { name: 'Thin' })).toBeInTheDocument()
    expect(within(group).getByRole('radio', { name: 'Thick' })).toBeInTheDocument()
  })

  it('marks the chosen option', async () => {
    const user = userEvent.setup()
    renderForm()

    await user.click(await screen.findByRole('radio', { name: 'Thick' }))
    await waitFor(() =>
      expect(screen.getByRole('radio', { name: 'Thick' })).toHaveAttribute('aria-checked', 'true'),
    )
  })
})

describe('chip multi-select, for arrays of enumerated values', () => {
  it('offers every value as a toggle, with no add-a-row step', async () => {
    renderForm()
    const group = await screen.findByRole('group', { name: /Garnishes/ })

    for (const label of ['Sprig', 'Zest', 'Dust']) {
      expect(within(group).getByRole('button', { name: new RegExp(label) })).toBeInTheDocument()
    }
  })

  it('toggles a value on and off', async () => {
    const user = userEvent.setup()
    renderForm()

    const sprig = await screen.findByRole('button', { name: /Sprig/ })

    // `waitFor` rather than a bare assertion: the click resolves before React has necessarily
    // re-rendered, which passes on a fast machine and fails on a loaded CI runner.
    await user.click(sprig)
    await waitFor(() => expect(sprig).toHaveAttribute('aria-pressed', 'true'))

    await user.click(sprig)
    await waitFor(() => expect(sprig).toHaveAttribute('aria-pressed', 'false'))
  })

  it('shows how many of the allowed maximum are chosen', async () => {
    const user = userEvent.setup()
    renderForm()

    await user.click(await screen.findByRole('button', { name: /Sprig/ }))
    expect(await screen.findByText('1 of 2 chosen')).toBeInTheDocument()
  })

  it('disables the remaining options once maxItems is reached', async () => {
    // sh:maxCount became maxItems, so the limit is visible before it is hit rather than only
    // being reported after a round trip.
    const user = userEvent.setup()
    renderForm()

    await user.click(await screen.findByRole('button', { name: /Sprig/ }))
    await user.click(await screen.findByRole('button', { name: /Zest/ }))

    expect(await screen.findByRole('button', { name: /Dust/ })).toBeDisabled()
    // Already-chosen values stay clickable, so a choice can always be undone.
    expect(screen.getByRole('button', { name: /Sprig/ })).toBeEnabled()
  })

  it('clears the whole selection', async () => {
    const user = userEvent.setup()
    renderForm()

    await user.click(await screen.findByRole('button', { name: /Sprig/ }))
    await user.click(await screen.findByRole('button', { name: 'Clear' }))

    await waitFor(() =>
      expect(screen.getByRole('button', { name: /Sprig/ })).toHaveAttribute(
        'aria-pressed',
        'false',
      ),
    )
  })
})

describe('bounded integers', () => {
  it('renders a stepper that cannot go below the minimum', async () => {
    renderForm()
    // blorpCount is 1..4 with a default of 1, so decrementing is unavailable from the start.
    expect(await screen.findByRole('button', { name: '-' })).toBeDisabled()
  })

  it('increments up to the maximum and then stops', async () => {
    const user = userEvent.setup()
    renderForm()

    const plus = await screen.findByRole('button', { name: '+' })
    await user.click(plus)
    await user.click(plus)
    await user.click(plus)

    expect(await screen.findByDisplayValue('4')).toBeInTheDocument()
    expect(plus).toBeDisabled()
  })
})

describe('the running total', () => {
  it('starts at the base price', async () => {
    renderForm()
    expect(await screen.findByText('10.00 CHF')).toBeInTheDocument()
  })

  it('adds the surcharge of a chosen option', async () => {
    const user = userEvent.setup()
    renderForm()

    await user.click(await screen.findByRole('radio', { name: 'Thick' }))
    expect(await screen.findByText('12.50 CHF')).toBeInTheDocument()
  })

  it('multiplies by the field the server nominated', async () => {
    // `multiplierField` comes from food:isMultiplier in the vocabulary, not from a field name
    // written in the client.
    const user = userEvent.setup()
    renderForm()

    await user.click(await screen.findByRole('button', { name: '+' }))
    expect(await screen.findByText('20.00 CHF')).toBeInTheDocument()
  })
})

describe('server violations', () => {
  it('shows a server violation without re-deriving or re-wording it', async () => {
    vi.spyOn(api, 'submitOrder').mockRejectedValue(rejection([violation()]))
    const user = userEvent.setup()
    renderForm()

    await user.click(await screen.findByRole('button', { name: 'Place order' }))
    expect(await screen.findByText(/No more than four blorps\./)).toBeInTheDocument()
  })

  it('surfaces a violation that no control can display', async () => {
    // sh:closed reports a field the schema does not contain, so there is no control to attach
    // the message to. Dropping it silently would hide a real rejection from the user.
    vi.spyOn(api, 'submitOrder').mockRejectedValue(
      rejection([
        violation({
          pointer: '/secretDiscount',
          field: 'secretDiscount',
          constraint: 'ClosedConstraintComponent',
          message: "'secretDiscount' is not a field of this dish's form.",
        }),
      ]),
    )
    const user = userEvent.setup()
    renderForm()

    await user.click(await screen.findByRole('button', { name: 'Place order' }))
    expect(
      await screen.findByText(/'secretDiscount' is not a field of this dish's form\./),
    ).toBeInTheDocument()
  })

  it('counts the problems', async () => {
    vi.spyOn(api, 'submitOrder').mockRejectedValue(
      rejection([violation(), violation({ pointer: '/thickness', field: 'thickness' })]),
    )
    const user = userEvent.setup()
    renderForm()

    await user.click(await screen.findByRole('button', { name: 'Place order' }))
    expect(await screen.findByText('2 things need fixing')).toBeInTheDocument()
  })

  it('uses the singular for one problem', async () => {
    vi.spyOn(api, 'submitOrder').mockRejectedValue(rejection([violation()]))
    const user = userEvent.setup()
    renderForm()

    await user.click(await screen.findByRole('button', { name: 'Place order' }))
    expect(await screen.findByText('One thing needs fixing')).toBeInTheDocument()
  })

  it('clears stale violations when the form is resubmitted', async () => {
    const submit = vi
      .spyOn(api, 'submitOrder')
      .mockRejectedValueOnce(rejection([violation()]))
      .mockResolvedValueOnce(receipt)
    const user = userEvent.setup()
    renderForm()

    await user.click(await screen.findByRole('button', { name: 'Place order' }))
    expect(await screen.findByText(/No more than four blorps\./)).toBeInTheDocument()

    await user.click(await screen.findByRole('button', { name: 'Place order' }))
    await waitFor(() => {
      expect(screen.queryByText(/No more than four blorps\./)).not.toBeInTheDocument()
    })
    expect(submit).toHaveBeenCalledTimes(2)
  })
})

describe('confirmation and failure', () => {
  it('shows a receipt when the server accepts the order', async () => {
    vi.spyOn(api, 'submitOrder').mockResolvedValue(receipt)
    const user = userEvent.setup()
    renderForm()

    await user.click(await screen.findByRole('button', { name: 'Place order' }))

    expect(await screen.findByRole('status')).toHaveTextContent('Order accepted')
    expect(screen.getByText('12.50 CHF')).toBeInTheDocument()
  })

  it('explains itself when the form cannot be loaded', async () => {
    vi.spyOn(api, 'getForm').mockRejectedValue(
      new ApiError(
        { type: 'x', title: 'Unknown dish', status: 404, detail: 'No dish is registered.' },
        404,
      ),
    )

    renderIn('en', 'nope')
    expect(await screen.findByRole('alert')).toHaveTextContent('Unknown dish')
  })
})

describe('language', () => {
  it('asks the server for the requested language', async () => {
    const getForm = vi.spyOn(api, 'getForm')
    renderForm('rm')

    await waitFor(() => {
      expect(getForm).toHaveBeenCalledWith('blorp-stew', 'rm')
    })
  })

  it('translates its own chrome without touching what the server sent', async () => {
    renderForm('de')

    // The button is the client's string...
    expect(await screen.findByRole('button', { name: 'Bestellen' })).toBeInTheDocument()
    // ...while the dish's own strings are whatever the server returned, untouched.
    expect(screen.getByRole('heading', { name: 'Blorp Stew' })).toBeInTheDocument()
  })

  it('submits in the current language so violations come back translated', async () => {
    const submit = vi.spyOn(api, 'submitOrder').mockResolvedValue(receipt)
    const user = userEvent.setup()
    renderForm('it')

    await user.click(await screen.findByRole('button', { name: 'Ordina' }))
    await waitFor(() => {
      expect(submit).toHaveBeenCalledWith('blorp-stew', expect.anything(), 'it')
    })
  })
})
