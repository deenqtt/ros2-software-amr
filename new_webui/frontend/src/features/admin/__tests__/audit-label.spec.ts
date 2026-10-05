import { describe, expect, it } from 'vitest'
import { auditDate, auditLabel, auditOutcome } from '../auditLabel'

const entry = (method: string, path: string, status = 200) => ({
  action: `${method} ${path}`,
  method,
  path,
  status,
  detail: null,
})

describe('auditLabel', () => {
  it('names the common changes in words', () => {
    expect(auditLabel(entry('POST', '/api/runs', 201))).toBe('Started a mission')
    expect(auditLabel(entry('PUT', '/api/robots/abc/mode'))).toBe('Changed a robot’s mode')
    expect(auditLabel(entry('DELETE', '/api/stations/s-1', 204))).toBe('Deleted a station')
  })

  it('does not confuse a robot edit with its mode or map', () => {
    expect(auditLabel(entry('PATCH', '/api/robots/abc'))).toBe('Edited a robot')
    expect(auditLabel(entry('PUT', '/api/robots/abc/map'))).toBe('Assigned a map to a robot')
  })

  it('says why a sign-in was refused', () => {
    const base = { action: 'login', method: 'POST', path: '/api/auth/login' }
    expect(auditLabel({ ...base, status: 200, detail: null })).toBe('Signed in')
    expect(auditLabel({ ...base, status: 401, detail: 'bad password' })).toBe(
      'Sign-in refused (wrong password)',
    )
    expect(auditLabel({ ...base, status: 429, detail: 'throttled' })).toBe(
      'Sign-in refused (paused after repeated failures)',
    )
  })

  it('falls back to the raw request for routes it does not know', () => {
    expect(auditLabel(entry('POST', '/api/something/new'))).toBe('POST /api/something/new')
  })
})

describe('auditOutcome', () => {
  it('separates refusals from failures', () => {
    expect(auditOutcome(201)).toBe('ok')
    expect(auditOutcome(403)).toBe('refused')
    expect(auditOutcome(409)).toBe('failed')
  })
})

describe('auditDate', () => {
  it('reads the server stamp as UTC', () => {
    expect(auditDate('2026-10-05 02:18:32').toISOString()).toBe('2026-10-05T02:18:32.000Z')
  })
})
