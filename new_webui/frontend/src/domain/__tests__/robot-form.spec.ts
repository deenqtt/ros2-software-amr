import { describe, expect, it } from 'vitest'
import {
  fromRobot,
  hasErrors,
  toRobotPatch,
  validateRobotForm,
  warnRobotForm,
  type RobotFormValues,
} from '../robot-form'
import type { RobotConfig } from '../types'

function robot(overrides: Partial<RobotConfig> = {}): RobotConfig {
  return {
    id: 'robot-1',
    name: 'AMR-01',
    bridgeUrl: 'ws://192.168.1.50:8765',
    rosDomainId: null,
    cameraUrl: null,
    namespace: '',
    accent: 1,
    serial: null,
    activeMapId: null,
    desiredMode: 'nav',
    ...overrides,
  }
}

function values(overrides: Partial<RobotFormValues> = {}): RobotFormValues {
  return { name: 'AMR-02', bridgeUrl: 'ws://192.168.1.51:8765', rosDomainId: '', ...overrides }
}

describe('validateRobotForm — name', () => {
  it('requires a name', () => {
    expect(validateRobotForm(values({ name: '   ' }), []).name).toBe('Name is required.')
  })

  it('rejects a duplicate name regardless of case or padding', () => {
    // Two robots sharing a name is how an operator drives the wrong one.
    const existing = [robot({ name: 'AMR-01' })]
    expect(validateRobotForm(values({ name: 'amr-01' }), existing).name).toBeDefined()
    expect(validateRobotForm(values({ name: '  AMR-01 ' }), existing).name).toBeDefined()
  })

  it('lets a robot keep its own name while editing', () => {
    const existing = [robot({ id: 'robot-1', name: 'AMR-01' })]
    expect(validateRobotForm(values({ name: 'AMR-01' }), existing, 'robot-1').name).toBeUndefined()
  })
})

describe('validateRobotForm — bridge URL', () => {
  it('requires a URL', () => {
    expect(validateRobotForm(values({ bridgeUrl: '' }), []).bridgeUrl).toBe(
      'Bridge URL is required.',
    )
  })

  it('rejects non-websocket protocols', () => {
    expect(validateRobotForm(values({ bridgeUrl: 'http://host:8765' }), []).bridgeUrl).toBe(
      'Must start with ws:// or wss://',
    )
  })

  it('rejects unparseable input', () => {
    expect(validateRobotForm(values({ bridgeUrl: 'not a url' }), []).bridgeUrl).toBe(
      'Not a valid WebSocket URL.',
    )
  })

  it('accepts ws and wss', () => {
    expect(
      validateRobotForm(values({ bridgeUrl: 'ws://10.0.0.2:8765' }), []).bridgeUrl,
    ).toBeUndefined()
    expect(
      validateRobotForm(values({ bridgeUrl: 'wss://robot.local:9090' }), []).bridgeUrl,
    ).toBeUndefined()
  })

  it('rejects a bridge another robot already uses', () => {
    const existing = [robot({ bridgeUrl: 'ws://10.0.0.2:8765' })]
    expect(validateRobotForm(values({ bridgeUrl: 'ws://10.0.0.2:8765' }), existing).bridgeUrl).toBe(
      'Another robot already uses this bridge.',
    )
  })
})

describe('validateRobotForm — ROS domain', () => {
  it('treats an empty domain as valid, because it is optional', () => {
    expect(validateRobotForm(values({ rosDomainId: '' }), []).rosDomainId).toBeUndefined()
  })

  it('accepts 0, which is a real domain', () => {
    expect(validateRobotForm(values({ rosDomainId: '0' }), []).rosDomainId).toBeUndefined()
  })

  it('rejects fractions and non-numbers', () => {
    expect(validateRobotForm(values({ rosDomainId: '4.5' }), []).rosDomainId).toBe(
      'Must be a whole number.',
    )
    expect(validateRobotForm(values({ rosDomainId: 'abc' }), []).rosDomainId).toBe(
      'Must be a whole number.',
    )
  })

  it('rejects out-of-range values', () => {
    expect(validateRobotForm(values({ rosDomainId: '-1' }), []).rosDomainId).toBeDefined()
    expect(validateRobotForm(values({ rosDomainId: '233' }), []).rosDomainId).toBeDefined()
  })

  it('warns but does not block above the safe ceiling', () => {
    const v = values({ rosDomainId: '150' })
    expect(validateRobotForm(v, []).rosDomainId).toBeUndefined()
    expect(warnRobotForm(v).rosDomainId).toContain('101')
  })

  it('does not warn inside the safe range', () => {
    expect(warnRobotForm(values({ rosDomainId: '42' })).rosDomainId).toBeUndefined()
  })
})

describe('form <-> record conversion', () => {
  it('turns an empty domain into null, not zero', () => {
    expect(toRobotPatch(values({ rosDomainId: '' })).rosDomainId).toBeNull()
    expect(toRobotPatch(values({ rosDomainId: '0' })).rosDomainId).toBe(0)
  })

  it('trims name and URL', () => {
    const patch = toRobotPatch(values({ name: '  AMR-03 ', bridgeUrl: ' ws://h:1 ' }))
    expect(patch.name).toBe('AMR-03')
    expect(patch.bridgeUrl).toBe('ws://h:1')
  })

  it('round-trips a record through the form', () => {
    const original = robot({ name: 'AMR-09', rosDomainId: 42 })
    expect(toRobotPatch(fromRobot(original))).toEqual({
      name: 'AMR-09',
      bridgeUrl: original.bridgeUrl,
      rosDomainId: 42,
    })
  })

  it('renders an unset domain as an empty field, not "null"', () => {
    expect(fromRobot(robot({ rosDomainId: null })).rosDomainId).toBe('')
  })
})

describe('hasErrors', () => {
  it('is false for a clean form and true otherwise', () => {
    expect(hasErrors(validateRobotForm(values(), []))).toBe(false)
    expect(hasErrors(validateRobotForm(values({ name: '' }), []))).toBe(true)
  })
})
