/**
 * The frontend's central claim, under test: this client can render a dish it has never heard of.
 *
 * Every schema below is invented in the test - "Blorp Stew" is not in the backend catalogue and
 * never will be. If the component could only render French Tacos and ramen, these tests would
 * fail, which is exactly what makes them worth having.
 */

import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { DishForm } from './DishForm'
import type { FormDefinition, Violation } from './api'
import * as api from './api'
import { ApiError } from './api'

const INVENTED_DISH: FormDefinition = {
  dish: {
    slug: 'blorp-stew',
    name: 'Blorp Stew',
    description: 'A dish that exists only in this test file.',
    cuisine: 'Imaginary',
    basePrice: 9.5,
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
      blorpCount: { type: 'integer', title: 'Blorp count', minimum: 1, maximum: 4 },
      garnishes: {
        type: 'array',
        title: 'Garnishes',
        maxItems: 2,
        items: {
          type: 'string',
          oneOf: [
            { const: 'sprig', title: 'Sprig' },
            { const: 'zest', title: 'Zest' },
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

beforeEach(() => {
  vi.spyOn(api, 'getForm').mockResolvedValue(INVENTED_DISH)
})

afterEach(() => {
  vi.restoreAllMocks()
})

describe('DishForm', () => {
  it('renders a dish it has never seen, from the schema alone', async () => {
    render(<DishForm slug="blorp-stew" />)

    expect(await screen.findByRole('heading', { name: 'Blorp Stew' })).toBeInTheDocument()
    // Group label, control labels and option labels all arrive from the server. Labels are
    // matched loosely because the vanilla renderers append a `*` to required fields.
    expect(await screen.findByText('Your stew')).toBeInTheDocument()
    expect(await screen.findByLabelText(/Thickness/)).toBeInTheDocument()
    expect(await screen.findByLabelText(/Blorp count/)).toBeInTheDocument()
    // The array control renders as an add-item list rather than a single labelled input, and
    // the vanilla renderers repeat its label, so presence is asserted rather than uniqueness.
    expect((await screen.findAllByText(/Garnishes/)).length).toBeGreaterThan(0)
  })

  it('names the shape it was generated from', async () => {
    render(<DishForm slug="blorp-stew" />)
    expect(await screen.findByText('BlorpStewOrderShape')).toBeInTheDocument()
  })

  it('shows a server violation without re-deriving or re-wording it', async () => {
    vi.spyOn(api, 'submitOrder').mockRejectedValue(rejection([violation()]))
    const user = userEvent.setup()

    render(<DishForm slug="blorp-stew" />)
    await user.click(await screen.findByRole('button', { name: 'Place order' }))

    // The exact string the SHACL shape declares, verbatim, on the control it belongs to.
    // Matched as a substring: the renderer concatenates this with Ajv's own optimistic
    // client-side message for the same field into one node.
    const message = await screen.findByText(/No more than four blorps\./)
    expect(message).toBeInTheDocument()
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

    render(<DishForm slug="blorp-stew" />)
    await user.click(await screen.findByRole('button', { name: 'Place order' }))

    expect(
      await screen.findByText(/'secretDiscount' is not a field of this dish's form\./),
    ).toBeInTheDocument()
  })

  it('reports how many problems the server found', async () => {
    vi.spyOn(api, 'submitOrder').mockRejectedValue(
      rejection([violation(), violation({ pointer: '/thickness', field: 'thickness' })]),
    )
    const user = userEvent.setup()

    render(<DishForm slug="blorp-stew" />)
    await user.click(await screen.findByRole('button', { name: 'Place order' }))

    expect(await screen.findByText('2 problems with this order')).toBeInTheDocument()
  })

  it('shows a receipt when the server accepts the order', async () => {
    vi.spyOn(api, 'submitOrder').mockResolvedValue({
      orderId: 'urn:food:order:test',
      dish: 'blorp-stew',
      accepted: true,
      total: 19,
      currency: 'CHF',
      data: {},
    })
    const user = userEvent.setup()

    render(<DishForm slug="blorp-stew" />)
    await user.click(await screen.findByRole('button', { name: 'Place order' }))

    expect(await screen.findByRole('status')).toHaveTextContent('Order accepted')
    expect(screen.getByText('19.00 CHF')).toBeInTheDocument()
  })

  it('clears stale violations when the form is resubmitted', async () => {
    const submit = vi
      .spyOn(api, 'submitOrder')
      .mockRejectedValueOnce(rejection([violation()]))
      .mockResolvedValueOnce({
        orderId: 'urn:food:order:test',
        dish: 'blorp-stew',
        accepted: true,
        total: 9.5,
        currency: 'CHF',
        data: {},
      })
    const user = userEvent.setup()

    render(<DishForm slug="blorp-stew" />)
    const button = await screen.findByRole('button', { name: 'Place order' })

    await user.click(button)
    expect(await screen.findByText(/No more than four blorps\./)).toBeInTheDocument()

    await user.click(await screen.findByRole('button', { name: 'Place order' }))
    await waitFor(() => {
      expect(screen.queryByText(/No more than four blorps\./)).not.toBeInTheDocument()
    })
    expect(submit).toHaveBeenCalledTimes(2)
  })

  it('explains itself when the form cannot be loaded', async () => {
    vi.spyOn(api, 'getForm').mockRejectedValue(
      new ApiError(
        { type: 'x', title: 'Unknown dish', status: 404, detail: "No dish is registered." },
        404,
      ),
    )

    render(<DishForm slug="nope" />)
    expect(await screen.findByRole('alert')).toHaveTextContent('Unknown dish')
  })
})
