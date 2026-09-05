/**
 * A multi-select for arrays of enumerated values, rendered as toggleable chips.
 *
 * This replaces the vanilla renderer's add-a-row list, which was the single worst thing about
 * the UI: picking three toppings meant three "add" clicks, each opening a dropdown, with the
 * cardinality limit only enforced after submitting.
 *
 * Everything it renders comes from the schema the server generated. It matches on *shape* -
 * an array whose items carry `oneOf` - and never on a field name, so it applies to ramen
 * toppings, tacos sauces and poke crunch alike, and to whatever a fourth dish declares.
 *
 * The cardinality bounds come from `maxItems`/`minItems`, which the translator derived from
 * `sh:maxCount`/`sh:minCount`. Reaching the maximum disables the unchosen chips rather than
 * hiding them, so the limit is visible before it is hit - but the server still decides, and a
 * request that gets past this is rejected by SHACL exactly as before.
 */

import type { ControlProps, RankedTester } from '@jsonforms/core'
import { and, isEnumSchema, rankWith, schemaMatches, uiTypeIs } from '@jsonforms/core'
import { withJsonFormsControlProps } from '@jsonforms/react'
import { useCallback, useMemo } from 'react'

import { CheckIcon, PlusIcon } from '../Icon'
import { useUi } from '../ui-context'

interface Option {
  const: string
  title?: string
}

function optionsOf(schema: unknown): Option[] {
  const items = (schema as { items?: { oneOf?: Option[]; enum?: string[] } })?.items
  if (items?.oneOf) return items.oneOf
  if (items?.enum) return items.enum.map((value) => ({ const: value, title: value }))
  return []
}

export function ChipMultiSelectControl({
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
  const selected = useMemo<string[]>(() => (Array.isArray(data) ? (data as string[]) : []), [data])
  const options = useMemo(() => optionsOf(schema), [schema])

  const maxItems = (schema as { maxItems?: number }).maxItems
  const minItems = (schema as { minItems?: number }).minItems
  const atLimit = maxItems !== undefined && selected.length >= maxItems

  const toggle = useCallback(
    (value: string) => {
      const next = selected.includes(value)
        ? selected.filter((item) => item !== value)
        : [...selected, value]
      // An empty array and an absent property mean the same thing to SHACL (sh:minCount 0),
      // but sending `undefined` keeps the payload minimal and matches what a fresh form sends.
      handleChange(path, next.length ? next : undefined)
    },
    [handleChange, path, selected],
  )

  if (!visible) return null

  const invalid = Boolean(errors)
  const counter =
    maxItems !== undefined
      ? t('chosenOf', { n: selected.length, max: maxItems })
      : selected.length
        ? t('chosenOf', { n: selected.length, max: options.length })
        : t('noneChosen')

  return (
    <div className={`field field--chips${invalid ? ' field--invalid' : ''}`}>
      <div className="field__head">
        <span className="field__label" id={`${path}-label`}>
          {label}
          {required && <span className="field__required"> *</span>}
        </span>
        <span className="field__counter">{counter}</span>
      </div>

      {description && <p className="field__hint">{description}</p>}

      <div className="chips" role="group" aria-labelledby={`${path}-label`}>
        {options.map((option) => {
          const isSelected = selected.includes(option.const)
          const isBlocked = !isSelected && atLimit
          return (
            <button
              key={option.const}
              type="button"
              className={`chip${isSelected ? ' chip--on' : ''}`}
              aria-pressed={isSelected}
              disabled={!enabled || isBlocked}
              // Explains *why* a chip is unavailable, rather than leaving it inertly greyed.
              title={isBlocked && maxItems ? t('atMost', { n: maxItems }) : undefined}
              onClick={() => toggle(option.const)}
            >
              <span className="chip__mark">
                {isSelected ? <CheckIcon /> : <PlusIcon />}
              </span>
              {option.title ?? option.const}
            </button>
          )
        })}
      </div>

      {selected.length > 0 && enabled && (
        <button type="button" className="field__action" onClick={() => handleChange(path, undefined)}>
          {t('clear')}
        </button>
      )}

      {invalid && <p className="field__error">{errors}</p>}
      {!invalid && minItems !== undefined && minItems > 0 && selected.length === 0 && (
        <p className="field__hint field__hint--quiet">{t('atLeast', { n: minItems })}</p>
      )}
    </div>
  )
}

/**
 * Ranked above the built-in array renderer so it wins for arrays of enumerated values, and no
 * higher, so anything else still falls through to JSON Forms' own renderers.
 */
export const chipMultiSelectTester: RankedTester = rankWith(
  10,
  and(
    uiTypeIs('Control'),
    schemaMatches((schema) => {
      if (schema?.type !== 'array') return false
      const items = schema.items as { oneOf?: unknown[]; enum?: unknown[] } | undefined
      return Boolean(items?.oneOf ?? items?.enum)
    }),
  ),
)

export const ChipMultiSelect = withJsonFormsControlProps(ChipMultiSelectControl)

// Re-exported so the registry file reads as a list of (tester, renderer) pairs.
export { isEnumSchema }
