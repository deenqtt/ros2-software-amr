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
import { computed, ref } from 'vue'

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

export const useAlarmStore = defineStore('alarms', () => {
  const alarms = ref<Alarm[]>([])

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
