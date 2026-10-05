/**
 * Survey page at phone width.
 *
 * The toolbar used to overflow a phone by ~41px. The fix moves the status
 * indicators to their own row, and must never move the emergency stop out of
 * sight while doing it.
 */
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { enableAutoUnmount, flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { ref, shallowRef } from 'vue'
import { createMemoryHistory, createRouter } from 'vue-router'
import SurveyView from '../views/SurveyView.vue'
import { useAuthStore } from '@/stores/auth'
import type { AgentStatus } from '../useRobotTelemetry'
import type { RobotConfig } from '@/domain/types'

vi.mock('vue-sonner', () => ({
  toast: { success: vi.fn(), error: vi.fn(), info: vi.fn(), warning: vi.fn() },
}))

const telemetry = vi.hoisted(() => ({ value: null as unknown }))

vi.mock('../useRobotTelemetry', () => ({
  useRobotTelemetry: () => telemetry.value,
}))

vi.mock('@/app/ros/pool', () => {
  const pool = {
    onSnapshot: vi.fn(),
    sync: vi.fn(),
    clientFor: vi.fn(() => null),
    focus: vi.fn(),
    setMuted: vi.fn(),
  }
  return { useRosPool: () => pool, resetRosPool: vi.fn() }
})

vi.mock('@/shared/composables/useGamepad', async () => {
  const { ref: vueRef } = await import('vue')
  return {
    useGamepad: () => ({
      state: vueRef({
        connected: false,
        id: '',
        standardMapping: true,
        leftX: 0,
        leftY: 0,
        deadmanHeld: false,
      }),
      windowFocused: vueRef(true),
      wasConnected: vueRef(false),
    }),
  }
})

const robotsMock = vi.hoisted(() => ({ list: vi.fn() }))

vi.mock('@/shared/api/robots', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@/shared/api/robots')>()
  return { ...actual, robotsApi: robotsMock }
})

const robot: RobotConfig = {
  id: 'r1',
  name: 'AMR-01',
  bridgeUrl: 'ws://10.0.0.1:8765',
  rosDomainId: null,
  cameraUrl: null,
  namespace: '',
  accent: 1,
  serial: null,
  activeMapId: null,
  desiredMode: 'map',
}

function mappingTelemetry() {
  const agent: AgentStatus = {
    mode: 'map',
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
    scan: shallowRef(null),
    pose: ref(null),
    velocity: ref({ linear: 0, angular: 0 }),
    footprint: ref(null),
    sensorOffset: ref(null),
    agent: ref(agent),
    clear: vi.fn(),
    reattach: vi.fn(),
  }
}

async function mountSurvey() {
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/maps', component: { template: '<div />' } },
      { path: '/maps/survey/:robotId', component: SurveyView },
    ],
  })
  await router.push('/maps/survey/r1')
  await router.isReady()
  const wrapper = mount(SurveyView, {
    attachTo: document.body,
    global: {
      plugins: [router],
      stubs: { LiveMapCanvas: true, DriveJoystick: true },
    },
  })
  await flushPromises()
  return wrapper
}

enableAutoUnmount(afterEach)

beforeEach(() => {
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
  document.body.innerHTML = ''
  robotsMock.list.mockReset().mockResolvedValue([robot])
  telemetry.value = mappingTelemetry()
})

describe('SurveyView — phone layout', () => {
  it('gives the SLAM and link indicators their own row below the toolbar', async () => {
    const wrapper = await mountSurvey()
    const status = wrapper.get('[data-testid="survey-status"]')
    expect(status.classes()).toContain('sm:hidden')
    expect(status.findComponent({ name: 'SlamIndicator' }).exists()).toBe(true)
    expect(status.findComponent({ name: 'LinkIndicator' }).exists()).toBe(true)
  })

  it('keeps the emergency stop in the toolbar, never folded away', async () => {
    const wrapper = await mountSurvey()
    const stop = wrapper.findComponent({ name: 'EmergencyStop' })
    expect(stop.exists()).toBe(true)
    // Nothing between it and the page hides it at any width.
    let node: Element | null = stop.element
    while (node && node !== wrapper.element) {
      expect(node.classList.contains('hidden')).toBe(false)
      expect((node as HTMLElement).style.display).not.toBe('none')
      node = node.parentElement
    }
  })

  it('names the back link even when its label is hidden', async () => {
    const wrapper = await mountSurvey()
    const back = wrapper.get('a[aria-label="Back to maps"]')
    expect(back.attributes('href')).toBe('/maps')
  })

  it('says why there is nothing to save before SLAM publishes a grid', async () => {
    const wrapper = await mountSurvey()
    const save = wrapper.findAll('button').find((b) => b.text().includes('Save map'))!
    expect(save.attributes('disabled')).toBeDefined()
    expect(wrapper.text()).toContain('Nothing to save until SLAM publishes a grid.')
  })

  it('makes the speed presets a finger-sized target on touch', async () => {
    const wrapper = await mountSurvey()
    const presets = wrapper
      .findAll('button')
      .filter((b) => b.classes().includes('flex-1') && b.classes().includes('touch:h-11'))
    expect(presets.length).toBeGreaterThan(1)
  })
})
