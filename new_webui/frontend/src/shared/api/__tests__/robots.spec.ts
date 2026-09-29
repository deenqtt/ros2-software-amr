/**
 * Wire-format translation.
 *
 * The boundary where snake_case meets camelCase is exactly where the old
 * project lost data — fields it had not declared were dropped silently on
 * every write. These pin the mapping in both directions.
 */
import { describe, expect, it } from 'vitest'
import { fromWire, RobotConflictError, toCreateWire, toPatchWire } from '../robots'

const wire = {
  id: 'abc',
  name: 'AMR-01',
  bridge_url: 'ws://10.0.0.1:8765',
  ros_domain_id: 42,
  camera_url: 'http://10.0.0.1:8080',
  namespace: 'amr_01',
  serial: 'SN-1',
  accent: 3,
  active_map_id: null,
  desired_mode: 'nav' as const,
  created_at: '2026-09-25 08:00:00',
  updated_at: '2026-09-25 08:00:00',
}

describe('fromWire', () => {
  it('renames every snake_case field', () => {
    expect(fromWire(wire)).toEqual({
      id: 'abc',
      name: 'AMR-01',
      bridgeUrl: 'ws://10.0.0.1:8765',
      rosDomainId: 42,
      cameraUrl: 'http://10.0.0.1:8080',
      namespace: 'amr_01',
      serial: 'SN-1',
      accent: 3,
      activeMapId: null,
      desiredMode: 'nav',
    })
  })

  it('keeps a zero domain as 0, because 0 is a real ROS domain', () => {
    expect(fromWire({ ...wire, ros_domain_id: 0 }).rosDomainId).toBe(0)
  })

  it('keeps an unset domain as null', () => {
    expect(fromWire({ ...wire, ros_domain_id: null }).rosDomainId).toBeNull()
  })
})

describe('toCreateWire', () => {
  it('sends only the fields the server accepts on create', () => {
    const body = toCreateWire({ name: 'AMR-02', bridgeUrl: 'ws://h:1', rosDomainId: null })
    // id and accent are the server's to assign; sending them is a 422.
    expect(body).toEqual({
      name: 'AMR-02',
      bridge_url: 'ws://h:1',
      ros_domain_id: null,
      camera_url: null,
      namespace: '',
      serial: null,
    })
    expect(body).not.toHaveProperty('id')
    expect(body).not.toHaveProperty('accent')
  })
})

describe('toPatchWire', () => {
  it('sends only the keys present, so omitted fields keep their stored value', () => {
    expect(toPatchWire({ name: 'AMR-09' })).toEqual({ name: 'AMR-09' })
  })

  it('sends an explicit null so a field can actually be cleared', () => {
    // The distinction the old PUT-based API could not express.
    expect(toPatchWire({ rosDomainId: null })).toEqual({ ros_domain_id: null })
  })

  it('does not invent keys for an empty patch', () => {
    expect(toPatchWire({})).toEqual({})
  })
})

describe('RobotConflictError', () => {
  it('maps the server field back to the form field', () => {
    expect(new RobotConflictError('name', 'x').formField).toBe('name')
    expect(new RobotConflictError('bridge_url', 'x').formField).toBe('bridgeUrl')
    expect(new RobotConflictError('mystery', 'x').formField).toBeNull()
  })
})
