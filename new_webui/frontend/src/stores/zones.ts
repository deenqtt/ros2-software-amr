/**
 * Zones for one map at a time.
 *
 * Scoped to a map for the same reason stations are: a polygon's coordinates
 * only mean something in one frame. A store holding every zone in the fleet
 * would invite drawing one site's keepout over another site's image, and the
 * result looks entirely plausible.
 *
 * Writes go to the server first and only then update local state.
 */
import { defineStore } from 'pinia'
import { computed, ref } from 'vue'
import { ApiError } from '@/shared/api/client'
import { zonesApi, ZoneNameTakenError, type ZonePatch } from '@/shared/api/zones'
import { config } from '@/app/config'
import type { Zone, ZoneDraft, ZoneKind } from '@/domain/types'

function describe(error: unknown): string {
  if (error instanceof ZoneNameTakenError) return error.message
  if (error instanceof ApiError) {
    if (error.isOffline) return `Backend unreachable at ${config.apiBaseUrl}`
    if (error.isNotFound) return 'That zone no longer exists.'
    return error.readable || `Request failed (${error.status})`
  }
  return error instanceof Error ? error.message : 'Something went wrong.'
}

export const useZoneStore = defineStore('zones', () => {
  const zones = ref<Zone[]>([])
  const mapId = ref<string | null>(null)
  const loading = ref(false)
  const loaded = ref(false)
  const error = ref<string | null>(null)

  const count = computed(() => zones.value.length)

  /**
   * Only the switched-on ones reach a robot.
   *
   * The canvas draws the rest faded, so an operator can see a zone that exists
   * but is doing nothing — which is different from one that is not there.
   */
  const active = computed(() => zones.value.filter((zone) => zone.enabled))

  const countByKind = computed(() => {
    const totals = {} as Record<ZoneKind, number>
    for (const zone of zones.value) {
      totals[zone.kind] = (totals[zone.kind] ?? 0) + 1
    }
    return totals
  })

  function byId(id: string): Zone | null {
    return zones.value.find((zone) => zone.id === id) ?? null
  }

  function nameTaken(name: string, exceptId?: string): boolean {
    const wanted = name.trim().toLocaleLowerCase()
    return zones.value.some(
      (zone) => zone.id !== exceptId && zone.name.toLocaleLowerCase() === wanted,
    )
  }

  async function load(targetMapId: string): Promise<void> {
    loading.value = true
    error.value = null
    try {
      const rows = await zonesApi.list(targetMapId)
      // Assigned together: a list from one map paired with another map's id
      // would draw polygons over the wrong image.
      zones.value = rows
      mapId.value = targetMapId
      loaded.value = true
    } catch (cause) {
      error.value = describe(cause)
      zones.value = []
    } finally {
      loading.value = false
    }
  }

  /** Throws on failure: the caller decides how to surface it. */
  async function create(draft: ZoneDraft): Promise<Zone> {
    const created = await zonesApi.create(draft)
    zones.value = [...zones.value, created]
    return created
  }

  async function update(id: string, patch: ZonePatch): Promise<Zone> {
    const updated = await zonesApi.update(id, patch)
    zones.value = zones.value.map((zone) => (zone.id === id ? updated : zone))
    return updated
  }

  async function remove(id: string): Promise<void> {
    try {
      await zonesApi.remove(id)
    } catch (cause) {
      // Already gone is the outcome that was asked for. Reporting failure
      // leaves a row that can never be removed, because every retry 404s.
      if (!(cause instanceof ApiError && cause.isNotFound)) throw cause
    }
    zones.value = zones.value.filter((zone) => zone.id !== id)
  }

  return {
    zones,
    active,
    countByKind,
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
