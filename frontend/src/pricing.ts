/**
 * A running estimate of the order total.
 *
 * Purely for display, and computed entirely from the `pricing` block the server sends with the
 * form: a base price, a surcharge per option token, and the name of the field that multiplies.
 * Nothing about any dish is written here. The authoritative total comes back on the receipt, and
 * if the two ever disagree the receipt is right.
 */

import type { FormDefinition } from './api'

export function estimateTotal(
  definition: FormDefinition,
  data: Record<string, unknown>,
): number {
  const { basePrice, surcharges, multiplierField } = definition.pricing
  let total = basePrice

  for (const [field, perToken] of Object.entries(surcharges)) {
    const chosen = data[field]
    const tokens = Array.isArray(chosen) ? chosen : chosen == null ? [] : [chosen]
    for (const token of tokens) {
      total += perToken[String(token)] ?? 0
    }
  }

  if (multiplierField) {
    const multiplier = data[multiplierField]
    if (typeof multiplier === 'number' && Number.isFinite(multiplier) && multiplier > 0) {
      total *= multiplier
    }
  }

  // Two decimals, avoiding the usual float artefacts (19.900000000000002).
  return Math.round(total * 100) / 100
}
