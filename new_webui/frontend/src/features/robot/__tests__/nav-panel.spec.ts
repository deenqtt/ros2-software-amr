import { describe, it, expect } from 'vitest'
import { navVerdict, panelPlacement, peekAction, type NavVerdictInput } from '../navPanel'
import { stallLabel } from '../stall'

function base(overrides: Partial<NavVerdictInput> = {}): NavVerdictInput {
  return {
    online: true,
    muted: false,
    attempt: 0,
    hasMap: true,
    run: null,
    agentMode: 'nav',
    agentState: 'running',
    poseSet: true,
    goalOutcome: 'none',
    goalBoxedIn: false,
    stalled: false,
    stillFor: 0,
    ...overrides,
  }
}

const patrol = { missionName: 'Patrol', stepIndex: 1, stepCount: 5, stopName: 'Dock A' }

describe('panelPlacement', () => {
  it('docks on desktop when open and collapses to a strip when closed', () => {
    expect(panelPlacement('desktop', true)).toBe('docked')
    expect(panelPlacement('desktop', false)).toBe('strip')
  })

  it('floats over the map on tablet when open', () => {
    expect(panelPlacement('tablet', true)).toBe('overlay')
    expect(panelPlacement('tablet', false)).toBe('strip')
  })

  it('is always a bottom sheet on phone', () => {
    expect(panelPlacement('phone', true)).toBe('sheet')
    expect(panelPlacement('phone', false)).toBe('sheet')
  })
})

describe('navVerdict', () => {
  it('reports muted monitoring before the link state', () => {
    expect(navVerdict(base({ muted: true, online: false }))).toEqual({
      text: 'Monitoring is off',
      tone: 'muted',
    })
  })

  it('says it is reconnecting when offline with attempts', () => {
    expect(navVerdict(base({ online: false, attempt: 2 }))).toEqual({
      text: 'Not connected, reconnecting',
      tone: 'warn',
    })
  })

  it('says not connected when offline with no attempts yet', () => {
    expect(navVerdict(base({ online: false, attempt: 0 }))).toEqual({
      text: 'Not connected',
      tone: 'warn',
    })
  })

  it('flags a missing map', () => {
    expect(navVerdict(base({ hasMap: false }))).toEqual({ text: 'No map assigned', tone: 'warn' })
  })

  it('shows the active run ahead of a stack problem', () => {
    expect(navVerdict(base({ run: patrol, agentState: 'starting' }))).toEqual({
      text: 'Patrol · step 2/5 → Dock A',
      tone: 'primary',
    })
  })

  it('omits the step count and stop when unknown', () => {
    expect(
      navVerdict(base({ run: { ...patrol, stepCount: null, stopName: null } })).text,
    ).toBe('Patrol · step 2')
  })

  it('warns while Nav2 is starting', () => {
    expect(navVerdict(base({ agentState: 'starting' }))).toEqual({
      text: 'Nav2 starting',
      tone: 'warn',
    })
  })

  it('faults when Nav2 failed', () => {
    expect(navVerdict(base({ agentState: 'failed' }))).toEqual({
      text: 'Nav2 failed',
      tone: 'fault',
    })
  })

  it('says stopped for an unknown mode', () => {
    expect(navVerdict(base({ agentMode: 'unknown', agentState: 'waiting' }))).toEqual({
      text: 'Stopped',
      tone: 'muted',
    })
  })

  it('warns when SLAM is running instead of navigation', () => {
    expect(navVerdict(base({ agentMode: 'map', agentState: 'running' }))).toEqual({
      text: 'SLAM running',
      tone: 'warn',
    })
  })

  it('reports a boxed-in goal failure', () => {
    expect(navVerdict(base({ goalOutcome: 'failed', goalBoxedIn: true }))).toEqual({
      text: 'Goal failed · boxed in',
      tone: 'fault',
    })
  })

  it('uses the stall label when stalled', () => {
    expect(navVerdict(base({ stalled: true, stillFor: 20000 }))).toEqual({
      text: stallLabel(20000),
      tone: 'warn',
    })
  })

  it('asks for the pose when it is not set', () => {
    expect(navVerdict(base({ poseSet: false }))).toEqual({
      text: 'Set the pose to start',
      tone: 'warn',
    })
  })

  it('says driving while a goal runs', () => {
    expect(navVerdict(base({ goalOutcome: 'running' }))).toEqual({
      text: 'Driving to goal',
      tone: 'ok',
    })
  })

  it('is ready when all is good', () => {
    expect(navVerdict(base())).toEqual({ text: 'Ready', tone: 'ok' })
  })
})

describe('peekAction', () => {
  it('offers stop after lap while a run is going', () => {
    expect(peekAction({ online: true, runState: 'running' })).toBe('stopAfterLap')
  })

  it('offers nothing while the run is already stopping', () => {
    expect(peekAction({ online: true, runState: 'stopping' })).toBeNull()
  })

  it('offers to open a mission when online with no run', () => {
    expect(peekAction({ online: true, runState: null })).toBe('openMission')
  })

  it('offers nothing when offline with no run', () => {
    expect(peekAction({ online: false, runState: null })).toBeNull()
  })

  it('still offers stop after lap for a run while offline', () => {
    expect(peekAction({ online: false, runState: 'running' })).toBe('stopAfterLap')
  })
})
