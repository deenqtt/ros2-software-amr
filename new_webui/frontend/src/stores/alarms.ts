/**
 * Alarms.
 *
 * Backs both the Alarm destination and the header bell. Acknowledging an
 * alarm silences the count but keeps the record — an operator needs to be
 * able to answer "what happened at 14:20" after the fact, which the old UI
 * could not do at all: its errors were toasts that vanished after three
 * seconds, and the ones raised by the ROS layer were never rendered.
 */
import { defineStore } from 'pinia'
import { computed, ref, watch } from 'vue'

export type AlarmSeverity = 'fault' | 'warning' | 'info'

export interface Alarm {
  id: string
  severity: AlarmSeverity
  /** Where it came from: a robot name, a subsystem, a service. */
  source: string
  message: string
  raisedAt: number
  acknowledgedAt: number | null
}

/**
 * Kept in this browser so a refresh does not wipe "what happened at 14:20".
 *
 * Per browser, not shared: the run history on the server is the record that
 * every operator sees. This is the operator's own inbox of it.
 */
const STORAGE_KEY = 'amr.alarms.v1'
/** Enough for a shift. Oldest are dropped first. */
const KEEP = 200

function restore(): Alarm[] {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    const parsed: unknown = raw ? JSON.parse(raw) : []
    return Array.isArray(parsed) ? (parsed as Alarm[]) : []
  } catch {
    // Blocked storage or a corrupt entry: start empty rather than not at all.
    return []
  }
}

export const useAlarmStore = defineStore('alarms', () => {
  const alarms = ref<Alarm[]>(restore())

  watch(
    alarms,
    (list) => {
      try {
        localStorage.setItem(STORAGE_KEY, JSON.stringify(list.slice(-KEEP)))
      } catch {
        // Full or blocked. The alarms still work for this session.
      }
    },
    { deep: true },
  )

  const active = computed(() => alarms.value.filter((a) => a.acknowledgedAt === null))
  const activeCount = computed(() => active.value.length)
  const faultCount = computed(() => active.value.filter((a) => a.severity === 'fault').length)

  /** Newest first — an operator reads the most recent event, not the oldest. */
  const ordered = computed(() => [...alarms.value].sort((a, b) => b.raisedAt - a.raisedAt))

  function raise(alarm: Omit<Alarm, 'id' | 'raisedAt' | 'acknowledgedAt'>): Alarm {
    const created: Alarm = {
      ...alarm,
      id: crypto.randomUUID(),
      raisedAt: Date.now(),
      acknowledgedAt: null,
    }
    alarms.value.push(created)
    if (alarms.value.length > KEEP) alarms.value.splice(0, alarms.value.length - KEEP)
    return created
  }

  function acknowledge(id: string) {
    const alarm = alarms.value.find((a) => a.id === id)
    if (alarm && alarm.acknowledgedAt === null) alarm.acknowledgedAt = Date.now()
  }

  function acknowledgeAll() {
    const now = Date.now()
    for (const alarm of alarms.value) {
      if (alarm.acknowledgedAt === null) alarm.acknowledgedAt = now
    }
  }

  function clear() {
    alarms.value = []
  }

  return { alarms, active, activeCount, faultCount, ordered, raise, acknowledge, acknowledgeAll, clear }
})
