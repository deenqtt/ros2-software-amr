/**
 * Raise an alarm when a robot's link drops.
 *
 * Mounted once at the root, which also makes it the place link monitoring
 * starts. Before this only pages that happened to need a robot connection
 * opened one, so the dashboard — which never did — reported every robot as
 * offline when it was the first page opened.
 *
 * Only a link that was up and then went down is an alarm. A robot that has not
 * connected since the page loaded may simply be switched off, and raising an
 * alarm for every powered-down robot on each refresh would bury the real ones.
 */
import { onMounted, watch } from 'vue'
import { useAlarmStore } from '@/stores/alarms'
import { useFleetStore } from '@/stores/fleet'
import { useLinkStore } from '@/stores/links'
import type { LinkState } from '@/domain/ros/link'

export type LinkTransition = 'lost' | 'restored' | null

/**
 * What a change of link state means for alarms.
 *
 * `lostRaised` is whether a "lost" alarm is outstanding for this robot, so a
 * link flapping between connecting and offline raises one alarm, not one per
 * retry, and "restored" is only said after a loss was.
 */
export function linkTransition(
  previous: LinkState | undefined,
  next: LinkState,
  lostRaised: boolean,
): LinkTransition {
  if (next === 'online') return lostRaised ? 'restored' : null
  if (next === 'offline' && !lostRaised && (previous === 'online' || previous === 'stale')) {
    return 'lost'
  }
  return null
}

export function useLinkAlarms() {
  const alarms = useAlarmStore()
  const fleet = useFleetStore()
  const links = useLinkStore()

  /** Last state seen per robot, and which robots have a "lost" outstanding. */
  const seen = new Map<string, LinkState>()
  const lost = new Map<string, number>()

  onMounted(async () => {
    try {
      await fleet.load()
    } catch {
      // The fleet store reports its own error; nothing to monitor without it.
    }
  })

  watch(
    () => fleet.robots,
    (robots) => links.sync(robots),
    { deep: true },
  )

  watch(
    () => fleet.robots.map((robot) => [robot.id, links.stateFor(robot.id)] as const),
    (states) => {
      for (const [robotId, state] of states) {
        const robot = fleet.byId(robotId)
        const change = linkTransition(seen.get(robotId), state, lost.has(robotId))
        seen.set(robotId, state)
        if (!robot || state === 'muted') continue

        if (change === 'lost') {
          lost.set(robotId, Date.now())
          alarms.raise({
            severity: 'warning',
            source: robot.name,
            message: `Lost the link to ${robot.name} — check it is powered on and on the network`,
            robotId,
          })
        } else if (change === 'restored') {
          const since = lost.get(robotId) ?? Date.now()
          lost.delete(robotId)
          const minutes = Math.max(1, Math.round((Date.now() - since) / 60_000))
          alarms.raise({
            severity: 'info',
            source: robot.name,
            message: `Link to ${robot.name} restored after ${minutes} min`,
            robotId,
          })
        }
      }
    },
  )
}
