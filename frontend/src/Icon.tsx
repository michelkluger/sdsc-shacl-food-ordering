/**
 * Inline SVG icons.
 *
 * These replace the Unicode glyphs the UI used to use. `☀` (U+2600) has an emoji presentation,
 * so Windows and Chrome render it through Segoe UI Emoji as a full-colour **orange** sun -
 * which put a colour from nowhere into a masthead built on SDSC indigo. Text glyphs cannot be
 * relied on to stay monochrome, and a variation selector only asks nicely.
 *
 * Every icon here draws with `currentColor` and sizes to `1em`, so it takes the colour and
 * scale of whatever it sits in and follows the theme automatically.
 */

interface IconProps {
  /** Icons are decorative here: the accessible name is always on the button that holds them. */
  className?: string
}

/** Every icon in this file has the same shape, so callers can hold one in a lookup table. */
export type IconComponent = (props: IconProps) => React.JSX.Element

const base = {
  width: '1em',
  height: '1em',
  viewBox: '0 0 24 24',
  fill: 'none',
  stroke: 'currentColor',
  strokeWidth: 2,
  strokeLinecap: 'round' as const,
  strokeLinejoin: 'round' as const,
  'aria-hidden': true,
  focusable: false,
}

export function SunIcon({ className }: IconProps) {
  return (
    <svg {...base} className={className}>
      <circle cx="12" cy="12" r="4" />
      <path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4" />
    </svg>
  )
}

export function MoonIcon({ className }: IconProps) {
  return (
    <svg {...base} className={className}>
      <path d="M21 12.8A9 9 0 1 1 11.2 3a7 7 0 0 0 9.8 9.8Z" />
    </svg>
  )
}

/** Half-filled circle: "follow whatever the system is doing". */
export function ContrastIcon({ className }: IconProps) {
  return (
    <svg {...base} className={className}>
      <circle cx="12" cy="12" r="9" />
      <path d="M12 3a9 9 0 0 1 0 18Z" fill="currentColor" stroke="none" />
    </svg>
  )
}

export function CheckIcon({ className }: IconProps) {
  return (
    <svg {...base} className={className}>
      <path d="m5 12.5 4.5 4.5L19 7.5" />
    </svg>
  )
}

export function PlusIcon({ className }: IconProps) {
  return (
    <svg {...base} className={className}>
      <path d="M12 5v14M5 12h14" />
    </svg>
  )
}
