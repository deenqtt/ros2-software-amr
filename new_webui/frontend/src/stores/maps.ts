/**
 * Map registry, backed by the API.
 *
 * Writes go to the server first and only then update local state. An
 * optimistic insert would show a map that the server may have rejected, and
 * this registry decides what a robot will navigate on.
 */
import { defineStore } from 'pinia'
import { computed, ref } from 'vue'
import { ApiError } from '@/shared/api/client'
import { mapsApi, MapInUseError, MapNameTakenError, type MapUpload } from '@/shared/api/maps'
import { config } from '@/app/config'
import type { MapRecord } from '@/domain/types'

function describe(error: unknown): string {
  if (error instanceof MapInUseError) return error.message
  if (error instanceof MapNameTakenError) return error.message
  if (error instanceof ApiError) {
    if (error.isOffline) return `Backend unreachable at ${config.apiBaseUrl}`
    if (error.isNotFound) return 'That map no longer exists.'
    return error.readable || `Request failed (${error.status})`
  }
  return error instanceof Error ? error.message : 'Something went wrong.'
}

export const useMapStore = defineStore('maps', () => {
  const maps = ref<MapRecord[]>([])
  const loading = ref(false)
  const loaded = ref(false)
  const error = ref<string | null>(null)

  const count = computed(() => maps.value.length)

  function byId(id: string): MapRecord | null {
    return maps.value.find((m) => m.id === id) ?? null
  }

  /**
   * The newest version of each name.
   *
   * Older versions stay in the list — they are what robots still running them
   * are running — but an operator picking a map to assign almost always wants
   * the current one.
   */
  const latestByName = computed(() => {
    const newest = new Map<string, MapRecord>()
    for (const map of maps.value) {
      const key = map.name.toLocaleLowerCase()
      const existing = newest.get(key)
      if (!existing || map.version > existing.version) newest.set(key, map)
    }
    return [...newest.values()]
  })

  function isLatest(map: MapRecord): boolean {
    return latestByName.value.some((m) => m.id === map.id)
  }

  async function load(): Promise<void> {
    loading.value = true
    error.value = null
    try {
      if (config.devLatencyMs > 0) {
        await new Promise((resolve) => setTimeout(resolve, config.devLatencyMs))
      }
      maps.value = await mapsApi.list()
      loaded.value = true
    } catch (cause) {
      error.value = describe(cause)
    } finally {
      loading.value = false
    }
  }

  /** Throws on failure: the caller decides how to surface it. */
  async function upload(payload: MapUpload): Promise<MapRecord> {
    const created = await mapsApi.upload(payload)
    // Re-read rather than splicing: the server may have returned an existing
    // version when the content was unchanged, and ordering is its business.
    await load()
    return created
  }

  /**
   * Rename a map. Throws on failure; the caller decides how to surface it.
   *
   * Reloads rather than patching the one row: the server renames every version
   * of the lineage, so the rest of the list is stale the moment this returns.
   */
  async function rename(id: string, name: string): Promise<MapRecord> {
    const renamed = await mapsApi.rename(id, name)
    await load()
    return renamed
  }

  /**
   * Replace a version's contents in place. Throws on failure.
   *
   * Reloads: the row's hash, size and note all change, and a robot's assignment
   * now points at different contents under the same id.
   */
  async function replaceImage(
    id: string,
    payload: { yamlFile: File; imageFile: File; note?: string | null },
  ): Promise<MapRecord> {
    const updated = await mapsApi.replaceImage(id, payload)
    await load()
    return updated
  }

  async function remove(id: string): Promise<void> {
    try {
      await mapsApi.remove(id)
    } catch (error) {
      // A 404 means it is already gone — deleted from another tab, or by
      // another operator. The request failed but the intent is satisfied, and
      // reporting failure would leave a row that can never be removed because
      // every retry 404s against the same missing map.
      if (!(error instanceof ApiError && error.isNotFound)) throw error
    }
    maps.value = maps.value.filter((m) => m.id !== id)
  }

  return {
    maps,
    loading,
    loaded,
    error,
    count,
    latestByName,
    isLatest,
    byId,
    load,
    upload,
    replaceImage,
    rename,
    remove,
    describeError: describe,
  }
})
