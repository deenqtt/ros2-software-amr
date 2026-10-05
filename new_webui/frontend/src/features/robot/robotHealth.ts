/**
 * One verdict for a robot: is it healthy, and if not, the one thing to know.
 *
 * The details page has the link, the robot's own agent and every topic, in
 * three places. Someone standing next to a robot that is not moving should not
 * have to read all three to learn whether anything is wrong, so this reads
 * them in the order a fault is found — can we reach it, is its stack up, is it
 * reaching the server, is its data flowing — and stops at the first problem.
 */
import type { LinkState } from '@/domain/ros/link'
import type { TopicHealth } from '@/domain/ros/health'

export type HealthTone = 'ok' | 'warn' | 'fault' | 'muted'

export interface HealthVerdict {
  tone: HealthTone
  title: string
  /** The supporting line: what is running and how much data is flowing. */
  line: string
}

export interface AgentHealthInput {
  mode: string
  state: string
  backend: string
}

function stackName(mode: string): string | null {
  return mode === 'nav' ? 'Nav2' : mode === 'map' ? 'SLAM' : null
}

export function robotHealth(input: {
  link: LinkState
  host: string
  agent: AgentHealthInput | null
  topics: readonly TopicHealth[]
}): HealthVerdict {
  const { link, agent, topics } = input

  if (link === 'muted') {
    return { tone: 'muted', title: 'Not monitored', line: 'Monitoring is off for this robot.' }
  }
  if (link === 'offline' || link === 'connecting') {
    return { tone: 'fault', title: "Can't reach the robot", line: `Nothing answered at ${input.host}.` }
  }

  const subscribed = topics.filter((topic) => topic.state !== 'idle')
  const ok = subscribed.filter((topic) => topic.state === 'ok').length
  const stale = subscribed.filter((topic) => topic.state === 'stale')
  const stack = agent ? stackName(agent.mode) : null

  const parts: string[] = []
  if (agent) parts.push(stack ? `${stack} ${agent.state}` : 'Stack stopped')
  if (subscribed.length) parts.push(`${ok} of ${subscribed.length} topics OK`)
  const line = parts.join(' · ') || 'Connected'

  if (agent?.state === 'failed') {
    return { tone: 'fault', title: `${stack ?? 'The stack'} failed to start`, line }
  }
  if (agent && (agent.backend === 'not configured' || agent.backend === 'error')) {
    return { tone: 'fault', title: 'The robot cannot use the server', line }
  }
  if (stale.length) {
    const what = stale.length === 1 ? `${stale[0]!.label} has` : `${stale.length} topics have`
    return { tone: 'warn', title: `${what} gone quiet`, line }
  }
  if (agent?.backend === 'unreachable') {
    return { tone: 'warn', title: "The robot can't reach the server", line }
  }
  if (agent && (agent.state === 'starting' || agent.state === 'stopping')) {
    return { tone: 'warn', title: `${stack ?? 'The stack'} is ${agent.state}`, line }
  }
  if (subscribed.length && ok === 0) {
    return { tone: 'warn', title: 'Connected, waiting for data', line }
  }
  return { tone: 'ok', title: 'Healthy', line }
}

/** Topics worth showing first on a phone: anything not plainly OK. */
export function problemTopics(topics: readonly TopicHealth[]): TopicHealth[] {
  return topics.filter((topic) => topic.state === 'stale' || topic.state === 'waiting')
}
