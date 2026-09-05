/**
 * Bounded integers, rendered as a stepper or a labelled slider.
 *
 * Both apply to any integer with `minimum` and `maximum` in the schema - which the translator
 * derived from `sh:minInclusive`/`sh:maxInclusive`. Quantity becomes a stepper; a 0-5 range like
 * spice level becomes a slider with its endpoints shown, because the useful thing about it is
 * the position on the scale rather than the number.
 *
 * Neither knows a field name. The stepper's buttons clamp to the bounds, so the common way to
 * produce an invalid value is simply unavailable - while the server still decides.
 */

import type { ControlProps, RankedTester } from '@jsonforms/core'
import { and, rankWith, schemaMatches, uiTypeIs } from '@jsonforms/core'
import { withJsonFormsControlProps } from '@jsonforms/react'

/** A range no wider than this reads better as a slider than as a spinner. */
const SLIDER_MAX_SPAN = 10

interface Bounds {
  minimum: number
  maximum: number
}

function boundsOf(schema: unknown): Bounds {
  const { minimum = 0, maximum = 99 } = (schema ?? {}) as Partial<Bounds>
  return { minimum, maximum }
}

export function BoundedIntegerControl({
  data,
  handleChange,
  path,
  label,
  description,
  schema,
  errors,
  visible,
  enabled,
  required,
}: ControlProps) {
  const { minimum, maximum } = boundsOf(schema)
  // A scale starts at zero; a count starts at one. Spice level 0-5 is an intensity, and its
  // useful property is the position on the scale, so it gets a slider. Quantity 1-10 is a
  // count, so it gets a stepper. Both facts come from `minimum` in the schema, which the
  // translator derived from sh:minInclusive - not from either field's name.
  const asSlider = maximum - minimum <= SLIDER_MAX_SPAN && minimum === 0
  const current = typeof data === 'number' ? data : (schema as { default?: number })?.default
  const invalid = Boolean(errors)

  if (!visible) return null

  const clamp = (value: number) => Math.min(maximum, Math.max(minimum, value))
  const value = typeof current === 'number' ? current : minimum

  return (
    <div className={`field field--number${invalid ? ' field--invalid' : ''}`}>
      <div className="field__head">
        <label className="field__label" htmlFor={`${path}-input`}>
          {label}
          {required && <span className="field__required"> *</span>}
        </label>
        {asSlider && <span className="field__counter">{value}</span>}
      </div>

      {description && <p className="field__hint">{description}</p>}

      {asSlider ? (
        <div className="slider">
          <span className="slider__end" aria-hidden="true">
            {minimum}
          </span>
          <input
            id={`${path}-input`}
            type="range"
            min={minimum}
            max={maximum}
            step={1}
            value={value}
            disabled={!enabled}
            onChange={(event) => handleChange(path, Number(event.target.value))}
          />
          <span className="slider__end" aria-hidden="true">
            {maximum}
          </span>
        </div>
      ) : (
        <div className="stepper">
          <button
            type="button"
            className="stepper__button"
            aria-label="-"
            disabled={!enabled || value <= minimum}
            onClick={() => handleChange(path, clamp(value - 1))}
          >
            −
          </button>
          <input
            id={`${path}-input`}
            className="stepper__value"
            type="number"
            inputMode="numeric"
            min={minimum}
            max={maximum}
            value={typeof current === 'number' ? current : ''}
            disabled={!enabled}
            onChange={(event) => {
              const next = event.target.value
              handleChange(path, next === '' ? undefined : Number(next))
            }}
          />
          <button
            type="button"
            className="stepper__button"
            aria-label="+"
            disabled={!enabled || value >= maximum}
            onClick={() => handleChange(path, clamp(value + 1))}
          >
            +
          </button>
        </div>
      )}

      {invalid && <p className="field__error">{errors}</p>}
    </div>
  )
}

export const boundedIntegerTester: RankedTester = rankWith(
  10,
  and(
    uiTypeIs('Control'),
    schemaMatches(
      (schema) =>
        schema?.type === 'integer' &&
        typeof schema.minimum === 'number' &&
        typeof schema.maximum === 'number',
    ),
  ),
)

export const BoundedInteger = withJsonFormsControlProps(BoundedIntegerControl)
