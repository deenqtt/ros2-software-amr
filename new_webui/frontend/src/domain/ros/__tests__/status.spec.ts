import { describe, expect, it } from 'vitest'
import {
  acceptsNewCommand,
  activityFromStatusCode,
  activityStatus,
  batteryTone,
  connectionStatus,
  dockingStatus,
  isStale,
} from '../status'

describe('status mapping', () => {
  it('maps every RobotStatus code', () => {
    expect(activityFromStatusCode(0)).toBe('idle')
    expect(activityFromStatusCode(1)).toBe('navigating')
    expect(activityFromStatusCode(2)).toBe('docking')
    expect(activityFromStatusCode(3)).toBe('undocking')
    expect(activityFromStatusCode(4)).toBe('charging')
    expect(activityFromStatusCode(5)).toBe('error')
    expect(activityFromStatusCode(99)).toBe('idle')
  })

  it('gives a tone and a human label for every state', () => {
    expect(activityStatus('error')).toEqual({ tone: 'fault', label: 'Error' })
    // Not the old raw-enum rendering of "following waypoints".
    expect(activityStatus('waiting_confirm').label).toBe('Waiting for confirm')
    expect(dockingStatus('docked').tone).toBe('success')
    expect(connectionStatus('reconnecting').tone).toBe('warning')
  })
})

describe('acceptsNewCommand', () => {
  it('refuses while disconnected', () => {
    expect(acceptsNewCommand('disconnected', 'idle', 'idle')).toBe(false)
    expect(acceptsNewCommand('reconnecting', 'idle', 'idle')).toBe(false)
  })

  it('refuses while the robot is busy', () => {
    expect(acceptsNewCommand('connected', 'navigating', 'idle')).toBe(false)
    expect(acceptsNewCommand('connected', 'waiting_confirm', 'idle')).toBe(false)
    expect(acceptsNewCommand('connected', 'idle', 'docking')).toBe(false)
    expect(acceptsNewCommand('connected', 'idle', 'undocking')).toBe(false)
  })

  it('allows when connected and idle, or parked on a charger', () => {
    expect(acceptsNewCommand('connected', 'idle', 'idle')).toBe(true)
    expect(acceptsNewCommand('connected', 'charging', 'docked')).toBe(true)
  })
})

describe('batteryTone', () => {
  it('lets charging outrank level', () => {
    expect(batteryTone(5, true)).toBe('success')
  })

  it('escalates as the pack drains', () => {
    expect(batteryTone(null, false)).toBe('neutral')
    expect(batteryTone(80, false)).toBe('neutral')
    expect(batteryTone(35, false)).toBe('warning')
    expect(batteryTone(15, false)).toBe('warning')
    expect(batteryTone(8, false)).toBe('fault')
  })
})

describe('isStale', () => {
  it('treats a topic that never arrived as stale', () => {
    expect(isStale(undefined, 1000)).toBe(true)
  })

  it('compares against the budget', () => {
    const now = 10_000
    expect(isStale(9_500, 1000, now)).toBe(false)
    expect(isStale(8_000, 1000, now)).toBe(true)
  })
})
