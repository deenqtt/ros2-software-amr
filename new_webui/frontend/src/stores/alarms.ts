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
  /** The robot it concerns, so the alarm can link to it. */
  robotId?: string | null
  /** The mission it concerns, likewise. */
  missionId?: string | null
}

/**
 * Only faults and warnings are alarms.
 *
 * An alarm is something an operator has to act on (ISA-18.2). "Started",
 * "reached a stop" and "finished" are the system working; they go in the log.
 * Making them alarms put five acknowledge buttons per route in front of the one
 * fault that mattered, and taught "Acknowledge all" as a reflex.
 */
export function isAlarm(alarm: Pick<Alarm, 'severity'>): boolean {
  return alarm.severity !== 'info'
}

const SEVERITY_RANK: Record<AlarmSeverity, number> = { fault: 0, warning: 1, info: 2 }

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

  /** Newest first — an operator reads the most recent event, not the oldest. */
  const ordered = computed(() => [...alarms.value].sort((a, b) => b.raisedAt - a.raisedAt))

  /** Unacknowledged faults, then warnings, newest first within each. */
  const active = computed(() =>
    alarms.value
      .filter((a) => isAlarm(a) && a.acknowledgedAt === null)
      .sort((a, b) => SEVERITY_RANK[a.severity] - SEVERITY_RANK[b.severity] || b.raisedAt - a.raisedAt),
  )
  const activeCount = computed(() => active.value.length)
  const faultCount = computed(() => active.value.filter((a) => a.severity === 'fault').length)

  /** Everything that is not waiting on the operator: events, and handled alarms. */
  const history = computed(() => ordered.value.filter((a) => !isAlarm(a) || a.acknowledgedAt !== null))

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

  /** Drop the log, keeping anything still waiting to be acknowledged. */
  function clearHistory() {
    alarms.value = alarms.value.filter((a) => isAlarm(a) && a.acknowledgedAt === null)
  }

  return {
    alarms,
    active,
    activeCount,
    faultCount,
    history,
    ordered,
    raise,
    acknowledge,
    acknowledgeAll,
    clear,
    clearHistory,
  }
})
