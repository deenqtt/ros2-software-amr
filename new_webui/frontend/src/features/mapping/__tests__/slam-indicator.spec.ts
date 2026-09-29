/**
 * SLAM indicator.
 *
 * It reads the agent's own report rather than inferring from map traffic: a
 * grid keeps arriving briefly after the stack dies and never arrives in the
 * first seconds after it starts, so an inferred indicator lies at exactly the
 * two moments an operator is looking at it.
 */
import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'
import SlamIndicator from '../components/SlamIndicator.vue'
import type { AgentStatus } from '../useRobotTelemetry'

function agent(overrides: Partial<AgentStatus> = {}): AgentStatus {
  return {
    mode: 'map',
    state: 'running',
    map: '',
    mapId: '',
    detail: '',
    managed: true,
    backend: 'ok',
    teleop: false,
    ...overrides,
  }
}

function render(value: AgentStatus | null) {
  return mount(SlamIndicator, { props: { agent: value } })
}

describe('SlamIndicator', () => {
  it('says SLAM is running only when the agent says so', () => {
    expect(render(agent()).text()).toContain('SLAM running')
  })

  it('distinguishes starting from running', () => {
    // The operator needs to know the wait is expected, not that it is stuck.
    expect(render(agent({ state: 'starting' })).text()).toContain('SLAM starting')
  })

  it('shows stopping while the stack comes down', () => {
    expect(render(agent({ state: 'stopping' })).text()).toContain('SLAM stopping')
  })

  it('reports a failed start as a fault, not as stopped', () => {
    const wrapper = render(agent({ state: 'failed', detail: 'Timed out after 45s' }))
    expect(wrapper.text()).toContain('SLAM failed')
    expect(wrapper.html()).toContain('Timed out after 45s')
  })

  it('says SLAM is stopped when the robot is idle', () => {
    expect(render(agent({ mode: 'unknown', state: 'idle' })).text()).toContain('SLAM stopped')
  })

  it('says navigating when Nav2 owns the robot, not "stopped"', () => {
    // Both mean SLAM is not running, but only one of them means the robot is
    // busy doing something else.
    expect(render(agent({ mode: 'nav', state: 'running' })).text()).toContain('Navigating')
  })

  it('treats a silent agent as unknown, not as stopped', () => {
    // No agent means mode switching is unavailable; an agent reporting idle
    // means it is available and nothing is running. They must not look alike.
    expect(render(null).text()).toContain('No agent')
  })
})
