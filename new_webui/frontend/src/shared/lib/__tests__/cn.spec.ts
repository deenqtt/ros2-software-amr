import { describe, expect, it } from 'vitest'
import { cn } from '../utils'

describe('cn', () => {
  it('keeps a text colour next to a custom font size', () => {
    expect(cn('text-on-primary', 'text-body-sm')).toBe('text-on-primary text-body-sm')
  })

  it('still lets a later font size replace an earlier one', () => {
    expect(cn('text-body-md', 'text-body-sm')).toBe('text-body-sm')
  })
})
