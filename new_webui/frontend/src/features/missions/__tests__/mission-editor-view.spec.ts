/**
 * Mission editor: the step list, and what a phone gets on top of it — a
 * sticky Save while there is something to save, and the route map folded.
 */
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { enableAutoUnmount, flushPromises, mount, RouterLinkStub } from '@vue/test-utils'
import type { VueWrapper } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import MissionEditorView from '../views/MissionEditorView.vue'
import CollapsibleSection from '@/shared/components/CollapsibleSection.vue'
import { useAuthStore } from '@/stores/auth'
import type { Role } from '@/domain/auth'
import type { Mission, Station } from '@/domain/types'
import { Select } from '@/shared/ui/select'

vi.mock('vue-sonner', () => ({
  toast: { success: vi.fn(), error: vi.fn(), info: vi.fn(), warning: vi.fn() },
}))

const api = vi.hoisted(() => ({
  get: vi.fn(),
  update: vi.fn(),
  list: vi.fn(),
  maps: vi.fn(),
  fetchFile: vi.fn(),
  stations: vi.fn(),
}))

vi.mock('@/shared/api/missions', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@/shared/api/missions')>()
  return {
    ...actual,
    missionsApi: { ...actual.missionsApi, get: api.get, update: api.update, list: api.list },
  }
})
vi.mock('@/shared/api/maps', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@/shared/api/maps')>()
  return {
    ...actual,
    mapsApi: { ...actual.mapsApi, list: api.maps, fetchFile: api.fetchFile },
  }
})
vi.mock('@/shared/api/stations', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@/shared/api/stations')>()
  return { ...actual, stationsApi: { ...actual.stationsApi, list: api.stations } }
})
vi.mock('@/domain/map/pgm', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@/domain/map/pgm')>()
  return { ...actual, decodePgm: vi.fn(() => ({ width: 1, height: 1, data: new Uint8Array(1) })) }
})

const nav = vi.hoisted(() => ({
  route: { params: { missionId: 'mission-1' }, query: {} },
  router: { push: vi.fn(), replace: vi.fn() },
}))

vi.mock('vue-router', async (importOriginal) => {
  const actual = await importOriginal<typeof import('vue-router')>()
  return { ...actual, useRoute: () => nav.route, useRouter: () => nav.router }
})

/** Copied from collapsible-section.spec.ts: a matchMedia that answers for one width. */
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

function station(id: string, name: string): Station {
  return {
    id,
    mapId: 'map-1',
    name,
    type: 'pick',
    x: 0,
    y: 0,
    yaw: 0,
    note: null,
    taughtByRobotId: null,
    createdAt: '2026-10-01 08:00:00',
    updatedAt: '2026-10-01 08:00:00',
  } as Station
}

const MISSION: Mission = {
  id: 'mission-1',
  mapId: 'map-1',
  name: 'Shuttle',
  note: null,
  steps: [
    { id: 's1', ordinal: 1, stationId: 'a', task: 'pick', confirm: 'auto', note: null },
    { id: 's2', ordinal: 2, stationId: 'b', task: 'drop', confirm: 'auto', note: null },
    { id: 's3', ordinal: 3, stationId: 'c', task: 'none', confirm: 'auto', note: null },
  ],
  createdAt: '2026-10-01 08:00:00',
  updatedAt: '2026-10-01 08:00:00',
}

function signInAs(role: Role) {
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
}

async function mountView(): Promise<VueWrapper> {
  const wrapper = mount(MissionEditorView, {
    attachTo: document.body,
    global: {
      stubs: {
        RouterLink: RouterLinkStub,
        StationMapCanvas: { template: '<div class="map-canvas-stub"><slot name="legend" /></div>' },
      },
    },
  })
  await flushPromises()
  return wrapper
}

/** Select is generic, so its props do not come typed through findAllComponents. */
type SelectProps = { label?: string; modelValue?: string | null; disabled?: boolean }
function selects(wrapper: VueWrapper): SelectProps[] {
  return wrapper.findAllComponents(Select).map((select) => select.props() as SelectProps)
}

/** Step cards, in order, by the station each one names. */
function stepStations(wrapper: VueWrapper): string[] {
  return selects(wrapper)
    .filter((select) => select.label === 'Station')
    .map((select) => String(select.modelValue))
}

function buttonByTitle(wrapper: VueWrapper, title: string, index = 0) {
  return wrapper.findAll(`button[title="${title}"]`)[index]!
}

function saveBar(wrapper: VueWrapper) {
  return wrapper.find('div[class~="sticky"][class~="bottom-0"]')
}

enableAutoUnmount(afterEach)

beforeEach(() => {
  setActivePinia(createPinia())
  signInAs('admin')
  document.body.innerHTML = ''
  nav.router.push.mockReset()
  api.get.mockReset().mockResolvedValue(structuredClone(MISSION))
  api.update.mockReset().mockResolvedValue(structuredClone(MISSION))
  api.list.mockReset().mockResolvedValue([])
  api.maps.mockReset().mockResolvedValue([])
  api.fetchFile.mockReset().mockResolvedValue(new Uint8Array(1))
  api.stations
    .mockReset()
    .mockResolvedValue([station('a', 'Dock A'), station('b', 'Line B'), station('c', 'Bay C')])
})

afterEach(() => delete (window as { matchMedia?: unknown }).matchMedia)

describe('MissionEditorView — steps', () => {
  it('renders one numbered card per step', async () => {
    const wrapper = await mountView()
    expect(stepStations(wrapper)).toEqual(['a', 'b', 'c'])
    const numbers = wrapper.findAll('span.font-data.text-white').map((span) => span.text())
    expect(numbers).toEqual(['1', '2', '3'])
  })

  it('moves a step down and removes one', async () => {
    const wrapper = await mountView()
    await buttonByTitle(wrapper, 'Move down', 0).trigger('click')
    expect(stepStations(wrapper)).toEqual(['b', 'a', 'c'])
    await buttonByTitle(wrapper, 'Remove this step', 2).trigger('click')
    expect(stepStations(wrapper)).toEqual(['b', 'a'])
  })
})

describe('MissionEditorView — phone', () => {
  it('shows a sticky Save once something changed, and it saves', async () => {
    screenWidth(390)
    const wrapper = await mountView()
    expect(saveBar(wrapper).exists()).toBe(false)

    await buttonByTitle(wrapper, 'Move down', 0).trigger('click')
    const bar = saveBar(wrapper)
    expect(bar.exists()).toBe(true)
    expect(bar.text()).toContain('Unsaved changes')

    await bar.get('button').trigger('click')
    await flushPromises()
    expect(api.update).toHaveBeenCalledWith(
      'mission-1',
      expect.objectContaining({ name: 'Shuttle' }),
    )
  })

  it('folds the route map, with the stop count in its header', async () => {
    screenWidth(390)
    const wrapper = await mountView()
    const section = wrapper.getComponent(CollapsibleSection)
    expect(section.text()).toContain('Route map')
    expect(section.text()).toContain('3 stops')
    const header = section.get('button[aria-expanded]')
    expect(header.attributes('aria-expanded')).toBe('false')
    expect(section.get('.map-canvas-stub').isVisible()).toBe(false)
    await header.trigger('click')
    expect(header.attributes('aria-expanded')).toBe('true')
    expect(section.get('.map-canvas-stub').isVisible()).toBe(true)
  })

  it('is view only for a viewer, with no save bar', async () => {
    screenWidth(390)
    signInAs('viewer')
    const wrapper = await mountView()
    expect(wrapper.text()).toContain('View only — editing missions needs the admin role.')
    const all = selects(wrapper)
    expect(all.length).toBeGreaterThan(0)
    expect(all.every((select) => select.disabled === true)).toBe(true)
    expect(saveBar(wrapper).exists()).toBe(false)
  })
})

describe('MissionEditorView — desktop', () => {
  it('keeps the bare map and no save bar', async () => {
    const wrapper = await mountView()
    await buttonByTitle(wrapper, 'Move down', 0).trigger('click')
    expect(wrapper.findComponent(CollapsibleSection).exists()).toBe(false)
    expect(wrapper.find('.map-canvas-stub').exists()).toBe(true)
    expect(saveBar(wrapper).exists()).toBe(false)
  })
})
