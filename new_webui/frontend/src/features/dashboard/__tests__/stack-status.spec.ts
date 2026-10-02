import { describe, expect, it } from 'vitest'
import { stackStatuses, stackSummary } from '../stackStatus'

describe('stackStatuses', () => {
  it('reports Nav2 running and SLAM stopped in navigation mode', () => {
    const status = stackStatuses({ mode: 'nav', state: 'running', detail: '' })

    expect(status.nav2.label).toBe('Running')
    expect(status.nav2.tone).toBe('success')
    expect(status.slam.label).toBe('Stopped')
    expect(status.slam.tone).toBe('neutral')
  })

  it('reports SLAM starting and Nav2 stopped in mapping mode', () => {
    const status = stackStatuses({ mode: 'map', state: 'starting', detail: 'Starting SLAM' })

    expect(status.slam.label).toBe('Starting')
    expect(status.slam.tone).toBe('active')
    expect(status.nav2.label).toBe('Stopped')
    expect(status.nav2.tone).toBe('neutral')
  })

  it('reports a failed stack on the mode that failed', () => {
    const status = stackStatuses({ mode: 'nav', state: 'failed', detail: 'map not found' })

    expect(status.nav2.label).toBe('Failed')
    expect(status.nav2.tone).toBe('fault')
    expect(status.nav2.detail).toBe('map not found')
    expect(status.slam.label).toBe('Stopped')
  })

  it('does not invent stack state before the agent has reported', () => {
    const status = stackStatuses(null)

    expect(status.nav2.label).toBe('Unknown')
    expect(status.slam.label).toBe('Unknown')
    expect(status.nav2.tone).toBe('neutral')
    expect(status.slam.tone).toBe('neutral')
  })
})

describe('stackSummary', () => {
  const agent = (mode: string, state: string, detail = '') => ({ mode, state, detail })

  it('says unknown, once, for a robot with no agent report', () => {
    const summary = stackSummary(null)
    expect(summary.label).toBe('Unknown')
    expect(summary.stack).toBeNull()
  })

  it('names the stack that is running', () => {
    expect(stackSummary(agent('nav', 'running'))).toMatchObject({ label: 'Running', stack: 'Nav2' })
    expect(stackSummary(agent('map', 'running'))).toMatchObject({ label: 'Running', stack: 'SLAM' })
  })

  it('names the stack that failed, with its detail', () => {
    expect(stackSummary(agent('nav', 'failed', 'map_server died'))).toMatchObject({
      label: 'Failed',
      tone: 'fault',
      stack: 'Nav2',
      detail: 'map_server died',
    })
  })

  it('says stopped only when neither stack is up', () => {
    expect(stackSummary(agent('unknown', 'idle'))).toMatchObject({ label: 'Stopped', stack: null })
  })
})
