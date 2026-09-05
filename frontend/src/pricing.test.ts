/**
 * The running order summary.
 *
 * `summarise` is pure and takes the whole form definition, so these tests are the cheapest place
 * to pin down the pricing rules. The dish below is invented: if any of this only worked for the
 * real catalogue, these would fail.
 */

import { describe, expect, it } from 'vitest'

import type { FormDefinition } from './api'
import { estimateTotal, summarise } from './pricing'

const DISH: FormDefinition = {
  dish: {
    slug: 'blorp-stew',
    name: 'Blorp Stew',
    description: 'Invented here.',
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
      thickness: {
        type: 'string',
        title: 'Thickness',
        oneOf: [
          { const: 'thin', title: 'Thin' },
          { const: 'thick', title: 'Thick' },
        ],
      },
      garnishes: {
        type: 'array',
        title: 'Garnishes',
        items: {
          type: 'string',
          oneOf: [
            { const: 'sprig', title: 'Sprig' },
            { const: 'zest', title: 'Zest' },
          ],
        },
      },
      blorpCount: { type: 'integer', title: 'Blorp count', minimum: 1, maximum: 4 },
      note: { type: 'string', title: 'Note' },
    },
  },
  uischema: { type: 'VerticalLayout', elements: [] },
  '@context': {},
  shapeIri: 'https://sdsc.example/ns/food#BlorpStewOrderShape',
  language: 'en',
  availableLanguages: ['en'],
  pricing: {
    basePrice: 10,
    currency: 'CHF',
    surcharges: {
      thickness: { thin: 0, thick: 2.5 },
      garnishes: { sprig: 1, zest: 1.5 },
    },
    multiplierField: 'blorpCount',
  },
}

describe('summarise', () => {
  it('starts from the base price with nothing chosen', () => {
    const summary = summarise(DISH, {})
    expect(summary.lines).toEqual([])
    expect(summary.subtotal).toBe(10)
    expect(summary.total).toBe(10)
    expect(summary.currency).toBe('CHF')
  })

  it('labels each chosen option from the schema the server sent', () => {
    // The labels come from `oneOf` titles, so they are already in the user's language.
    const summary = summarise(DISH, { thickness: 'thick' })
    expect(summary.lines).toEqual([
      { field: 'thickness:thick', fieldLabel: 'Thickness', optionLabel: 'Thick', amount: 2.5 },
    ])
  })

  it('gives one line per element of a multi-valued field', () => {
    const summary = summarise(DISH, { garnishes: ['sprig', 'zest'] })
    expect(summary.lines.map((line) => line.optionLabel)).toEqual(['Sprig', 'Zest'])
    expect(summary.subtotal).toBe(12.5)
  })

  it('keeps zero-cost choices as lines so the summary shows the whole order', () => {
    const summary = summarise(DISH, { thickness: 'thin' })
    expect(summary.lines).toHaveLength(1)
    expect(summary.lines[0]?.amount).toBe(0)
    expect(summary.total).toBe(10)
  })

  it('ignores fields that carry no surcharges', () => {
    expect(summarise(DISH, { note: 'no onions' }).lines).toEqual([])
  })

  it('lists lines in schema order, not surcharge-map order', () => {
    // So the summary reads in the same sequence as the form being filled in.
    const summary = summarise(DISH, { garnishes: ['sprig'], thickness: 'thick' })
    expect(summary.lines.map((line) => line.fieldLabel)).toEqual(['Thickness', 'Garnishes'])
  })

  it('multiplies by the field the server nominated, and reports its label', () => {
    const summary = summarise(DISH, { thickness: 'thick', blorpCount: 3 })
    expect(summary.subtotal).toBe(12.5)
    expect(summary.multiplier).toBe(3)
    expect(summary.multiplierLabel).toBe('Blorp count')
    expect(summary.total).toBe(37.5)
  })

  it('treats an absent or invalid multiplier as one', () => {
    for (const value of [undefined, 0, -2, 'two', null]) {
      expect(summarise(DISH, { blorpCount: value }).total).toBe(10)
    }
  })

  it('ignores the multiplier entirely when the dish declares none', () => {
    const withoutMultiplier: FormDefinition = {
      ...DISH,
      pricing: { ...DISH.pricing, multiplierField: null },
    }
    const summary = summarise(withoutMultiplier, { blorpCount: 5 })
    expect(summary.multiplierLabel).toBeNull()
    expect(summary.total).toBe(10)
  })

  it('falls back to the token when an option has no title', () => {
    const summary = summarise(DISH, { thickness: 'unlabelled' })
    expect(summary.lines[0]?.optionLabel).toBe('unlabelled')
  })

  it('rounds to two decimals rather than exposing float artefacts', () => {
    const awkward: FormDefinition = {
      ...DISH,
      pricing: { ...DISH.pricing, basePrice: 0.1, surcharges: { thickness: { thick: 0.2 } } },
    }
    expect(summarise(awkward, { thickness: 'thick' }).total).toBe(0.3)
  })
})

describe('estimateTotal', () => {
  it('agrees with the summary it wraps', () => {
    const data = { thickness: 'thick', garnishes: ['zest'], blorpCount: 2 }
    expect(estimateTotal(DISH, data)).toBe(summarise(DISH, data).total)
  })
})
