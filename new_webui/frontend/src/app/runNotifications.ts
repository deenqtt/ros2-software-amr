/**
 * Tell the operator what the fleet's missions are doing, wherever they are.
 *
 * Mounted once at the root, not on the navigation page: a robot reaching a
 * stop, failing or finishing matters just as much to someone looking at the
 * dashboard. Each event is a toast for now and an alarm for later — the bell
 * keeps the record a toast throws away after a few seconds.
 *
 * The run rows on the server are the source of truth: the agent writes an
 * arrival the moment Nav2 reports success, so "reached <station>" is what the
 * database says, not a guess from a goal status that also fires for one-off
 * goals and has no idea which station it was.
 */
import { onBeforeUnmount, onMounted } from 'vue'
import { toast } from 'vue-sonner'
import { missionsApi, runsApi } from '@/shared/api/missions'
import { stationsApi } from '@/shared/api/stations'
import { useAlarmStore, type AlarmSeverity } from '@/stores/alarms'
import { useFleetStore } from '@/stores/fleet'
import { useMissionStore } from '@/stores/missions'
import { diffRuns, type RunEvent } from '@/features/missions/runEvents'
import type { Mission, MissionRun } from '@/domain/types'

/** Same order as the navigation page used to poll at while a run was live. */
export const RUN_POLL_MS = 2500

/** Set by the operator's own cancel. That tab already said so. */
const OPERATOR_CANCEL = 'canceled by the operator'

export function useRunNotifications() {
  const alarms = useAlarmStore()
  const fleet = useFleetStore()
  const missions = useMissionStore()

  let previous: Map<string, MissionRun> | null = null
  let timer: ReturnType<typeof setInterval> | null = null
  let polling = false

  // Routes and station names change rarely; a run's arrivals come every few
  // seconds. Cached as promises so a burst of events fetches each once.
  const missionCache = new Map<string, Promise<Mission | null>>()
  const stationCache = new Map<string, Promise<Map<string, string>>>()

  function missionFor(id: string): Promise<Mission | null> {
    let pending = missionCache.get(id)
    if (!pending) {
      pending = missionsApi.get(id).catch(() => {
        // Not cached as a failure: the next event should try again.
        missionCache.delete(id)
        return null
      })
      missionCache.set(id, pending)
    }
    return pending
  }

  function stationNames(mapId: string): Promise<Map<string, string>> {
    let pending = stationCache.get(mapId)
    if (!pending) {
      pending = stationsApi
        .list(mapId)
        .then((rows) => new Map(rows.map((station) => [station.id, station.name])))
        .catch(() => {
          stationCache.delete(mapId)
          return new Map<string, string>()
        })
      stationCache.set(mapId, pending)
    }
    return pending
  }

  async function describeStep(run: MissionRun, index: number) {
    const mission = run.missionId ? await missionFor(run.missionId) : null
    const step = mission?.steps[index]
    const station = step && mission ? (await stationNames(mission.mapId)).get(step.stationId) : undefined
    return { station: station ?? null, total: mission?.steps.length ?? null }
  }

  function robotName(run: MissionRun): string {
    return (run.robotId && fleet.byId(run.robotId)?.name) || 'Robot'
  }

  function record(severity: AlarmSeverity, source: string, message: string) {
    alarms.raise({ severity, source, message })
  }

  async function announce(event: RunEvent): Promise<void> {
    const { run } = event
    const robot = robotName(run)
    const mission = run.missionName

    switch (event.kind) {
      case 'started':
        // The operator who started it has had a toast already.
        record('info', robot, `Started ${mission}`)
        return

      case 'reached': {
        const index = run.reachedIndex ?? 0
        const { station, total } = await describeStep(run, index)
        const place = station ?? `step ${index + 1}`
        const progress = total ? `step ${index + 1} of ${total}` : `step ${index + 1}`
        const lap = run.mode === 'once' ? '' : ` · lap ${run.reachedLap ?? run.lap}`
        toast.success(`${robot} reached ${place}`, { description: `${mission} · ${progress}${lap}` })
        record('info', robot, `Reached ${place} (${mission}, ${progress}${lap})`)
        return
      }

      case 'done':
        toast.success(`${robot} finished ${mission}`)
        record('info', robot, `Finished ${mission}`)
        return

      case 'failed':
        toast.error(`${mission} failed on ${robot}`, { description: run.detail ?? undefined })
        record('fault', robot, `${mission} failed${run.detail ? `: ${run.detail}` : ''}`)
        return

      case 'canceled':
        if (run.detail !== OPERATOR_CANCEL) {
          toast.warning(`${mission} canceled on ${robot}`, { description: run.detail ?? undefined })
        }
        record('warning', robot, `${mission} canceled${run.detail ? `: ${run.detail}` : ''}`)
        return
    }
  }

  async function poll(): Promise<void> {
    // A slow backend must not stack polls up behind each other.
    if (polling) return
    polling = true
    try {
      const rows = await runsApi.list()
      // Shared with every page, so a run started from another tab or the
      // dashboard shows up on the navigation page without a reload.
      missions.runs = rows
      // Rows come newest first. Diffed oldest first, so the newest toast ends
      // up on top — and a run's own events (reached, then done) keep their order.
      const events = diffRuns(previous, [...rows].reverse())
      previous = new Map(rows.map((run) => [run.id, run]))
      for (const event of events) await announce(event)
    } catch {
      // A missed poll is a few seconds of silence; the next one catches up,
      // and the diff still sees every change because it compares rows.
    } finally {
      polling = false
    }
  }

  onMounted(() => {
    // Names for the messages. Nothing breaks if this fails: they say "Robot".
    if (!fleet.loaded) void fleet.load().catch(() => undefined)
    void poll()
    timer = setInterval(() => void poll(), RUN_POLL_MS)
  })

  onBeforeUnmount(() => {
    if (timer !== null) clearInterval(timer)
    timer = null
  })
}
