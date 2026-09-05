/**
 * Renders one dish's order form.
 *
 * The component takes a slug and nothing else. Every field, label, option, default, group and
 * hint comes from the schema pair the server generated from that dish's SHACL shape. There is
 * no branch on which dish this is, and adding a dish to the backend changes nothing here.
 */

import { JsonForms } from '@jsonforms/react'
import {
  vanillaCells,
  vanillaRenderers,
  vanillaStyles,
  JsonFormsStyleContext,
} from '@jsonforms/vanilla-renderers'
import { useCallback, useEffect, useMemo, useState } from 'react'

import { ApiError, getForm, submitOrder } from './api'
import type { FormDefinition, OrderReceipt, Violation } from './api'
import { formLevelViolations, toAdditionalErrors } from './violations'

const renderers = [...vanillaRenderers]

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
  const [definition, setDefinition] = useState<FormDefinition | null>(null)
  const [data, setData] = useState<Record<string, unknown>>({})
  const [violations, setViolations] = useState<Violation[]>([])
  const [status, setStatus] = useState<Status>({ kind: 'loading' })

  // `App` mounts this component with `key={slug}`, so a different dish is a fresh mount with
  // fresh state rather than a component that has to reset itself. That is why the effect body
  // sets no state synchronously: there is nothing stale to clear.
  useEffect(() => {
    let cancelled = false

    getForm(slug)
      .then((loaded) => {
        if (cancelled) return
        setDefinition(loaded)
        // JSON Forms applies `default` from the schema itself, so starting from an empty object
        // is correct: the sh:defaultValue in the shape is what pre-fills the form.
        setStatus({ kind: 'ready' })
      })
      .catch((error: unknown) => {
        if (cancelled) return
        const problem = error instanceof ApiError ? error.problem : null
        setStatus({
          kind: 'failed',
          title: problem?.title ?? 'Could not load the form',
          detail: problem?.detail ?? 'The server did not return a form for this dish.',
        })
      })

    return () => {
      cancelled = true
    }
  }, [slug])

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
      const receipt = await submitOrder(slug, data)
      setStatus({ kind: 'accepted', receipt })
    } catch (error: unknown) {
      if (error instanceof ApiError && error.violations.length > 0) {
        // The server is the authority. Its violations are shown as-is; nothing is re-checked
        // or re-worded here, so the message the user reads is the one the shape declares.
        setViolations(error.violations)
        setStatus({ kind: 'ready' })
        return
      }
      const problem = error instanceof ApiError ? error.problem : null
      setStatus({
        kind: 'failed',
        title: problem?.title ?? 'Could not submit the order',
        detail: problem?.detail ?? 'Something went wrong. Please try again.',
      })
    }
  }, [data, slug])

  if (status.kind === 'loading') {
    return <p className="notice">Loading the form for {slug}…</p>
  }

  if (status.kind === 'failed') {
    return (
      <div className="notice notice--error" role="alert">
        <strong>{status.title}</strong>
        <p>{status.detail}</p>
      </div>
    )
  }

  if (status.kind === 'accepted') {
    return (
      <div className="receipt" role="status">
        <h2>Order accepted</h2>
        <p className="receipt__total">
          {status.receipt.total.toFixed(2)} {status.receipt.currency}
        </p>
        <p className="receipt__id">
          Reference <code>{status.receipt.orderId}</code>
        </p>
        <button type="button" onClick={() => setStatus({ kind: 'ready' })}>
          Order another
        </button>
      </div>
    )
  }

  if (!definition) return null

  return (
    <section className="dish-form" aria-label={`Order form for ${definition.dish.name}`}>
      <header className="dish-form__header">
        <h2>{definition.dish.name}</h2>
        <p>{definition.dish.description}</p>
        <p className="dish-form__meta">
          From {definition.dish.basePrice.toFixed(2)} {definition.dish.currency}
          {definition.dish.allergens.length > 0 && (
            <> · contains {definition.dish.allergens.join(', ')}</>
          )}
        </p>
      </header>

      {violations.length > 0 && (
        <div className="notice notice--error" role="alert">
          <strong>
            {violations.length} {violations.length === 1 ? 'problem' : 'problems'} with this order
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

      <button
        type="button"
        className="submit"
        onClick={() => void handleSubmit()}
        disabled={status.kind === 'submitting'}
      >
        {status.kind === 'submitting' ? 'Checking…' : 'Place order'}
      </button>

      <p className="dish-form__provenance">
        Generated from <code>{definition.shapeIri.split('#').pop()}</code>. Validation runs on the
        server against that SHACL shape.
      </p>
    </section>
  )
}
