import { describe, expect, it } from 'vitest'
import { alarmAge, alarmTime } from '../alarmTime'
import { linkTransition } from '@/app/linkAlarms'

const NOW = new Date(2026, 9, 2, 10, 30, 0).getTime()

describe('alarmTime', () => {
  it('shows the time alone for today', () => {
    expect(alarmTime(new Date(2026, 9, 2, 9, 5, 7).getTime(), NOW)).toBe('09:05:07')
  })

  it('names yesterday', () => {
    expect(alarmTime(new Date(2026, 9, 1, 23, 59, 0).getTime(), NOW)).toBe('Yesterday 23:59:00')
  })

  it('gives a date for anything older', () => {
    expect(alarmTime(new Date(2026, 8, 28, 14, 20, 0).getTime(), NOW)).toBe('28 Sep 14:20:00')
  })

  it('says how long ago, coarsely', () => {
    expect(alarmAge(NOW - 10_000, NOW)).toBe('just now')
    expect(alarmAge(NOW - 5 * 60_000, NOW)).toBe('5m ago')
    expect(alarmAge(NOW - 3 * 3_600_000, NOW)).toBe('3h ago')
  })
})

describe('linkTransition', () => {
  it('raises when a link that was up goes down', () => {
    expect(linkTransition('online', 'offline', false)).toBe('lost')
    expect(linkTransition('stale', 'offline', false)).toBe('lost')
  })

  it('stays quiet for a robot that was never up', () => {
    expect(linkTransition(undefined, 'offline', false)).toBeNull()
    expect(linkTransition('connecting', 'offline', false)).toBeNull()
  })

  it('raises once while the link keeps retrying', () => {
    expect(linkTransition('connecting', 'offline', true)).toBeNull()
  })

  it('says restored only after a loss was raised', () => {
    expect(linkTransition('connecting', 'online', true)).toBe('restored')
    expect(linkTransition('connecting', 'online', false)).toBeNull()
  })
})
