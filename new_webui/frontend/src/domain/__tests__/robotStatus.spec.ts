import { describe, expect, it } from 'vitest'
import {
  STATUS_FRESH_MS,
  robotStatusDescriptor,
  robotStatusLine,
} from '../robotStatus'

const REPORTED = '2026-10-16T08:00:00Z'

function fresh(nowOffsetMs = 0): number {
  return Date.parse(REPORTED) + nowOffsetMs
}

describe('robotStatusDescriptor', () => {
  it('gives every word a tone from the shared scale', () => {
    const expected = {
      parked: 'neutral',
      mapping: 'active',
      ready: 'neutral',
      on_mission: 'active',
      waiting_confirm: 'attention',
      charging: 'success',
      error: 'fault',
      paused: 'warning',
    } as const
    for (const [status, tone] of Object.entries(expected)) {
      expect(robotStatusDescriptor(status as never, REPORTED, fresh()).tone).toBe(tone)
    }
  })

  it('says what each word means in plain text', () => {
    expect(robotStatusDescriptor('on_mission', REPORTED, fresh()).label).toBe('On mission')
    expect(robotStatusDescriptor('waiting_confirm', REPORTED, fresh()).label).toBe(
      'Needs confirm',
    )
  })

  it('reads a robot that has never reported as unknown, not offline', () => {
    expect(robotStatusDescriptor(null, null, fresh())).toEqual({
      tone: 'neutral',
      label: 'No report yet',
      offline: true,
    })
    expect(robotStatusDescriptor('ready', null, fresh()).offline).toBe(true)
  })

  it('calls a robot offline once its report is past a few heartbeats', () => {
    const within = robotStatusDescriptor('ready', REPORTED, fresh(STATUS_FRESH_MS - 1))
    expect(within.offline).toBe(false)

    const gone = robotStatusDescriptor('ready', REPORTED, fresh(STATUS_FRESH_MS + 1))
    expect(gone).toEqual({ tone: 'warning', label: 'Offline', offline: true })
  })

  it('reads a registry stamp that carries no zone as UTC', () => {
    // The format the backend actually sends: SQLite's datetime('now') writes
    // "2026-10-16 08:00:00", which is UTC with nothing on it to say so. Read
    // as local wall-clock it lands seven hours adrift in WIB, and a report
    // two seconds old renders as Offline — which is exactly what it did.
    const stamp = '2026-10-16 08:00:00'
    const twoSecondsOn = Date.parse('2026-10-16T08:00:02Z')
    expect(robotStatusDescriptor('on_mission', stamp, twoSecondsOn).offline).toBe(false)
    expect(robotStatusDescriptor('on_mission', stamp, twoSecondsOn).label).toBe('On mission')

    // It still goes quiet when the robot really has stopped reporting.
    const fiveMinutesOn = Date.parse('2026-10-16T08:05:00Z')
    expect(robotStatusDescriptor('on_mission', stamp, fiveMinutesOn).label).toBe('Offline')
  })

  it('does not invent an offline that the clock cannot support', () => {
    // A malformed stamp is missing information, not an outage: it reads as
    // unknown rather than alarming.
    expect(robotStatusDescriptor('ready', 'not a date', fresh()).offline).toBe(true)
  })
})

describe('robotStatusLine', () => {
  it("prefers the robot's own context over the bare label", () => {
    expect(robotStatusLine('on_mission', 'docking at Table 3', REPORTED, fresh())).toBe(
      'docking at Table 3',
    )
  })

  it('falls back to the label when the robot said nothing', () => {
    expect(robotStatusLine('ready', '', REPORTED, fresh())).toBe('Ready')
    expect(robotStatusLine('ready', '   ', REPORTED, fresh())).toBe('Ready')
  })

  it('says offline instead of quoting a stale robot', () => {
    // A word from five minutes ago is not the robot speaking now; the line
    // must not carry it as if it were.
    expect(robotStatusLine('on_mission', 'docking at Table 3', REPORTED, fresh(STATUS_FRESH_MS + 1))).toBe(
      'Offline',
    )
  })
})
