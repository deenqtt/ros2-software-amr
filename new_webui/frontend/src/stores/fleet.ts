/**
 * Robot registry, backed by the API.
 *
 * Previously this held the registry in localStorage, which made it
 * per-browser: adding a robot on one laptop left every other machine unaware
 * of it, and nothing survived clearing site data. The records live in the
 * backend now; this store is a cache of them plus the request state the UI
 * needs to render honestly.
 *
 * Writes go to the server first and only then update local state. Optimistic
 * updates would show a robot that the server may have rejected — and this is
 * the registry that decides which machine an operator is about to drive.
 */
import { defineStore } from 'pinia'
import { computed, ref } from 'vue'
import { ApiError } from '@/shared/api/client'
import { robotsApi, RobotConflictError, type RobotDraft } from '@/shared/api/robots'
import { config } from '@/app/config'
import type { DesiredMode, RobotConfig } from '@/domain/types'

function describe(error: unknown): string {
  if (error instanceof RobotConflictError) return error.message
  if (error instanceof ApiError) {
    if (error.isOffline) return `Backend unreachable at ${config.apiBaseUrl}`
    if (error.isNotFound) return 'That robot no longer exists.'
    return error.message || `Request failed (${error.status})`
  }
  return error instanceof Error ? error.message : 'Something went wrong.'
}

export const useFleetStore = defineStore('fleet', () => {
  const robots = ref<RobotConfig[]>([])
  const selectedId = ref<string | null>(null)

  const loading = ref(false)
  const loaded = ref(false)
  const error = ref<string | null>(null)

  const selected = computed(() => robots.value.find((r) => r.id === selectedId.value) ?? null)
  const count = computed(() => robots.value.length)
  const isEmpty = computed(() => loaded.value && robots.value.length === 0)

  function byId(id: string): RobotConfig | null {
    return robots.value.find((r) => r.id === id) ?? null
  }

  function select(id: string | null) {
    selectedId.value = id
  }

  async function load(): Promise<void> {
    loading.value = true
    error.value = null
    try {
      if (config.devLatencyMs > 0) {
        await new Promise((resolve) => setTimeout(resolve, config.devLatencyMs))
      }
      robots.value = await robotsApi.list()
      loaded.value = true
    } catch (cause) {
      // Keep whatever was already on screen rather than blanking the table:
      // stale-but-labelled beats empty-and-silent.
      error.value = describe(cause)
    } finally {
      loading.value = false
    }
  }

  /**
   * Writes throw on failure instead of swallowing the error.
   *
   * The caller has to decide what to do — a form shows the conflict next to the
   * offending field, a toast is not enough. The old UI reported success for
   * writes that never reached anything.
   */
  async function add(draft: RobotDraft): Promise<RobotConfig> {
    const created = await robotsApi.create(draft)
    robots.value = [...robots.value, created].sort((a, b) =>
      a.name.localeCompare(b.name, undefined, { sensitivity: 'base' }),
    )
    return created
  }

  async function update(id: string, patch: Partial<RobotDraft>): Promise<RobotConfig> {
    const updated = await robotsApi.update(id, patch)
    robots.value = robots.value
      .map((robot) => (robot.id === id ? updated : robot))
      .sort((a, b) => a.name.localeCompare(b.name, undefined, { sensitivity: 'base' }))
    return updated
  }

  /**
   * Record what a robot should be doing.
   *
   * Intent, not a command: the robot's agent reconciles towards this on its
   * own sync loop, so this returns as soon as the registry has it rather than
   * waiting for a stack to come up. Without a caller for this the registry
   * could only ever be written by the agent itself, and a parked robot stayed
   * parked with nothing in the UI able to release it.
   */
  async function setMode(id: string, mode: DesiredMode): Promise<RobotConfig> {
    const updated = await robotsApi.setMode(id, mode)
    robots.value = robots.value.map((robot) => (robot.id === id ? updated : robot))
    return updated
  }

  async function remove(id: string): Promise<void> {
    await robotsApi.remove(id)
    robots.value = robots.value.filter((r) => r.id !== id)
    if (selectedId.value === id) selectedId.value = null
  }

  return {
    robots,
    selectedId,
    selected,
    count,
    isEmpty,
    loading,
    loaded,
    error,
    byId,
    select,
    load,
    add,
    update,
    setMode,
    remove,
    describeError: describe,
  }
})
