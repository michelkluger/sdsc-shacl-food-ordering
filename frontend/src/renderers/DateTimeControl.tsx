/**
 * Date-and-time fields, with a button that fills in the current moment.
 *
 * Matched on shape - a string whose schema `format` is `date-time`, which the translator derived
 * from `sh:datatype xsd:dateTime` - and never on a field name, so it applies to any dish that
 * declares a datetime property.
 *
 * Two things it fixes. A bare `datetime-local` input yields `2026-09-05T18:30`: no seconds and,
 * more importantly, no timezone, which for a *pickup* time is exactly the detail you do not want
 * ambiguous. This control stores a full offset-qualified ISO string instead. And typing a
 * timestamp by hand is miserable, so "Now" fills it in.
 */

import type { ControlProps, RankedTester } from '@jsonforms/core'
import { and, rankWith, schemaMatches, uiTypeIs } from '@jsonforms/core'
import { withJsonFormsControlProps } from '@jsonforms/react'
import { useCallback } from 'react'

import { useUi } from '../ui-context'

const pad = (value: number) => String(value).padStart(2, '0')

/** The browser's current UTC offset as `+02:00` / `-05:00`, which is what xsd:dateTime wants. */
function localOffset(date: Date): string {
  const minutes = -date.getTimezoneOffset()
  const sign = minutes >= 0 ? '+' : '-'
  const absolute = Math.abs(minutes)
  return `${sign}${pad(Math.floor(absolute / 60))}:${pad(absolute % 60)}`
}

/** `Date` -> `2026-09-05T18:30:00+02:00`, in local time. */
export function toIsoWithOffset(date: Date): string {
  const local =
    `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}` +
    `T${pad(date.getHours())}:${pad(date.getMinutes())}:${pad(date.getSeconds())}`
  return `${local}${localOffset(date)}`
}

/**
 * A stored ISO string -> the `YYYY-MM-DDTHH:mm` that `<input type="datetime-local">` requires.
 *
 * Returns an empty string for anything unparseable rather than throwing: the value may have been
 * typed by hand or arrived from elsewhere, and a broken input is better than a broken form.
 */
export function toInputValue(stored: unknown): string {
  if (typeof stored !== 'string' || !stored) return ''
  const parsed = new Date(stored)
  if (Number.isNaN(parsed.getTime())) return ''
  return (
    `${parsed.getFullYear()}-${pad(parsed.getMonth() + 1)}-${pad(parsed.getDate())}` +
    `T${pad(parsed.getHours())}:${pad(parsed.getMinutes())}`
  )
}

export function DateTimeControlBase({
  data,
  handleChange,
  path,
  label,
  description,
  errors,
  visible,
  enabled,
  required,
}: ControlProps) {
  const { t } = useUi()
  const invalid = Boolean(errors)

  const setNow = useCallback(() => {
    handleChange(path, toIsoWithOffset(new Date()))
  }, [handleChange, path])

  const onInput = useCallback(
    (value: string) => {
      if (!value) {
        // An empty optional field means "absent", not "empty string" - which would fail the
        // datatype constraint rather than being ignored.
        handleChange(path, undefined)
        return
      }
      const parsed = new Date(value)
      handleChange(path, Number.isNaN(parsed.getTime()) ? value : toIsoWithOffset(parsed))
    },
    [handleChange, path],
  )

  if (!visible) return null

  return (
    <div className={`field field--datetime${invalid ? ' field--invalid' : ''}`}>
      <div className="field__head">
        <label className="field__label" htmlFor={`${path}-input`}>
          {label}
          {required && <span className="field__required"> *</span>}
        </label>
      </div>

      {description && <p className="field__hint">{description}</p>}

      <div className="datetime">
        <input
          id={`${path}-input`}
          type="datetime-local"
          value={toInputValue(data)}
          disabled={!enabled}
          onChange={(event) => onInput(event.target.value)}
        />
        <button type="button" className="datetime__now" disabled={!enabled} onClick={setNow}>
          {t('now')}
        </button>
        {typeof data === 'string' && data !== '' && enabled && (
          <button
            type="button"
            className="datetime__clear"
            onClick={() => handleChange(path, undefined)}
          >
            {t('clear')}
          </button>
        )}
      </div>

      {invalid && <p className="field__error">{errors}</p>}
      {!invalid && !required && <p className="field__hint field__hint--quiet">{t('optional')}</p>}
    </div>
  )
}

export const dateTimeTester: RankedTester = rankWith(
  10,
  and(
    uiTypeIs('Control'),
    schemaMatches((schema) => schema?.type === 'string' && schema.format === 'date-time'),
  ),
)

export const DateTimeControl = withJsonFormsControlProps(DateTimeControlBase)
