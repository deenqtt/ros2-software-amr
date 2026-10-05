/**
 * Alarm page: every active alarm acknowledges on its own row, and a phone
 * shows the latest part of the log with the rest one tap away.
 */
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { enableAutoUnmount, flushPromises, mount, RouterLinkStub } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import AlarmView from '../views/AlarmView.vue'
import { useAlarmStore, type Alarm } from '@/stores/alarms'

function screenWidth(width: number) {
  window.matchMedia = ((query: string) => ({
    matches: width <= Number(/max-width:\s*(\d+)px/.exec(query)?.[1] ?? Infinity),
    media: query,
    onchange: null,
    addEventListener: () => {},
    removeEventListener: () => {},
    addListener: () => {},
    removeListener: () => {},
    dispatchEvent: () => false,
  })) as typeof window.matchMedia
}

const NOW = Date.now()

function alarm(overrides: Partial<Alarm> & Pick<Alarm, 'id'>): Alarm {
  return {
    severity: 'info',
    source: 'AMR-01',
    message: 'Reached Dock',
    raisedAt: NOW - 60_000,
    acknowledgedAt: null,
    ...overrides,
  }
}

function seed() {
  const alarms = useAlarmStore()
  alarms.alarms = [
    alarm({
      id: 'f1',
      severity: 'fault',
      message: 'Shuttle failed at Dock',
      robotId: 'r1',
      missionId: 'm9',
    }),
    alarm({ id: 'w1', severity: 'warning', source: 'Server', message: 'Lost the link' }),
    ...Array.from({ length: 25 }, (_, i) =>
      alarm({ id: `h${i}`, message: `Logged event ${i}`, raisedAt: NOW - 120_000 - i * 1000 }),
    ),
  ]
  return alarms
}

function mountView() {
  return mount(AlarmView, {
    attachTo: document.body,
    global: { stubs: { RouterLink: RouterLinkStub } },
  })
}

/** The active card's list is the first `ul`; the log's is the second. */
function activeRows(wrapper: ReturnType<typeof mountView>) {
  return wrapper.findAll('ul')[0]!.findAll('li')
}
function logRows(wrapper: ReturnType<typeof mountView>) {
  return wrapper.findAll('ul')[1]!.findAll('li')
}
function buttonLabelled(wrapper: ReturnType<typeof mountView>, label: string) {
  return wrapper.findAll('button').find((b) => b.text().trim() === label)
}

enableAutoUnmount(afterEach)

beforeEach(() => {
  localStorage.clear()
  setActivePinia(createPinia())
})

afterEach(() => delete (window as { matchMedia?: unknown }).matchMedia)

describe('AlarmView', () => {
  it('shows the whole log on a wide screen', () => {
    seed()
    const wrapper = mountView()
    expect(logRows(wrapper)).toHaveLength(25)
    expect(wrapper.text()).not.toContain('Show all')
  })

  it('shows the latest 20 on a phone, and the rest on a tap', async () => {
    screenWidth(390)
    seed()
    const wrapper = mountView()
    expect(logRows(wrapper)).toHaveLength(20)
    expect(logRows(wrapper)[0]!.text()).toContain('Logged event 0')
    await buttonLabelled(wrapper, 'Show all 25')!.trigger('click')
    expect(logRows(wrapper)).toHaveLength(25)
    expect(wrapper.text()).not.toContain('Show all')
  })

  it('gives every active alarm its own Acknowledge', async () => {
    const alarms = seed()
    const spy = vi.spyOn(alarms, 'acknowledge')
    const wrapper = mountView()
    const rows = activeRows(wrapper)
    expect(rows).toHaveLength(2)
    for (const row of rows) {
      expect(row.findAll('button').filter((b) => b.text() === 'Acknowledge')).toHaveLength(1)
    }
    await rows[1]!.findAll('button').find((b) => b.text() === 'Acknowledge')!.trigger('click')
    expect(spy).toHaveBeenCalledWith('w1')
    expect(alarms.activeCount).toBe(1)
    expect(alarms.history.some((a) => a.id === 'w1')).toBe(true)
  })

  it('offers Acknowledge all only when there is more than one', async () => {
    const alarms = seed()
    const wrapper = mountView()
    await buttonLabelled(wrapper, 'Acknowledge all')!.trigger('click')
    expect(alarms.activeCount).toBe(0)

    alarms.alarms.push(alarm({ id: 'f2', severity: 'fault', message: 'Bumper hit' }))
    await flushPromises()
    expect(alarms.activeCount).toBe(1)
    expect(buttonLabelled(wrapper, 'Acknowledge all')).toBeUndefined()
  })

  it('links an alarm to its robot and its mission', () => {
    seed()
    const wrapper = mountView()
    const [robot, mission] = activeRows(wrapper)[0]!.findAllComponents(RouterLinkStub)
    expect(robot!.props('to')).toBe('/robot/r1/nav')
    expect(mission!.props('to')).toBe('/mission/edit/m9')
    expect(mission!.text()).toBe('Open mission')
  })

  it('clears the log after confirming, and keeps what is active', async () => {
    const alarms = seed()
    const wrapper = mountView()
    await buttonLabelled(wrapper, 'Clear log')!.trigger('click')
    await flushPromises()
    const dialog = document.querySelector('[role="alertdialog"]')!
    expect(dialog.textContent).toContain('Clear the log?')
    const confirm = [...dialog.querySelectorAll('button')].find(
      (b) => b.textContent?.trim() === 'Clear log',
    )!
    confirm.click()
    await flushPromises()
    expect(alarms.history).toHaveLength(0)
    expect(alarms.activeCount).toBe(2)
  })
})
