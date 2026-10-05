import type { LinkState } from '@/domain/ros/link'

/**
 * What a link state means and what to do about it, in an operator's words.
 *
 * The browser's WebSocket error carries no reason — by design, so pages cannot
 * probe networks — and "WebSocket error" is all the old Attention box could
 * say. What it can say is the likely causes, in the order worth checking.
 */
export function connectionHelp(
  state: LinkState,
  bridgeUrl: string,
  attempt: number,
): {
  title: string
  detail: string | null
  /** What to check, in the order worth checking. Empty when nothing is wrong. */
  checks: string[]
  tone: 'ok' | 'warn' | 'fault' | 'muted'
} {
  switch (state) {
    case 'online':
      return { title: 'Connected', detail: null, checks: [], tone: 'ok' }
    case 'stale':
      return {
        title: 'Connected, but some data has stopped',
        detail:
          'rosbridge is answering, so the process publishing the silent topics below is the likely cause.',
        checks: [],
        tone: 'warn',
      }
    case 'muted':
      return {
        title: 'Not monitored',
        detail: 'Monitoring is off, so this browser does not connect to the robot.',
        checks: [],
        tone: 'muted',
      }
    case 'connecting':
    case 'offline':
      return {
        title: attempt > 0 ? `Can't reach the robot — attempt ${attempt}` : "Can't reach the robot",
        detail: `Nothing answered at ${bridgeUrl}.`,
        checks: [
          'The robot is powered on',
          `rosbridge is running on ${portOf(bridgeUrl)}`,
          "This device is on the robot's network",
        ],
        tone: 'fault',
      }
  }
}

/** The agent's view of the server, for the Robot agent section. */
export function backendLabel(backend: string): { text: string; tone: string } {
  if (backend === 'ok') return { text: 'Reaching the server', tone: 'text-status-ok' }
  if (backend === 'unreachable') {
    return { text: 'Cannot reach the server — running from its last snapshot', tone: 'text-status-warn' }
  }
  if (backend === 'not configured') {
    return { text: 'No server configured — maps and missions will not sync', tone: 'text-status-fault' }
  }
  if (backend === 'error') return { text: 'Server returned an error', tone: 'text-status-fault' }
  return { text: 'Not reported', tone: 'text-muted' }
}

function portOf(bridgeUrl: string): string {
  try {
    const url = new URL(bridgeUrl)
    return url.port ? `port ${url.port}` : 'its port'
  } catch {
    return 'its port'
  }
}
