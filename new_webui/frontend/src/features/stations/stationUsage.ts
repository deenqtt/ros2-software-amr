import type { MissionSummary } from '@/domain/types'

/**
 * Which missions name each station, by station id.
 *
 * The server refuses to delete a station a mission step still names. Knowing
 * that up front lets the list say so and the delete dialog name the routes,
 * instead of offering a button the server will turn down.
 *
 * A route that visits the same station twice is listed once.
 */
export function missionsByStation(
  missions: Pick<MissionSummary, 'id' | 'name' | 'stationIds'>[],
): Map<string, { id: string; name: string }[]> {
  const usage = new Map<string, { id: string; name: string }[]>()
  for (const mission of missions) {
    for (const stationId of new Set(mission.stationIds)) {
      const list = usage.get(stationId) ?? []
      list.push({ id: mission.id, name: mission.name })
      usage.set(stationId, list)
    }
  }
  return usage
}
