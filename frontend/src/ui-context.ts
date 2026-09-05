/**
 * The UI language, shared with the custom renderers.
 *
 * JSON Forms constructs renderers itself, so props cannot be threaded down to them. A context is
 * the way to give them the handful of chrome strings they need ("Clear", "3 of 5 chosen") while
 * everything about the *dish* still arrives from the server inside the schema.
 */

import { createContext, useContext } from 'react'

import { DEFAULT_LANGUAGE, translator } from './i18n'
import type { Language, Translate } from './i18n'

export interface UiContextValue {
  language: Language
  t: Translate
}

export const UiContext = createContext<UiContextValue>({
  language: DEFAULT_LANGUAGE,
  t: translator(DEFAULT_LANGUAGE),
})

export const useUi = (): UiContextValue => useContext(UiContext)
