/**
 * The running order summary: what has been chosen, what each choice costs, and the total.
 *
 * Sticky beside the form on a wide screen and pinned to the bottom of the viewport on a narrow
 * one, so the price is visible the whole time someone is customising rather than only once they
 * scroll to the end.
 *
 * Every line comes from the `pricing` block and the schema titles the server sent. No dish and
 * no field is named here, so a new dish gets a correct summary with nothing added.
 */

import type { FormDefinition } from './api'
import { summarise } from './pricing'
import { useUi } from './ui-context'

interface Props {
  definition: FormDefinition
  data: Record<string, unknown>
  submitting: boolean
  problemCount: number
  onSubmit: () => void
}

export function OrderSummary({ definition, data, submitting, problemCount, onSubmit }: Props) {
  const { t } = useUi()
  const summary = summarise(definition, data)
  const money = (amount: number) => `${amount.toFixed(2)} ${summary.currency}`

  return (
    <aside className="summary" aria-label={t('yourOrder')}>
      <div className="summary__card">
        <h3 className="summary__title">{t('yourOrder')}</h3>

        <dl className="summary__lines">
          <div className="summary__line">
            <dt>{definition.dish.name}</dt>
            <dd>{money(summary.basePrice)}</dd>
          </div>

          {summary.lines.map((line) => (
            <div className="summary__line summary__line--option" key={line.field}>
              <dt>
                <span className="summary__field">{line.fieldLabel}</span>
                <span className="summary__option">{line.optionLabel}</span>
              </dt>
              <dd className={line.amount === 0 ? 'summary__included' : undefined}>
                {line.amount === 0 ? t('included') : `+${money(line.amount)}`}
              </dd>
            </div>
          ))}

          {summary.multiplier > 1 && (
            <div className="summary__line summary__line--multiplier">
              <dt>
                {summary.multiplierLabel} × {summary.multiplier}
              </dt>
              <dd>{money(summary.subtotal)}</dd>
            </div>
          )}
        </dl>

        <p className="summary__total">
          <span className="summary__total-label" id="summary-total-label">
            {t('estimatedTotal')}
          </span>
          {/* <output> is the element for the result of a calculation: it has an implicit
              `status` role, so a screen reader announces the price as choices change. */}
          <output className="summary__total-value" aria-labelledby="summary-total-label">
            {money(summary.total)}
          </output>
        </p>

        <button
          type="button"
          className="button button--primary summary__submit"
          onClick={onSubmit}
          disabled={submitting}
        >
          {submitting ? t('checking') : t('placeOrder')}
        </button>

        {problemCount > 0 && (
          <p className="summary__problems">{t('problemsShort', { n: problemCount })}</p>
        )}

        <p className="summary__caveat">{t('priceEstimate')}</p>
      </div>
    </aside>
  )
}
