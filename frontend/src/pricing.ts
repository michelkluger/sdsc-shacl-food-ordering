/**
 * A running estimate of the order total, broken down line by line.
 *
 * Purely for display, and computed entirely from what the server sent with the form: the
 * `pricing` block (a base price, a surcharge per option token, and which field multiplies) and
 * the schema's own `oneOf` titles for the labels. Nothing about any dish is written here, and
 * no field is named. The authoritative total comes back on the receipt; if the two ever
 * disagree, the receipt is right.
 */

import type { FormDefinition } from './api'

export interface PriceLine {
  /** JSON key of the field this choice belongs to, used only as a React key. */
  field: string
  /** The field's own label, e.g. "Toppings". */
  fieldLabel: string
  /** The chosen option's label, e.g. "Chashu pork". */
  optionLabel: string
  /** Surcharge in the dish's currency. Zero means the option is included in the base price. */
  amount: number
}

export interface PriceSummary {
  basePrice: number
  lines: PriceLine[]
  /** Base price plus every surcharge, before the multiplier. */
  subtotal: number
  /** The value of the multiplier field, or 1 when there is none or it is unset. */
  multiplier: number
  /** The multiplier field's label, so the UI can say "× 2 Quantity" rather than "× 2". */
  multiplierLabel: string | null
  total: number
  currency: string
}

interface JsonSchemaLike {
  properties?: Record<string, PropertySchema>
}

interface PropertySchema {
  title?: string
  oneOf?: { const?: string; title?: string }[]
  items?: { oneOf?: { const?: string; title?: string }[] }
}

function propertiesOf(definition: FormDefinition): Record<string, PropertySchema> {
  return (definition.schema as JsonSchemaLike).properties ?? {}
}

/** The human label for one option token, from the schema the server generated. */
function optionLabel(property: PropertySchema | undefined, token: string): string {
  const options = property?.oneOf ?? property?.items?.oneOf ?? []
  return options.find((option) => option.const === token)?.title ?? token
}

/**
 * An option token is a string or a number. Anything else - an object, an empty string, null -
 * cannot name an option, so it contributes no line rather than stringifying to something
 * meaningless like `[object Object]`.
 */
const isToken = (value: unknown): value is string | number =>
  (typeof value === 'string' && value !== '') || typeof value === 'number'

function chosenTokens(value: unknown): string[] {
  if (Array.isArray(value)) return (value as unknown[]).filter(isToken).map(String)
  if (typeof value === 'boolean') return value ? ['true'] : []
  return isToken(value) ? [String(value)] : []
}

/** Round to two decimals, avoiding the usual float artefacts (19.900000000000002). */
const money = (value: number) => Math.round(value * 100) / 100

export function summarise(definition: FormDefinition, data: Record<string, unknown>): PriceSummary {
  const { basePrice, currency, surcharges, multiplierField } = definition.pricing
  const properties = propertiesOf(definition)
  const lines: PriceLine[] = []

  // Iterated in schema order rather than surcharge-map order, so the summary reads in the same
  // sequence as the form the user is filling in.
  for (const [field, property] of Object.entries(properties)) {
    const perToken = surcharges[field]
    if (!perToken) continue

    for (const token of chosenTokens(data[field])) {
      lines.push({
        field: `${field}:${token}`,
        fieldLabel: property.title ?? field,
        optionLabel: optionLabel(property, token),
        amount: perToken[token] ?? 0,
      })
    }
  }

  const subtotal = money(basePrice + lines.reduce((sum, line) => sum + line.amount, 0))

  let multiplier = 1
  let multiplierLabel: string | null = null
  if (multiplierField) {
    const value = data[multiplierField]
    if (typeof value === 'number' && Number.isFinite(value) && value > 0) {
      multiplier = value
    }
    multiplierLabel = properties[multiplierField]?.title ?? multiplierField
  }

  return {
    basePrice,
    lines,
    subtotal,
    multiplier,
    multiplierLabel,
    total: money(subtotal * multiplier),
    currency,
  }
}

/** The total alone, for callers that do not need the breakdown. */
export function estimateTotal(
  definition: FormDefinition,
  data: Record<string, unknown>,
): number {
  return summarise(definition, data).total
}
