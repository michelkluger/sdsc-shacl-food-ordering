/**
 * Translate server violations into the error objects JSON Forms renders.
 *
 * This is the join between the two halves of the system. The backend addresses every SHACL
 * violation with a JSON pointer; JSON Forms attaches an error to a control by matching an Ajv
 * `instancePath`, which is also a JSON pointer. So the mapping is essentially the identity
 * function - which is the whole reason the backend was made to emit pointers rather than field
 * names or prose.
 */

import type { ErrorObject } from 'ajv'

import type { Violation } from './api'

/**
 * Errors JSON Forms will display, given via its `additionalErrors` prop.
 *
 * `keyword: 'shacl'` marks these as server-side so they are distinguishable from Ajv's own
 * optimistic client-side checks, and `schemaPath` points at the property so a renderer that
 * looks it up finds something real.
 */
export function toAdditionalErrors(violations: Violation[]): ErrorObject[] {
  return violations.map((violation) => ({
    instancePath: violation.pointer,
    schemaPath: violation.field ? `#/properties/${violation.field}` : '#',
    keyword: 'shacl',
    params: { constraint: violation.constraint, value: violation.value },
    message: violation.message,
  }))
}

/**
 * Violations that no control can display, and which therefore need showing at form level.
 *
 * A `sh:closed` violation names a field the schema does not contain, so no control exists to
 * carry its message; the same is true of anything reported against the order as a whole. Left
 * unhandled these would vanish silently, which is worse than a validator that simply said no.
 */
export function formLevelViolations(
  violations: Violation[],
  schemaProperties: readonly string[],
): Violation[] {
  const known = new Set(schemaProperties)
  return violations.filter((violation) => violation.field === null || !known.has(violation.field))
}
