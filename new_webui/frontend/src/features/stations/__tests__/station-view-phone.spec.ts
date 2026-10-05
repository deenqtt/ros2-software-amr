/**
 * Station page on a phone.
 *
 * The map keeps the full width and the list is the other half of a Map/List
 * switch. Placing and dragging stations are left to bigger screens, and the
 * page says so in words, because a phone has no hover to show a tooltip.
 */
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { enableAutoUnmount, flushPromises, mount, RouterLinkStub } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { ref } from 'vue'
import StationView from '../views/StationView.vue'
import StationMapCanvas from '../components/StationMapCanvas.vue'
import { useAuthStore } from '@/stores/auth'
import type { Role } from '@/domain/auth'
import type { MapRecord, Station } from '@/domain/types'

vi.mock('vue-sonner', () => ({
  toast: { success: vi.fn(), error: vi.fn(), info: vi.fn(), warning: vi.fn() },
}))

vi.mock('@/features/mapping/useRobotTelemetry', () => ({
  useRobotTelemetry: () => ({ pose: ref(null) }),
}))

function mapRecord(): MapRecord {
  return {
    id: 'm1',
    name: 'Warehouse',
    version: 1,
    contentHash: 'h',
    yamlFile: 'map.yaml',
    imageFile: 'map.pgm',
    imageBytes: 4,
    resolution: 0.05,
    width: 2,
    height: 2,
    originX: 0,
    originY: 0,
    originYaw: 0,
    negate: 0,
    occupiedThresh: 0.65,
    freeThresh: 0.2,
    createdByRobotId: null,
    note: null,
    createdAt: '2026-09-28 08:00:00',
  }
}

function station(): Station {
  return {
    id: 's1',
    mapId: 'm1',
    name: 'Dock 1',
    type: 'pick',
    x: 1,
    y: 2,
    yaw: 0,
    note: 'By the shutter',
    taughtByRobotId: null,
    createdAt: '2026-09-28 08:00:00',
    updatedAt: '2026-09-28 08:00:00',
  }
}

vi.mock('@/shared/api/maps', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@/shared/api/maps')>()
  return {
    ...actual,
    mapsApi: {
      list: vi.fn(async () => [mapRecord()]),
      fetchFile: vi.fn().mockResolvedValue(new Uint8Array()),
    },
  }
})

// The canvas is stubbed, so any grid will do; a real PGM is not the subject.
vi.mock('@/domain/map/pgm', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@/domain/map/pgm')>()
  return { ...actual, decodePgm: () => ({ width: 2, height: 2, cells: new Uint8Array(4) }) }
})

vi.mock('@/shared/api/stations', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@/shared/api/stations')>()
  return { ...actual, stationsApi: { list: vi.fn(async () => [station()]) } }
})

vi.mock('@/shared/api/missions', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@/shared/api/missions')>()
  return {
    ...actual,
    missionsApi: { list: vi.fn().mockResolvedValue([]) },
    runsApi: { list: vi.fn().mockResolvedValue([]) },
  }
})

vi.mock('@/shared/api/robots', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@/shared/api/robots')>()
  return { ...actual, robotsApi: { list: vi.fn().mockResolvedValue([]) } }
})

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

async function mountAs(role: Role, width: number) {
  screenWidth(width)
  setActivePinia(createPinia())
  const auth = useAuthStore()
  auth.user = {
    id: 'u',
    username: 't',
    displayName: null,
    role,
    sessionIdleMinutes: 720,
    mustChangePassword: false,
  }
  auth.status = 'signed-in'
  const wrapper = mount(StationView, {
    attachTo: document.body,
    global: { stubs: { RouterLink: RouterLinkStub, StationMapCanvas: true } },
  })
  await flushPromises()
  return wrapper
}

type Wrapper = Awaited<ReturnType<typeof mountAs>>

const canvas = (wrapper: Wrapper) => wrapper.findComponent(StationMapCanvas)
const radio = (wrapper: Wrapper, label: string) =>
  wrapper.findAll('[role="radio"]').find((b) => b.text().startsWith(label))!
const buttonByText = (wrapper: Wrapper, text: string) =>
  wrapper.findAll('button').find((b) => b.text().includes(text))

async function openRowMenu(wrapper: Wrapper, name: string) {
  await wrapper.get(`button[aria-label="More actions for ${name}"]`).trigger('click')
  await flushPromises()
  const items = [...document.querySelectorAll('[role="menuitem"]')]
  return (label: string) => items.find((item) => item.textContent?.trim() === label) as HTMLElement
}

enableAutoUnmount(afterEach)

beforeEach(() => {
  document.body.innerHTML = ''
})

afterEach(() => delete (window as { matchMedia?: unknown }).matchMedia)

describe('StationView — phone', () => {
  it('gives the map the width and the list a switch', async () => {
    const wrapper = await mountAs('admin', 390)
    expect(radio(wrapper, 'List').text()).toBe('List (1)')
    expect(wrapper.find('button[title="Show the station list"]').exists()).toBe(false)
    expect(wrapper.find('button[title="Hide the station list"]').exists()).toBe(false)
    expect(buttonByText(wrapper, 'Add station')).toBeUndefined()
    expect(canvas(wrapper).props('placing')).toBe(false)
    expect(canvas(wrapper).props('movable')).toBe(false)
  })

  it('lists the stations and says why adding on the map is off', async () => {
    const wrapper = await mountAs('admin', 390)
    await radio(wrapper, 'List').trigger('click')
    expect(wrapper.text()).toContain('Dock 1')
    const add = buttonByText(wrapper, 'Add on map')!
    expect(add.attributes('disabled')).toBeDefined()
    expect(wrapper.text()).toContain('Placing a station on the map needs a tablet or laptop.')
  })

  it('shows a tapped row on the map, with its card and actions', async () => {
    const wrapper = await mountAs('admin', 390)
    await radio(wrapper, 'List').trigger('click')
    await wrapper.get('li button').trigger('click')

    expect(radio(wrapper, 'Map').attributes('aria-checked')).toBe('true')
    expect(canvas(wrapper).props('selectedId')).toBe('s1')
    expect(canvas(wrapper).props('hideLegend')).toBe(true)
    expect(wrapper.text()).toContain('Dock 1')
    // The card shows the detail a list row leaves out.
    expect(wrapper.text()).toContain('By the shutter')

    const item = await openRowMenu(wrapper, 'Dock 1')
    item('Edit').click()
    await flushPromises()
    expect(document.body.textContent).toContain('Edit Dock 1')
  })

  it('closes the card from its button or a tap on empty map', async () => {
    const wrapper = await mountAs('admin', 390)
    await radio(wrapper, 'List').trigger('click')
    await wrapper.get('li button').trigger('click')
    await wrapper.get('button[aria-label="Close"]').trigger('click')
    expect(wrapper.find('button[aria-label="More actions for Dock 1"]').exists()).toBe(false)

    await radio(wrapper, 'List').trigger('click')
    await wrapper.get('li button').trigger('click')
    canvas(wrapper).vm.$emit('select', null)
    await flushPromises()
    expect(wrapper.find('button[aria-label="More actions for Dock 1"]').exists()).toBe(false)
    expect(canvas(wrapper).props('hideLegend')).toBe(false)
  })

  it('shows a viewer the role as the reason, and Edit and Remove disabled', async () => {
    const wrapper = await mountAs('viewer', 390)
    await radio(wrapper, 'List').trigger('click')
    expect(wrapper.text()).toContain('Needs the admin role')
    expect(wrapper.text()).not.toContain('needs a tablet or laptop')
    const item = await openRowMenu(wrapper, 'Dock 1')
    for (const label of ['Edit', 'Remove']) {
      expect(item(label).hasAttribute('data-disabled')).toBe(true)
    }
  })
})

describe('StationView — desktop', () => {
  it('keeps the docked list and drag-to-move', async () => {
    const wrapper = await mountAs('admin', 1366)
    expect(wrapper.find('[role="radiogroup"]').exists()).toBe(false)
    expect(wrapper.find('aside').exists()).toBe(true)
    expect(canvas(wrapper).props('movable')).toBe(true)
    expect(buttonByText(wrapper, 'Add station')).toBeDefined()
  })
})
