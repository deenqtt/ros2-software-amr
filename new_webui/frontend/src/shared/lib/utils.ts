import { clsx, type ClassValue } from 'clsx'
import { extendTailwindMerge } from 'tailwind-merge'

/**
 * tailwind-merge does not read tailwind.config, so it takes `text-body-sm` for
 * a text colour and drops the `text-on-primary` before it — every primary
 * button lost its white label. Naming the custom font sizes fixes that.
 */
const twMerge = extendTailwindMerge({
  extend: {
    classGroups: {
      'font-size': [
        {
          text: [
            'display-sm',
            'title-lg',
            'title-md',
            'title-sm',
            'body-md',
            'body-sm',
            'caption',
            'label',
            'number-lg',
            'number-md',
            'number-sm',
          ],
        },
      ],
    },
  },
})

export function cn(...inputs: ClassValue[]): string {
  return twMerge(clsx(inputs))
}

/** Fixed-decimal formatter that renders a placeholder instead of NaN. */
export function formatNumber(value: number | null | undefined, digits = 2, fallback = '—'): string {
  if (value === null || value === undefined || !Number.isFinite(value)) return fallback
  return value.toFixed(digits)
}

export function formatPercent(value: number | null | undefined, fallback = '—'): string {
  if (value === null || value === undefined || !Number.isFinite(value)) return fallback
  return `${Math.round(value)}%`
}
