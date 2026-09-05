import { describe, expect, it } from 'vitest'

import type { Violation } from './api'
import { formLevelViolations, toAdditionalErrors } from './violations'

function violation(overrides: Partial<Violation> = {}): Violation {
  return {
    pointer: '/toppings/1',
    field: 'toppings',
    path: 'https://sdsc.example/ns/food#topping',
    constraint: 'SPARQLConstraintComponent',
    severity: 'violation',
    message: 'Chashu pork is not available with a vegan broth.',
    value: 'chashu',
    ...overrides,
  }
}

describe('toAdditionalErrors', () => {
  it('uses the server pointer as the Ajv instancePath verbatim', () => {
    // The backend emits JSON pointers precisely so this mapping stays the identity function.
    const [error] = toAdditionalErrors([violation()])
    expect(error?.instancePath).toBe('/toppings/1')
    expect(error?.message).toBe('Chashu pork is not available with a vegan broth.')
  })

  it('marks errors as server-side so they are distinguishable from Ajv checks', () => {
    const [error] = toAdditionalErrors([violation()])
    expect(error?.keyword).toBe('shacl')
    expect(error?.params).toMatchObject({ constraint: 'SPARQLConstraintComponent' })
  })

  it('points schemaPath at the property when the violation names a field', () => {
    const [error] = toAdditionalErrors([violation()])
    expect(error?.schemaPath).toBe('#/properties/toppings')
  })

  it('falls back to the document root for a violation with no field', () => {
    const [error] = toAdditionalErrors([violation({ field: null, pointer: '' })])
    expect(error?.schemaPath).toBe('#')
    expect(error?.instancePath).toBe('')
  })

  it('preserves order and count', () => {
    const errors = toAdditionalErrors([violation(), violation({ pointer: '/spiceLevel' })])
    expect(errors.map((error) => error.instancePath)).toEqual(['/toppings/1', '/spiceLevel'])
  })
})

describe('formLevelViolations', () => {
  const known = ['toppings', 'spiceLevel']

  it('keeps violations whose field is not in the schema', () => {
    // sh:closed names a field the schema does not declare, so no control can display it.
    const orphan = violation({ field: 'secretDiscount', pointer: '/secretDiscount' })
    expect(formLevelViolations([orphan], known)).toEqual([orphan])
  })

  it('keeps violations reported against the order as a whole', () => {
    const rootLevel = violation({ field: null, pointer: '' })
    expect(formLevelViolations([rootLevel], known)).toEqual([rootLevel])
  })

  it('drops violations a control will already show', () => {
    expect(formLevelViolations([violation()], known)).toEqual([])
  })
})
