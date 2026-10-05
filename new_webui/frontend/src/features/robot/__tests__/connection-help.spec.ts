import { describe, expect, it } from 'vitest'
import { backendLabel, connectionHelp } from '../connectionHelp'

describe('connectionHelp', () => {
  it('names the address and what to check when nothing answers', () => {
    const help = connectionHelp('offline', 'ws://10.0.0.5:9090', 3)
    expect(help.title).toContain('attempt 3')
    expect(help.detail).toContain('ws://10.0.0.5:9090')
    expect(help.checks).toEqual([
      'The robot is powered on',
      'rosbridge is running on port 9090',
      "This device is on the robot's network",
    ])
    expect(help.tone).toBe('fault')
  })

  it('points at the publisher, not the network, when only topics are silent', () => {
    expect(connectionHelp('stale', 'ws://x', 0).detail).toContain('publishing')
  })

  it('says monitoring is off rather than calling a muted robot broken', () => {
    expect(connectionHelp('muted', 'ws://x', 0).tone).toBe('muted')
  })
})

describe('backendLabel', () => {
  it('reads the agent server states in words', () => {
    expect(backendLabel('ok').tone).toBe('text-status-ok')
    expect(backendLabel('unreachable').text).toContain('snapshot')
    expect(backendLabel('not configured').tone).toBe('text-status-fault')
    expect(backendLabel('whatever').text).toBe('Not reported')
  })
})
