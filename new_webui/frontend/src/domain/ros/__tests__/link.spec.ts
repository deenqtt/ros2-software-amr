import { describe, expect, it } from 'vitest'
import { backoffCeiling, backoffDelay, deriveLinkState, linkAllowsCommands } from '../link'

describe('deriveLinkState', () => {
  const base = { muted: false, socketOpen: false, connecting: false, hasStaleTopic: false }

  it('reports offline when there is no socket', () => {
    expect(deriveLinkState(base)).toBe('offline')
  })

  it('reports connecting while the socket is being opened', () => {
    expect(deriveLinkState({ ...base, connecting: true })).toBe('connecting')
  })

  it('reports online when the socket is up and data is flowing', () => {
    expect(deriveLinkState({ ...base, socketOpen: true })).toBe('online')
  })

  it('reports stale when the socket is up but a periodic topic went quiet', () => {
    // The failure a boolean cannot express: rosbridge answers, the stack
    // behind it is dead, and the old UI called that "connected".
    expect(deriveLinkState({ ...base, socketOpen: true, hasStaleTopic: true })).toBe('stale')
  })

  it('lets mute win over every other signal', () => {
    expect(
      deriveLinkState({ muted: true, socketOpen: true, connecting: true, hasStaleTopic: true }),
    ).toBe('muted')
    expect(deriveLinkState({ ...base, muted: true })).toBe('muted')
  })
})

describe('linkAllowsCommands', () => {
  it('permits commands only on a healthy link', () => {
    expect(linkAllowsCommands('online')).toBe(true)
    // Stale means we cannot see the robot. Sending it somewhere blind is worse
    // than refusing.
    expect(linkAllowsCommands('stale')).toBe(false)
    expect(linkAllowsCommands('connecting')).toBe(false)
    expect(linkAllowsCommands('offline')).toBe(false)
    expect(linkAllowsCommands('muted')).toBe(false)
  })
})

describe('backoffDelay', () => {
  const noJitter = { jitter: 0 }

  it('grows exponentially from the base', () => {
    expect(backoffDelay(1, noJitter)).toBe(1000)
    expect(backoffDelay(2, noJitter)).toBe(2000)
    expect(backoffDelay(3, noJitter)).toBe(4000)
    expect(backoffDelay(4, noJitter)).toBe(8000)
  })

  it('caps at the maximum', () => {
    expect(backoffDelay(99, noJitter)).toBe(30_000)
  })

  it('returns zero for a nonsense attempt number', () => {
    expect(backoffDelay(0)).toBe(0)
    expect(backoffDelay(-3)).toBe(0)
  })

  it('spreads retries so a fleet does not reconnect in lockstep', () => {
    // One network blip drops every robot at once; without jitter they all
    // retry in the same millisecond, forever.
    const lowest = backoffDelay(3, { jitter: 0.25 }, () => 0)
    const highest = backoffDelay(3, { jitter: 0.25 }, () => 0.999999)
    expect(lowest).toBe(3000)
    expect(highest).toBe(5000)
    expect(highest - lowest).toBeGreaterThan(0)
  })

  it('never returns a negative delay', () => {
    expect(backoffDelay(1, { jitter: 2 }, () => 0)).toBe(0)
  })

  it('states its own ceiling', () => {
    expect(backoffCeiling()).toBe(37_500)
  })
})
