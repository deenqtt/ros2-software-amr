import { describe, expect, it } from 'vitest'
import { missionsByStation } from '../stationUsage'

describe('missionsByStation', () => {
  it('lists every mission that names a station', () => {
    const usage = missionsByStation([
      { id: 'm1', name: 'Shuttle', stationIds: ['a', 'b'] },
      { id: 'm2', name: 'Loop', stationIds: ['b', 'c'] },
    ])
    expect(usage.get('b')?.map((m) => m.name)).toEqual(['Shuttle', 'Loop'])
    expect(usage.get('a')?.map((m) => m.name)).toEqual(['Shuttle'])
    expect(usage.has('d')).toBe(false)
  })

  it('counts a route that visits a station twice once', () => {
    const usage = missionsByStation([{ id: 'm1', name: 'Back and forth', stationIds: ['a', 'b', 'a'] }])
    expect(usage.get('a')).toHaveLength(1)
  })
})
