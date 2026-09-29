import { clsx, type ClassValue } from 'clsx'
import { twMerge } from 'tailwind-merge'

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
