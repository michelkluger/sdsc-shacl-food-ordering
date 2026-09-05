/**
 * The whole contract with the backend.
 *
 * Note what is *not* here: no dish names, no field names, no option lists, no validation rules.
 * The client knows there is a list of dishes and that each one yields a schema pair; everything
 * specific to French Tacos or ramen arrives over the wire, generated from a SHACL shape.
 */

import type { JsonSchema, UISchemaElement } from '@jsonforms/core'

const BASE = (import.meta.env.VITE_API_BASE_URL ?? '').replace(/\/$/, '')

export interface DishSummary {
  slug: string
  name: string
  description: string
  cuisine: string
  basePrice: number
  currency: string
  image: string | null
  tags: string[]
  diets: string[]
  allergens: string[]
}

/** Enough for a running estimate. The server prices the order authoritatively on submit. */
export interface PricingHint {
  basePrice: number
  currency: string
  surcharges: Record<string, Record<string, number>>
  multiplierField: string | null
}

export interface FormDefinition {
  dish: DishSummary
  schema: JsonSchema
  uischema: UISchemaElement
  '@context': Record<string, unknown>
  shapeIri: string
  /** The language the strings above are in, after negotiation. */
  language: string
  /** Every language the server can serve, so the switcher is never a hardcoded list. */
  availableLanguages: string[]
  pricing: PricingHint
}

export interface OrderReceipt {
  orderId: string
  dish: string
  dishName: string
  accepted: boolean
  total: number
  currency: string
  data: Record<string, unknown>
}

/** One SHACL constraint failure, addressed at the field that caused it. */
export interface Violation {
  /** JSON pointer into the submitted data, e.g. `/toppings/1`. */
  pointer: string
  field: string | null
  path: string | null
  constraint: string
  severity: string
  message: string
  value: unknown
}

/** RFC 9457 problem details. `violations` is present only on a SHACL rejection. */
export interface ProblemDetail {
  type: string
  title: string
  status: number
  detail: string
  instance?: string
  dish?: string
  violations?: Violation[]
  availableDishes?: string[]
}

export class ApiError extends Error {
  constructor(
    readonly problem: ProblemDetail,
    readonly status: number,
  ) {
    super(problem.detail || problem.title)
    this.name = 'ApiError'
  }

  /** Violations if the server rejected the payload on constraint grounds, else empty. */
  get violations(): Violation[] {
    return this.problem.violations ?? []
  }
}

function withLanguage(path: string, language?: string): string {
  if (!language) return path
  const separator = path.includes('?') ? '&' : '?'
  return `${path}${separator}lang=${encodeURIComponent(language)}`
}

async function request<T>(path: string, language?: string, init?: RequestInit): Promise<T> {
  let response: Response
  try {
    response = await fetch(`${BASE}${withLanguage(path, language)}`, {
      ...init,
      headers: {
        'Content-Type': 'application/json',
        // Sent as well as `?lang=` so the API behaves correctly for any client, including one
        // that only sets the header. The explicit parameter wins, which is what a user
        // clicking the switcher means.
        ...(language ? { 'Accept-Language': language } : {}),
        ...init?.headers,
      },
    })
  } catch (cause) {
    // A network failure has no problem document, so synthesise one. Every caller then has a
    // single error shape to handle rather than branching on "did we even reach the server".
    throw new ApiError(
      {
        type: 'about:blank',
        title: 'Cannot reach the server',
        status: 0,
        detail: cause instanceof Error ? cause.message : 'The request failed.',
      },
      0,
    )
  }

  if (!response.ok) {
    const problem = (await response.json().catch(() => null)) as ProblemDetail | null
    throw new ApiError(
      problem ?? {
        type: 'about:blank',
        title: response.statusText || 'Request failed',
        status: response.status,
        detail: `The server returned ${response.status}.`,
      },
      response.status,
    )
  }

  return response.json() as Promise<T>
}

export const listDishes = (language?: string): Promise<DishSummary[]> =>
  request<DishSummary[]>('/api/dishes', language)

export const getForm = (slug: string, language?: string): Promise<FormDefinition> =>
  request<FormDefinition>(`/api/dishes/${encodeURIComponent(slug)}/form`, language)

export const submitOrder = (
  slug: string,
  data: Record<string, unknown>,
  language?: string,
): Promise<OrderReceipt> =>
  request<OrderReceipt>(`/api/orders/${encodeURIComponent(slug)}`, language, {
    method: 'POST',
    body: JSON.stringify({ data }),
  })
