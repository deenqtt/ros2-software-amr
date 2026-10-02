/**
 * Station registry for one map at a time.
 *
 * Scoped to a map on purpose. A station's coordinates only mean anything in one
 * frame, so a store holding every station in the fleet would invite a component
 * to render one map's poses over another's image — and the result looks
 * plausible, which is the worst kind of wrong for a thing a robot drives to.
 *
 * Writes go to the server first and only then update local state.
 */
import { defineStore } from 'pinia'
import { computed, ref } from 'vue'
import { ApiError } from '@/shared/api/client'
import {
  stationsApi,
  StationInUseError,
  StationNameTakenError,
  type StationPatch,
} from '@/shared/api/stations'
import { config } from '@/app/config'
import type { Station, StationDraft } from '@/domain/types'

function describe(error: unknown): string {
  if (error instanceof StationNameTakenError) return error.message
  if (error instanceof StationInUseError) {
    return error.missions.length
      ? `Used by ${error.missions.join(', ')}. Take it out of those missions first.`
      : 'A mission still uses this station. Take it out of that mission first.'
  }
  if (error instanceof ApiError) {
    if (error.isOffline) return `Backend unreachable at ${config.apiBaseUrl}`
    if (error.isNotFound) return 'That station no longer exists.'
    return error.message || `Request failed (${error.status})`
  }
  return error instanceof Error ? error.message : 'Something went wrong.'
}

export const useStationStore = defineStore('stations', () => {
  const stations = ref<Station[]>([])
  /** Which map the loaded stations belong to. Null before the first load. */
  const mapId = ref<string | null>(null)
  const loading = ref(false)
  const loaded = ref(false)
  const error = ref<string | null>(null)

  const count = computed(() => stations.value.length)

  function byId(id: string): Station | null {
    return stations.value.find((station) => station.id === id) ?? null
  }

  /** Whether a name is free, so a form can say so before the server does. */
  function nameTaken(name: string, exceptId?: string): boolean {
    const wanted = name.trim().toLocaleLowerCase()
    return stations.value.some(
      (station) => station.id !== exceptId && station.name.toLocaleLowerCase() === wanted,
    )
  }

  async function load(targetMapId: string): Promise<void> {
    loading.value = true
    error.value = null
    try {
      const rows = await stationsApi.list(targetMapId)
      // Assigned together: a list from one map paired with another map's id
      // would render poses over the wrong image.
      stations.value = rows
      mapId.value = targetMapId
      loaded.value = true
    } catch (cause) {
      error.value = describe(cause)
      stations.value = []
    } finally {
      loading.value = false
    }
  }

  /** Throws on failure: the caller decides how to surface it. */
  async function create(draft: StationDraft): Promise<Station> {
    const created = await stationsApi.create(draft)
    stations.value = [...stations.value, created].sort((a, b) =>
      a.name.localeCompare(b.name, undefined, { sensitivity: 'base' }),
    )
    return created
  }

  async function update(id: string, patch: StationPatch): Promise<Station> {
    const updated = await stationsApi.update(id, patch)
    stations.value = stations.value.map((station) => (station.id === id ? updated : station))
    return updated
  }

  async function remove(id: string): Promise<void> {
    try {
      await stationsApi.remove(id)
    } catch (cause) {
      // Already gone is the outcome that was asked for. Reporting failure would
      // leave a row that can never be removed, because every retry 404s.
      if (!(cause instanceof ApiError && cause.isNotFound)) throw cause
    }
    stations.value = stations.value.filter((station) => station.id !== id)
  }

  return {
    stations,
    mapId,
    loading,
    loaded,
    error,
    count,
    byId,
    nameTaken,
    load,
    create,
    update,
    remove,
    describeError: describe,
  }
})
