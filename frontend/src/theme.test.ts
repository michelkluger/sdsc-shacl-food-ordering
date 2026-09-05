/**
 * Theme selection.
 *
 * The behaviour worth pinning down is the three-state part: "system" has to survive as a real
 * choice, and an explicit choice has to beat the system preference in *both* directions. The
 * second half of that lives in CSS specificity, so `applyTheme` is tested on the attribute it
 * sets, which is what the stylesheet keys on.
 */

import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import {
  DEFAULT_THEME,
  THEMES,
  applyTheme,
  initialTheme,
  isTheme,
  rememberTheme,
  resolvesToDark,
} from './theme'

const root = () => document.documentElement

beforeEach(() => {
  localStorage.clear()
  root().removeAttribute('data-theme')
  root().style.colorScheme = ''
})

afterEach(() => {
  vi.restoreAllMocks()
})

describe('the set of themes', () => {
  it('offers system as a real choice, not only as the initial default', () => {
    // Without it, anyone who touches the toggle can never go back to following their OS.
    expect(THEMES).toContain('system')
    expect(DEFAULT_THEME).toBe('system')
  })

  it('recognises its own values and rejects anything else', () => {
    for (const theme of THEMES) expect(isTheme(theme)).toBe(true)
    for (const other of ['', 'sepia', 'DARK']) expect(isTheme(other)).toBe(false)
  })
})

describe('applyTheme', () => {
  it('stamps an explicit choice onto the root element', () => {
    applyTheme('dark')
    expect(root().getAttribute('data-theme')).toBe('dark')

    applyTheme('light')
    expect(root().getAttribute('data-theme')).toBe('light')
  })

  it('removes the attribute for system so the media query decides', () => {
    applyTheme('dark')
    applyTheme('system')
    expect(root().hasAttribute('data-theme')).toBe(false)
  })

  it('sets color-scheme so native controls and scrollbars follow', () => {
    applyTheme('dark')
    expect(root().style.colorScheme).toBe('dark')

    applyTheme('system')
    expect(root().style.colorScheme).toBe('light dark')
  })
})

describe('initialTheme', () => {
  it('follows the system when nothing has been chosen', () => {
    expect(initialTheme()).toBe('system')
  })

  it('restores a remembered choice', () => {
    rememberTheme('dark')
    expect(initialTheme()).toBe('dark')
  })

  it('ignores a stored value that is not a theme', () => {
    localStorage.setItem('food-api.theme', 'sepia')
    expect(initialTheme()).toBe('system')
  })

  it('falls back rather than throwing when storage is unavailable', () => {
    // Private browsing and blocked site data make these throw outright, and a remembered
    // preference is a convenience, never a requirement.
    vi.spyOn(Storage.prototype, 'getItem').mockImplementation(() => {
      throw new Error('SecurityError')
    })
    expect(initialTheme()).toBe('system')
  })

  it('applies the chosen theme even when it cannot be remembered', () => {
    vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => {
      throw new Error('QuotaExceededError')
    })
    expect(() => rememberTheme('dark')).not.toThrow()
  })
})

describe('resolvesToDark', () => {
  const withSystemDark = (dark: boolean) => {
    vi.stubGlobal(
      'matchMedia',
      vi.fn().mockReturnValue({ matches: dark, media: '(prefers-color-scheme: dark)' }),
    )
  }

  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('answers from the explicit choice regardless of the system', () => {
    withSystemDark(true)
    expect(resolvesToDark('light')).toBe(false)

    withSystemDark(false)
    expect(resolvesToDark('dark')).toBe(true)
  })

  it('defers to the system when following it', () => {
    withSystemDark(true)
    expect(resolvesToDark('system')).toBe(true)

    withSystemDark(false)
    expect(resolvesToDark('system')).toBe(false)
  })
})
