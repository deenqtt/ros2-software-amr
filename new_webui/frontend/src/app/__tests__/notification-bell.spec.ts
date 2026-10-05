import { afterEach, beforeEach, describe, expect, it } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { createMemoryHistory, createRouter } from 'vue-router'
import NotificationBell from '../layouts/NotificationBell.vue'
import { useAlarmStore } from '@/stores/alarms'

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

function router() {
  return createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/', component: { template: '<div />' } },
      { path: '/alarm', component: { template: '<div />' } },
    ],
  })
}

describe('NotificationBell', () => {
  beforeEach(() => {
    localStorage.clear()
    setActivePinia(createPinia())
  })
  afterEach(() => delete (window as { matchMedia?: unknown }).matchMedia)

  it('is a plain link to the Alarm screen on a phone, keeping the count', async () => {
    screenWidth(390)
    useAlarmStore().raise({ severity: 'fault', source: 'AMR-01', message: 'Navigation aborted' })
    const wrapper = mount(NotificationBell, { global: { plugins: [router()] } })
    await flushPromises()
    const link = wrapper.get('a')
    expect(link.attributes('href')).toBe('/alarm')
    expect(link.attributes('aria-label')).toBe('1 active alarms')
    expect(link.text()).toContain('1')
    expect(wrapper.find('[aria-haspopup]').exists()).toBe(false)
  })

  it('opens a one-line "all clear" on wider screens when nothing is active', async () => {
    screenWidth(1366)
    const wrapper = mount(NotificationBell, {
      global: { plugins: [router()] },
      attachTo: document.body,
    })
    await wrapper.get('button').trigger('click')
    await flushPromises()
    expect(document.body.textContent).toContain('All clear')
    expect(document.body.textContent).toContain('Open alarm log')
    expect(document.body.textContent).not.toContain('Acknowledge all')
    wrapper.unmount()
  })
})
