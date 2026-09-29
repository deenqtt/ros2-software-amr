import type { StatusTone } from '@/domain/types'

export interface StackStatus {
  label: 'Running' | 'Starting' | 'Stopping' | 'Failed' | 'Stopped' | 'Unknown'
  tone: StatusTone
  detail: string
}

export interface AgentStackSnapshot {
  mode: string
  state: string
  detail: string
}

function unknown(name: string): StackStatus {
  return {
    label: 'Unknown',
    tone: 'neutral',
    detail: `No robot agent status received for ${name}.`,
  }
}

function stopped(name: string): StackStatus {
  return {
    label: 'Stopped',
    tone: 'neutral',
    detail: `${name} is not running.`,
  }
}

function statusFor(
  name: string,
  mode: string,
  state: string,
  detail: string,
  expectedMode: string,
): StackStatus {
  if (mode !== expectedMode) return stopped(name)

  if (state === 'running') {
    return { label: 'Running', tone: 'success', detail: `${name} is running.` }
  }
  if (state === 'starting') {
    return { label: 'Starting', tone: 'active', detail: detail || `Starting ${name}.` }
  }
  if (state === 'stopping') {
    return { label: 'Stopping', tone: 'active', detail: detail || `Stopping ${name}.` }
  }
  if (state === 'failed') {
    return { label: 'Failed', tone: 'fault', detail: detail || `${name} failed to start.` }
  }
  return stopped(name)
}

export function stackStatuses(agent: AgentStackSnapshot | null): {
  nav2: StackStatus
  slam: StackStatus
} {
  if (!agent) {
    return { nav2: unknown('Nav2'), slam: unknown('SLAM') }
  }

  return {
    nav2: statusFor('Nav2', agent.mode, agent.state, agent.detail, 'nav'),
    slam: statusFor('SLAM', agent.mode, agent.state, agent.detail, 'map'),
  }
}
