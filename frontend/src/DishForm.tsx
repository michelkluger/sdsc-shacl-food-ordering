/**
 * Renders one dish's order form.
 *
 * The component takes a slug and nothing else. Every field, label, option,
 * default, group and hint comes from the schema pair the server generated from that dish's
 * SHACL shape, in that language. There is no branch on which dish this is, and adding a dish or
 * a language to the backend changes nothing here.
 */

import { JsonForms } from '@jsonforms/react'
import { vanillaCells, JsonFormsStyleContext } from '@jsonforms/vanilla-renderers'
import { vanillaStyles } from '@jsonforms/vanilla-renderers'
import { useCallback, useEffect, useMemo, useState } from 'react'

import { ApiError, getForm, submitOrder } from './api'
import type { FormDefinition, OrderReceipt, Violation } from './api'
import { renderers } from './renderers'
import { useUi } from './ui-context'
import { estimateTotal } from './pricing'
import { formLevelViolations, toAdditionalErrors } from './violations'

interface Props {
  slug: string
}

type Status =
  | { kind: 'loading' }
  | { kind: 'ready' }
  | { kind: 'submitting' }
  | { kind: 'accepted'; receipt: OrderReceipt }
  | { kind: 'failed'; title: string; detail: string }

export function DishForm({ slug }: Props) {
  // Language comes from context rather than a prop so there is exactly one source for it: the
  // chrome strings and the language asked of the server can never disagree.
  const { t, language } = useUi()
  const [definition, setDefinition] = useState<FormDefinition | null>(null)
  const [data, setData] = useState<Record<string, unknown>>({})
  const [violations, setViolations] = useState<Violation[]>([])
  const [status, setStatus] = useState<Status>({ kind: 'loading' })

  // `App` mounts this with `key={slug}`, so switching dish is a fresh mount with fresh state
  // rather than a component resetting itself. Switching *language* deliberately is not: the
  // JSON keys are identical across languages, so the answers already filled in stay valid and
  // are carried over. That is the whole point of keeping the wire contract language-independent.
  useEffect(() => {
    let cancelled = false

    getForm(slug, language)
      .then((loaded) => {
        if (cancelled) return
        setDefinition(loaded)
        setStatus((current) => (current.kind === 'accepted' ? current : { kind: 'ready' }))
      })
      .catch((error: unknown) => {
        if (cancelled) return
        const problem = error instanceof ApiError ? error.problem : null
        setStatus({
          kind: 'failed',
          title: problem?.title ?? t('formFailed'),
          detail: problem?.detail ?? t('apiUnreachable'),
        })
      })

    return () => {
      cancelled = true
    }
  }, [slug, language, t])

  const schemaProperties = useMemo(
    () => Object.keys((definition?.schema as { properties?: object })?.properties ?? {}),
    [definition],
  )
  const additionalErrors = useMemo(() => toAdditionalErrors(violations), [violations])
  const orphanViolations = useMemo(
    () => formLevelViolations(violations, schemaProperties),
    [violations, schemaProperties],
  )

  const handleSubmit = useCallback(async () => {
    setStatus({ kind: 'submitting' })
    setViolations([])
    try {
      const receipt = await submitOrder(slug, data, language)
      setStatus({ kind: 'accepted', receipt })
    } catch (error: unknown) {
      if (error instanceof ApiError && error.violations.length > 0) {
        // The server is the authority. Its violations are shown as-is; nothing is re-checked or
        // re-worded here, so what the user reads is what the shape declares, in their language.
        setViolations(error.violations)
        setStatus({ kind: 'ready' })
        // Bring the first problem into view rather than leaving the user to hunt for it.
        // Feature-detected: `scrollIntoView` is absent in jsdom and in some older browsers, and
        // this runs inside a requestAnimationFrame callback where a throw is unhandled and
        // invisible. Scrolling is a nicety; failing to scroll must not break submission.
        requestAnimationFrame(() => {
          const target = document.querySelector('.field--invalid')
          if (target && typeof target.scrollIntoView === 'function') {
            target.scrollIntoView({ behavior: 'smooth', block: 'center' })
          }
        })
        return
      }
      const problem = error instanceof ApiError ? error.problem : null
      setStatus({
        kind: 'failed',
        title: problem?.title ?? t('formFailed'),
        detail: problem?.detail ?? t('apiUnreachable'),
      })
    }
  }, [data, slug, language, t])

  if (status.kind === 'loading') {
    return (
      <section className="panel panel--placeholder" aria-busy="true">
        <span className="spinner" aria-hidden="true" />
        {t('loadingForm')}
      </section>
    )
  }

  if (status.kind === 'failed') {
    return (
      <section className="panel notice notice--error" role="alert">
        <strong>{status.title}</strong>
        <p>{status.detail}</p>
      </section>
    )
  }

  if (status.kind === 'accepted') {
    return (
      <section className="panel receipt" role="status">
        <span className="receipt__tick" aria-hidden="true">
          ✓
        </span>
        <h2>{t('orderAccepted')}</h2>
        <p className="receipt__dish">{status.receipt.dishName}</p>
        <p className="receipt__total">
          {status.receipt.total.toFixed(2)} {status.receipt.currency}
        </p>
        <p className="receipt__id">
          {t('reference')} <code>{status.receipt.orderId.replace('urn:food:order:', '')}</code>
        </p>
        <button type="button" className="button button--ghost" onClick={() => setStatus({ kind: 'ready' })}>
          {t('orderAnother')}
        </button>
      </section>
    )
  }

  if (!definition) return null

  const estimate = estimateTotal(definition, data)
  const problemCount = violations.length

  return (
    <section className="panel dish-form" aria-label={definition.dish.name}>
      <header className="dish-form__header">
        <h2>{definition.dish.name}</h2>
        <p className="dish-form__description">{definition.dish.description}</p>
        {definition.dish.allergens.length > 0 && (
          <p className="dish-form__allergens">
            {t('contains')} {definition.dish.allergens.join(' · ')}
          </p>
        )}
      </header>

      {problemCount > 0 && (
        <div className="notice notice--error" role="alert">
          <strong>
            {problemCount === 1 ? t('problemsOne') : t('problemsMany', { n: problemCount })}
          </strong>
          {orphanViolations.length > 0 && (
            <ul>
              {orphanViolations.map((violation, index) => (
                <li key={`${violation.pointer}-${index}`}>{violation.message}</li>
              ))}
            </ul>
          )}
        </div>
      )}

      <JsonFormsStyleContext.Provider value={{ styles: vanillaStyles }}>
        <JsonForms
          schema={definition.schema}
          uischema={definition.uischema}
          data={data}
          renderers={renderers}
          cells={vanillaCells}
          additionalErrors={additionalErrors}
          onChange={({ data: next }) => setData(next as Record<string, unknown>)}
        />
      </JsonFormsStyleContext.Provider>

      <footer className="dish-form__footer">
        <div className="dish-form__total">
          <span className="dish-form__total-label">{t('estimatedTotal')}</span>
          <span className="dish-form__total-value">
            {estimate.toFixed(2)} {definition.dish.currency}
          </span>
        </div>
        <button
          type="button"
          className="button button--primary"
          onClick={() => void handleSubmit()}
          disabled={status.kind === 'submitting'}
        >
          {status.kind === 'submitting' ? t('checking') : t('placeOrder')}
        </button>
      </footer>

      <p className="provenance">
        {t('generatedFrom')} <code>{definition.shapeIri.split('#').pop()}</code>.{' '}
        {t('validatedOnServer')}
      </p>
    </section>
  )
}
