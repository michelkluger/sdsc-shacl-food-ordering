/**
 * A single-choice control rendered as a row of selectable cards.
 *
 * Applies to any scalar `oneOf` enumeration with a small number of options - a broth, a size, a
 * base. A dropdown hides the choices behind a click; when there are five of them and the whole
 * point of the page is choosing between them, showing them is better.
 *
 * Matched on shape, never on field name, so it applies to every dish's enumerations and to
 * whatever a new dish declares. Above the threshold it declines and JSON Forms falls back to
 * its own select, which is the right control for a long list.
 */

import type { ControlProps, RankedTester } from '@jsonforms/core'
import { and, rankWith, schemaMatches, uiTypeIs } from '@jsonforms/core'
import { withJsonFormsControlProps } from '@jsonforms/react'

import { useUi } from '../ui-context'

/** Above this many options, a dropdown is genuinely the better control. */
const MAX_CARDS = 6

interface Option {
  const: string
  title?: string
}

function optionsOf(schema: unknown): Option[] {
  const oneOf = (schema as { oneOf?: Option[] })?.oneOf
  if (oneOf) return oneOf
  const values = (schema as { enum?: string[] })?.enum
  return values ? values.map((value) => ({ const: value, title: value })) : []
}

export function OptionCardsControl({
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
  const { t } = useUi()
  const options = optionsOf(schema)
  const invalid = Boolean(errors)

  if (!visible) return null

  return (
    <div className={`field field--cards${invalid ? ' field--invalid' : ''}`}>
      <div className="field__head">
        <span className="field__label" id={`${path}-label`}>
          {label}
          {required && <span className="field__required"> *</span>}
        </span>
      </div>

      {description && <p className="field__hint">{description}</p>}

      <div className="option-cards" role="radiogroup" aria-labelledby={`${path}-label`}>
        {options.map((option) => {
          const isSelected = data === option.const
          return (
            <button
              key={option.const}
              type="button"
              role="radio"
              aria-checked={isSelected}
              disabled={!enabled}
              className={`option-card${isSelected ? ' option-card--on' : ''}`}
              // Re-clicking the chosen card clears it, so a user can undo a selection in an
              // optional field without reloading the form.
              onClick={() => handleChange(path, isSelected && !required ? undefined : option.const)}
            >
              {option.title ?? option.const}
            </button>
          )
        })}
      </div>

      {invalid && <p className="field__error">{errors}</p>}
      {!invalid && !required && <p className="field__hint field__hint--quiet">{t('optional')}</p>}
    </div>
  )
}

export const optionCardsTester: RankedTester = rankWith(
  10,
  and(
    uiTypeIs('Control'),
    schemaMatches((schema) => {
      if (schema?.type !== 'string') return false
      const oneOf = schema.oneOf as unknown[] | undefined
      const values = schema.enum as unknown[] | undefined
      const count = oneOf?.length ?? values?.length ?? 0
      return count > 0 && count <= MAX_CARDS
    }),
  ),
)

export const OptionCards = withJsonFormsControlProps(OptionCardsControl)
