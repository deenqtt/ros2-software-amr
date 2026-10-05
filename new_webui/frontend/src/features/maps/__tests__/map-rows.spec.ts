import { describe, expect, it } from 'vitest'
import { robotsSummary } from '../mapRows'

describe('robotsSummary', () => {
  it('names two robots and counts the rest', () => {
    expect(robotsSummary(['R1', 'R2', 'R3'])).toBe('R1, R2 +1')
    expect(robotsSummary(['R1', 'R2', 'R3', 'R4'])).toBe('R1, R2 +2')
  })

  it('names a lone robot without a count', () => {
    expect(robotsSummary(['R1'])).toBe('R1')
    expect(robotsSummary(['R1', 'R2'])).toBe('R1, R2')
  })

  it('says so when no robot runs the map', () => {
    expect(robotsSummary([])).toBe('Not on any robot')
  })

  it('honours a different number shown', () => {
    expect(robotsSummary(['R1', 'R2', 'R3'], 1)).toBe('R1 +2')
  })
})
