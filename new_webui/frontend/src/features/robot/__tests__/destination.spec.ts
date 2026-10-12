import { describe, expect, it } from 'vitest'
import { destinationOptions } from '../destination'

const keepout = {
  kind: 'keepout' as const,
  enabled: true,
  name: 'Switchboard',
  polygon: [
    [0, 0],
    [2, 0],
    [2, 2],
    [0, 2],
  ] as [number, number][],
}

const station = (id: string, name: string, x: number, y: number) => ({
  id,
  name,
  type: 'charging' as const,
  x,
  y,
})

describe('destinationOptions', () => {
  it('lists every station by name, in order', () => {
    const options = destinationOptions(
      [station('b', 'Line 2', 5, 5), station('a', 'Dock A', 6, 6)],
      [],
    )
    expect(options.map((option) => option.label)).toEqual(['Dock A', 'Line 2'])
    expect(options.every((option) => !option.disabled)).toBe(true)
  })

  it('keeps a station inside an active keep-out listed but not pickable', () => {
    const [inside] = destinationOptions([station('a', 'Panel bay', 1, 1)], [keepout])
    expect(inside?.disabled).toBe(true)
    expect(inside?.hint).toBe('inside keep-out "Switchboard"')
  })

  it('lets a station be picked once its keep-out is switched off', () => {
    const [inside] = destinationOptions(
      [station('a', 'Panel bay', 1, 1)],
      [{ ...keepout, enabled: false }],
    )
    expect(inside?.disabled).toBe(false)
  })
})
