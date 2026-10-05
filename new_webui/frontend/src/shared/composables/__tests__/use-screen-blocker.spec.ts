import { afterEach, beforeEach, describe, expect, it } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import { useScreenBlocker } from '../useScreenBlocker'

function screenWidth(width: number) {
  window.matchMedia = ((query: string) => ({
    matches: width <= Number(/max-width:\s*(\d+)px/.exec(query)?.[1] ?? Infinity),
    media: query,
    onchange: null,
    addEventListener: () => {},
    removeEventListener: () => {},
    addListener: () => {},
    removeListener: () => {},
    dispatchEvent: () => false,
  })) as typeof window.matchMedia
}

describe('useScreenBlocker', () => {
  beforeEach(() => setActivePinia(createPinia()))
  afterEach(() => delete (window as { matchMedia?: unknown }).matchMedia)

  it('blocks the task on a phone and says why', () => {
    screenWidth(390)
    const { tooSmall, reason } = useScreenBlocker('Placing a station on the map')
    expect(tooSmall.value).toBe(true)
    expect(reason.value).toBe('Placing a station on the map needs a tablet or laptop.')
  })

  it.each([1366, 800])('lets the task through at %ipx', (width) => {
    screenWidth(width)
    const { tooSmall, reason } = useScreenBlocker('Drawing zones')
    expect(tooSmall.value).toBe(false)
    expect(reason.value).toBe('')
  })
})
