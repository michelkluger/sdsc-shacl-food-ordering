/**
 * Light, dark, or whatever the system says.
 *
 * Three states rather than two. "System" has to be a real, selectable option and not just the
 * initial default, because otherwise a person who follows their OS theme has no way back once
 * they have touched the toggle.
 *
 * The choice is written to `data-theme` on the root element, which the stylesheet keys on:
 *
 *   :root                                     light tokens
 *   :root:not([data-theme='light']) @media dark   dark, when the system asks and the user
 *                                                 has not explicitly chosen light
 *   :root[data-theme='dark']                  dark, chosen explicitly
 *
 * With `system` selected the attribute is removed entirely, so the media query decides.
 */

export const THEMES = ['system', 'light', 'dark'] as const

export type Theme = (typeof THEMES)[number]

export const DEFAULT_THEME: Theme = 'system'

const STORAGE_KEY = 'food-api.theme'

export function isTheme(value: string): value is Theme {
  return (THEMES as readonly string[]).includes(value)
}

/**
 * The theme to start in: a previous explicit choice, else follow the system.
 *
 * Storage access is wrapped because it throws outright in some privacy modes, and a remembered
 * preference is a convenience rather than a requirement.
 */
export function initialTheme(): Theme {
  try {
    const stored = localStorage.getItem(STORAGE_KEY)
    if (stored && isTheme(stored)) return stored
  } catch {
    // Private browsing, or site data blocked. Follow the system.
  }
  return DEFAULT_THEME
}

export function rememberTheme(theme: Theme): void {
  try {
    localStorage.setItem(STORAGE_KEY, theme)
  } catch {
    // Not being able to remember the choice must not stop it applying now.
  }
}

/** Apply a theme to the document. `system` removes the attribute so the media query decides. */
export function applyTheme(theme: Theme): void {
  const root = document.documentElement
  if (theme === 'system') {
    root.removeAttribute('data-theme')
  } else {
    root.setAttribute('data-theme', theme)
  }

  // Tells the browser to paint form controls, scrollbars and the address bar to match, which
  // the CSS tokens alone cannot do.
  root.style.colorScheme = theme === 'system' ? 'light dark' : theme
}

/** True when the given theme resolves to dark right now, following the system if need be. */
export function resolvesToDark(theme: Theme): boolean {
  if (theme === 'dark') return true
  if (theme === 'light') return false
  return typeof matchMedia === 'function' && matchMedia('(prefers-color-scheme: dark)').matches
}
