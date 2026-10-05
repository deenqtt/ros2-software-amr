/**
 * The Navigation page per screen size.
 *
 * On a phone the status panel used to stay docked and take half the width,
 * leaving the map a strip. It is now a bottom sheet with a one-line peek bar;
 * tablets start with it folded; desktop keeps the docked panel.
 */
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { enableAutoUnmount, flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { defineComponent, h, ref, shallowRef } from 'vue'
import { createMemoryHistory, createRouter } from 'vue-router'
import RobotNavigationView from '../views/RobotNavigationView.vue'
import { useAuthStore } from '@/stores/auth'
import { useFleetStore } from '@/stores/fleet'
import { useLinkStore } from '@/stores/links'
import { useMapStore } from '@/stores/maps'
import type { AgentStatus } from '@/features/mapping/useRobotTelemetry'
import type { RobotConfig } from '@/domain/types'

vi.mock('vue-sonner', () => ({
  toast: { success: vi.fn(), error: vi.fn(), info: vi.fn(), warning: vi.fn() },
}))

const telemetry = vi.hoisted(() => ({ value: null as unknown }))

vi.mock('@/features/mapping/useRobotTelemetry', () => ({
  useRobotTelemetry: () => telemetry.value,
}))

vi.mock('@/app/ros/pool', () => {
  const pool = {
    onSnapshot: vi.fn(() => () => undefined),
    sync: vi.fn(),
    clientFor: vi.fn(() => null),
    focus: vi.fn(),
    setMuted: vi.fn(),
    setOptionalTopics: vi.fn(),
  }
  return { useRosPool: () => pool, resetRosPool: vi.fn() }
})

vi.mock('@/shared/api/missions', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@/shared/api/missions')>()
  return {
    ...actual,
    missionsApi: { list: vi.fn(async () => []), get: vi.fn() },
    runsApi: { list: vi.fn(async () => []) },
  }
})

// The canvas draws with <canvas>, which jsdom lacks; only its legend slot matters here.
vi.mock('../components/RobotMapCanvas.vue', () => ({
  default: defineComponent({
    name: 'RobotMapCanvas',
    setup(_, { slots }) {
      return () => h('div', { 'data-testid': 'map' }, slots.legend?.())
    },
  }),
}))

const robot: RobotConfig = {
  id: 'r1',
  name: 'AMR-01',
  bridgeUrl: 'ws://10.0.0.1:8765',
  rosDomainId: null,
  cameraUrl: null,
  namespace: '',
  accent: 1,
  serial: null,
  // No map: keeps the zone, station and mission loads out of the test.
  activeMapId: null,
  desiredMode: 'nav',
}

/** Make the ui store's width queries answer as a screen this wide would. */
function setScreen(width: number) {
  window.matchMedia = ((query: string) => {
    const max = /max-width:\s*(\d+)px/.exec(query)
    const min = /min-width:\s*(\d+)px/.exec(query)
    const matches = (max ? width <= Number(max[1]) : true) && (min ? width >= Number(min[1]) : true)
    return {
      matches: max || min ? matches : false,
      media: query,
      onchange: null,
      addListener: () => undefined,
      removeListener: () => undefined,
      addEventListener: () => undefined,
      removeEventListener: () => undefined,
      dispatchEvent: () => false,
    }
  }) as typeof window.matchMedia
}

function navTelemetry() {
  const agent: AgentStatus = {
    mode: 'nav',
    state: 'running',
    map: '',
    mapId: '',
    detail: '',
    managed: true,
    backend: 'ok',
    teleop: false,
  }
  return {
    grid: shallowRef(null),
    costmap: shallowRef(null),
    plan: shallowRef(null),
    particles: shallowRef(null),
    scan: shallowRef(null),
    pose: ref(null),
    velocity: ref({ linear: 0, angular: 0 }),
    footprint: ref(null),
    sensorOffset: ref(null),
    agent: ref(agent),
    goalOutcome: ref('idle'),
    goalFailure: ref(null),
    stall: ref({ stalled: false, stillFor: 0 }),
    clear: vi.fn(),
    reattach: vi.fn(),
  }
}

async function mountNav(width: number) {
  setScreen(width)
  setActivePinia(createPinia())
  const auth = useAuthStore()
  auth.user = {
    id: 'u',
    username: 't',
    displayName: null,
    role: 'operator',
    sessionIdleMinutes: 720,
    mustChangePassword: false,
  }
  auth.status = 'signed-in'
  const fleet = useFleetStore()
  fleet.robots = [robot]
  fleet.loaded = true
  useMapStore().loaded = true
  useLinkStore().links = { r1: { state: 'online', attempt: 0, lastError: null, topics: [] } }

  const router = createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/robot', component: { template: '<div />' } },
      { path: '/maps', component: { template: '<div />' } },
      { path: '/robot/:robotId/detail', component: { template: '<div />' } },
      { path: '/robot/:robotId/nav', component: RobotNavigationView },
    ],
  })
  await router.push('/robot/r1/nav')
  await router.isReady()
  const wrapper = mount(RobotNavigationView, {
    attachTo: document.body,
    global: { plugins: [router], stubs: { RobotBar: true } },
  })
  await flushPromises()
  return wrapper
}

enableAutoUnmount(afterEach)

beforeEach(() => {
  document.body.innerHTML = ''
  telemetry.value = navTelemetry()
})

describe('RobotNavigationView — phone', () => {
  it('shows a collapsed peek bar with the verdict, and expands into the full panel', async () => {
    const wrapper = await mountNav(390)
    const toggle = wrapper.get('[data-testid="nav-peek-toggle"]')
    expect(toggle.attributes('aria-expanded')).toBe('false')
    expect(wrapper.get('[data-testid="nav-verdict"]').text()).not.toBe('')
    expect(wrapper.findAll('button').some((b) => b.text().includes('Start mission'))).toBe(false)
    expect(wrapper.text()).not.toContain('Status & mission')

    await toggle.trigger('click')
    expect(toggle.attributes('aria-expanded')).toBe('true')
    expect(wrapper.find('#nav-sheet-body').exists()).toBe(true)
    expect(wrapper.findAll('button').some((b) => b.text().includes('Start mission'))).toBe(true)
    const terms = wrapper.findAll('dt').map((dt) => dt.text())
    expect(terms).toContain('Stack')
    expect(terms).toContain('Pose')
  })

  it('labels the icon-only map tools for assistive tech', async () => {
    const wrapper = await mountNav(390)
    const radios = wrapper.findAll('[role="radio"]')
    expect(radios).toHaveLength(3)
    for (const radio of radios) {
      expect(['Pan', 'Set pose', 'Go here']).toContain(radio.attributes('aria-label'))
      expect(radio.attributes('title')).toBeTruthy()
    }
    expect(wrapper.find('[aria-label="Map layers"]').exists()).toBe(true)
  })

  it('moves the zone legend out of the map strip', async () => {
    const wrapper = await mountNav(390)
    expect(wrapper.get('[data-testid="map"]').text()).toBe('')
  })

  it('folds the sheet when a map tool is armed', async () => {
    const wrapper = await mountNav(390)
    const toggle = wrapper.get('[data-testid="nav-peek-toggle"]')
    await toggle.trigger('click')
    expect(toggle.attributes('aria-expanded')).toBe('true')

    const setPose = wrapper.get('[role="radio"][aria-label="Set pose"]')
    expect(setPose.attributes('disabled')).toBeUndefined()
    await setPose.trigger('click')
    expect(setPose.attributes('aria-checked')).toBe('true')
    expect(toggle.attributes('aria-expanded')).toBe('false')
  })
})

describe('RobotNavigationView — larger screens', () => {
  it('keeps the docked panel on desktop', async () => {
    const wrapper = await mountNav(1280)
    expect(wrapper.text()).toContain('Status & mission')
    expect(wrapper.find('dl').exists()).toBe(true)
    expect(wrapper.find('[data-testid="nav-peek-toggle"]').exists()).toBe(false)
    // The legend stays on the map strip.
    expect(wrapper.get('[data-testid="map"]').text()).not.toBe('')
  })

  it('starts folded on a tablet, map first', async () => {
    const wrapper = await mountNav(900)
    const header = wrapper.get('aside button[aria-expanded]')
    expect(header.attributes('aria-expanded')).toBe('false')
    expect(wrapper.find('dl').exists()).toBe(false)
    expect(wrapper.find('[data-testid="nav-peek-toggle"]').exists()).toBe(false)
  })
})
