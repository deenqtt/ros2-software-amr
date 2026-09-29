/**
 * Missions for one map, and the runs of them.
 *
 * Scoped to a map for the same reason stations are: a route names stations, and
 * a station's coordinates only mean anything in one frame. A store holding
 * every route in the fleet would invite a dispatch against the wrong map, and
 * the refusal would come from the server rather than from the screen.
 *
 * Runs are *not* scoped: an operator watching the floor wants every robot at
 * once, and a run carries its own robot.
 */
import { defineStore } from 'pinia'
import { computed, ref } from 'vue'
import { ApiError } from '@/shared/api/client'
import {
  missionsApi,
  MissionNameTakenError,
  RobotBusyError,
  runsApi,
  WrongMapError,
  type DispatchDraft,
  type MissionDraft,
} from '@/shared/api/missions'
import { config } from '@/app/config'
import { isRunLive, type Mission, type MissionRun, type MissionSummary } from '@/domain/types'

function describe(error: unknown): string {
  if (
    error instanceof MissionNameTakenError ||
    error instanceof RobotBusyError ||
    error instanceof WrongMapError
  ) {
    return error.message
  }
  if (error instanceof ApiError) {
    if (error.isOffline) return `Backend unreachable at ${config.apiBaseUrl}`
    if (error.isNotFound) return 'That mission no longer exists.'
    return error.message || `Request failed (${error.status})`
  }
  return error instanceof Error ? error.message : 'Something went wrong.'
}

export const useMissionStore = defineStore('missions', () => {
  const missions = ref<MissionSummary[]>([])
  const runs = ref<MissionRun[]>([])
  const mapId = ref<string | null>(null)
  const loading = ref(false)
  const loaded = ref(false)
  const error = ref<string | null>(null)

  const count = computed(() => missions.value.length)

  /** What is happening on the floor right now. */
  const liveRuns = computed(() => runs.value.filter((run) => isRunLive(run.state)))

  function runForRobot(robotId: string): MissionRun | null {
    return liveRuns.value.find((run) => run.robotId === robotId) ?? null
  }

  function nameTaken(name: string, exceptId?: string): boolean {
    const wanted = name.trim().toLocaleLowerCase()
    return missions.value.some(
      (mission) => mission.id !== exceptId && mission.name.toLocaleLowerCase() === wanted,
    )
  }

  async function load(targetMapId: string): Promise<void> {
    loading.value = true
    error.value = null
    try {
      // Together, so a list from one map is never paired with another map's id.
      const [rows, runRows] = await Promise.all([missionsApi.list(targetMapId), runsApi.list()])
      missions.value = rows
      runs.value = runRows
      mapId.value = targetMapId
      loaded.value = true
    } catch (cause) {
      error.value = describe(cause)
      missions.value = []
    } finally {
      loading.value = false
    }
  }

  /** Just the runs. Polled while something is live, without redrawing the list. */
  async function refreshRuns(): Promise<void> {
    try {
      runs.value = await runsApi.list()
    } catch {
      // A missed poll is a stale number for a few seconds, not an error worth
      // putting on screen — the next one corrects it.
    }
  }

  async function reloadMissions(): Promise<void> {
    if (!mapId.value) return
    missions.value = await missionsApi.list(mapId.value)
  }

  /** Throws on failure: the caller decides how to surface it. */
  async function create(draft: MissionDraft): Promise<Mission> {
    const created = await missionsApi.create(draft)
    await reloadMissions()
    return created
  }

  async function update(id: string, patch: Parameters<typeof missionsApi.update>[1]) {
    const updated = await missionsApi.update(id, patch)
    await reloadMissions()
    return updated
  }

  async function remove(id: string): Promise<void> {
    try {
      await missionsApi.remove(id)
    } catch (cause) {
      // Already gone is the outcome that was asked for. Reporting failure
      // leaves a row that can never be removed, because every retry 404s.
      if (!(cause instanceof ApiError && cause.isNotFound)) throw cause
    }
    missions.value = missions.value.filter((mission) => mission.id !== id)
  }

  async function dispatch(draft: DispatchDraft): Promise<MissionRun> {
    const run = await runsApi.start(draft)
    await refreshRuns()
    return run
  }

  async function stopAfterLap(id: string): Promise<void> {
    await runsApi.stopAfterLap(id)
    await refreshRuns()
  }

  async function cancel(id: string): Promise<void> {
    await runsApi.cancel(id)
    await refreshRuns()
  }

  return {
    missions,
    runs,
    liveRuns,
    mapId,
    loading,
    loaded,
    error,
    count,
    runForRobot,
    nameTaken,
    load,
    refreshRuns,
    create,
    update,
    remove,
    dispatch,
    stopAfterLap,
    cancel,
    describeError: describe,
  }
})
