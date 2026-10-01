/**
 * Where a running mission goes, as markers on the navigation map.
 *
 * A route that revisits a station — out to a pick, back to a drop, back to
 * the pick — would otherwise stack two discs on one spot, the later hiding
 * the earlier. One marker per station, labelled with every step that uses it,
 * reads correctly.
 */
import type { MissionRun, MissionStep, Station } from '@/domain/types'

export type StepStatus = 'done' | 'current' | 'pending'

export interface MissionMarker {
  stationId: string
  name: string
  x: number
  y: number
  yaw: number
  /** Step numbers from 1, in route order. */
  ordinals: number[]
  status: StepStatus
}

export interface MissionOverlay {
  markers: MissionMarker[]
  /** Station positions in step order, for the line that joins them. */
  route: { x: number; y: number }[]
}

/** Where one step stands in the lap the robot is on. */
export function stepStatus(index: number, run: MissionRun): StepStatus {
  if (run.state === 'done') return 'done'
  // Only an arrival on this lap counts: last lap's arrivals are history.
  const reached = run.reachedLap === run.lap ? run.reachedIndex : null
  if (index < run.stepIndex || (reached !== null && index <= reached)) return 'done'
  if (index === run.stepIndex) return 'current'
  return 'pending'
}

/** Current outranks pending outranks done: a station still to visit is not finished. */
const RANK: Record<StepStatus, number> = { current: 2, pending: 1, done: 0 }

export function missionOverlay(
  steps: MissionStep[],
  stationsById: (id: string) => Station | null,
  run: MissionRun,
): MissionOverlay {
  const byStation = new Map<string, MissionMarker>()
  const route: { x: number; y: number }[] = []

  steps.forEach((step, index) => {
    const station = stationsById(step.stationId)
    // A step whose station was deleted cannot be drawn. It is still counted,
    // so the numbers on the others stay the step numbers the card shows.
    if (!station) return
    route.push({ x: station.x, y: station.y })

    const status = stepStatus(index, run)
    const existing = byStation.get(station.id)
    if (existing) {
      existing.ordinals.push(index + 1)
      if (RANK[status] > RANK[existing.status]) existing.status = status
      return
    }
    byStation.set(station.id, {
      stationId: station.id,
      name: station.name,
      x: station.x,
      y: station.y,
      yaw: station.yaw,
      ordinals: [index + 1],
      status,
    })
  })

  return { markers: [...byStation.values()], route }
}
