import { beforeEach, describe, expect, it } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import { useAlarmStore } from '@/stores/alarms'

beforeEach(() => {
  localStorage.clear()
  setActivePinia(createPinia())
})

describe('alarm store', () => {
  it('does not count routine events as alarms', () => {
    const alarms = useAlarmStore()
    alarms.raise({ severity: 'info', source: 'AMR-01', message: 'Reached Dock' })
    alarms.raise({ severity: 'info', source: 'AMR-01', message: 'Finished Shuttle' })
    expect(alarms.activeCount).toBe(0)
    expect(alarms.history).toHaveLength(2)
  })

  it('puts faults ahead of newer warnings', () => {
    const alarms = useAlarmStore()
    alarms.raise({ severity: 'fault', source: 'AMR-01', message: 'Shuttle failed' })
    alarms.raise({ severity: 'warning', source: 'AMR-02', message: 'Lost the link' })
    expect(alarms.active.map((a) => a.severity)).toEqual(['fault', 'warning'])
    expect(alarms.faultCount).toBe(1)
  })

  it('moves an acknowledged alarm to the log', () => {
    const alarms = useAlarmStore()
    const raised = alarms.raise({ severity: 'fault', source: 'AMR-01', message: 'Shuttle failed' })
    alarms.acknowledge(raised.id)
    expect(alarms.activeCount).toBe(0)
    expect(alarms.history.map((a) => a.id)).toEqual([raised.id])
  })

  it('clears the log without touching what is still active', () => {
    const alarms = useAlarmStore()
    alarms.raise({ severity: 'info', source: 'AMR-01', message: 'Started Shuttle' })
    const open = alarms.raise({ severity: 'warning', source: 'AMR-02', message: 'Lost the link' })
    alarms.clearHistory()
    expect(alarms.alarms.map((a) => a.id)).toEqual([open.id])
  })
})
