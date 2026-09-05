/**
 * The renderer registry.
 *
 * Each entry is a (tester, renderer) pair. Every tester matches on the *shape* of the schema -
 * an array of enumerated values, a bounded integer, a short enumeration - and none of them
 * matches on a field name. That is what keeps the "no dish-specific frontend logic" property
 * true while still producing controls appropriate to each kind of constraint.
 *
 * The vanilla renderers stay in the list, at their own lower ranks, so anything these do not
 * claim still renders.
 */

import { vanillaRenderers } from '@jsonforms/vanilla-renderers'
import type { JsonFormsRendererRegistryEntry } from '@jsonforms/core'

import { ChipMultiSelect, chipMultiSelectTester } from './ChipMultiSelect'
import { OptionCards, optionCardsTester } from './OptionCards'
import { BoundedInteger, boundedIntegerTester } from './StepperControl'

export const renderers: JsonFormsRendererRegistryEntry[] = [
  ...vanillaRenderers,
  { tester: chipMultiSelectTester, renderer: ChipMultiSelect },
  { tester: optionCardsTester, renderer: OptionCards },
  { tester: boundedIntegerTester, renderer: BoundedInteger },
]
