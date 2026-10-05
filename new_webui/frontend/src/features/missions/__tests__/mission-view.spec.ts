/**
 * Mission page: the phone list, the Running now controls, and the map picker
 * that appears twice (its own row on a phone, the toolbar from md).
 *
 * jsdom applies no CSS, so the phone list and the table both render; queries
 * are scoped to one or the other.
 */
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { enableAutoUnmount, flushPromises, mount, RouterLinkStub } from '@vue/test-utils'
import type { DOMWrapper, VueWrapper } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import MissionView from '../views/MissionView.vue'
import { useAuthStore } from '@/stores/auth'
import type { Role } from '@/domain/auth'
import type { MapRecord, MissionRun, MissionSummary, RobotConfig } from '@/domain/types'
import { Select } from '@/shared/ui/select'

vi.mock('vue-sonner', () => ({
  toast: { success: vi.fn(), error: vi.fn(), info: vi.fn(), warning: vi.fn() },
}))

const api = vi.hoisted(() => ({
  robots: vi.fn(),
  maps: vi.fn(),
  stations: vi.fn(),
  missions: vi.fn(),
  runs: vi.fn(),
}))

vi.mock('@/shared/api/robots', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@/shared/api/robots')>()
  return { ...actual, robotsApi: { ...actual.robotsApi, list: api.robots } }
})
vi.mock('@/shared/api/maps', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@/shared/api/maps')>()
  return { ...actual, mapsApi: { ...actual.mapsApi, list: api.maps } }
})
vi.mock('@/shared/api/stations', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@/shared/api/stations')>()
  return { ...actual, stationsApi: { ...actual.stationsApi, list: api.stations } }
})
vi.mock('@/shared/api/missions', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@/shared/api/missions')>()
  return {
    ...actual,
    missionsApi: { ...actual.missionsApi, list: api.missions },
    runsApi: { ...actual.runsApi, list: api.runs },
  }
})

const nav = vi.hoisted(() => ({
  route: { query: {} as Record<string, string> },
  router: { push: vi.fn(), replace: vi.fn() },
}))

vi.mock('vue-router', async (importOriginal) => {
  const actual = await importOriginal<typeof import('vue-router')>()
  return { ...actual, useRoute: () => nav.route, useRouter: () => nav.router }
})

function map(id: string, name: string): MapRecord {
  return {
    id,
    name,
    version: 1,
    contentHash: 'h',
    yamlFile: 'map.yaml',
    imageFile: 'map.pgm',
    imageBytes: 1,
    resolution: 0.05,
    width: 10,
    height: 10,
    originX: 0,
    originY: 0,
    originYaw: 0,
    negate: 0,
    occupiedThresh: 0.65,
    freeThresh: 0.2,
    createdByRobotId: null,
    note: null,
    createdAt: '2026-10-01 08:00:00',
  }
}

function robot(overrides: Partial<RobotConfig> = {}): RobotConfig {
  return {
    id: 'robot-1',
    name: 'R1',
    bridgeUrl: 'ws://10.0.0.1:9090',
    rosDomainId: null,
    cameraUrl: null,
    namespace: '',
    accent: 1,
    serial: null,
    activeMapId: 'map-1',
    desiredMode: 'nav',
    ...overrides,
  } as RobotConfig
}

function mission(overrides: Partial<MissionSummary> = {}): MissionSummary {
  return {
    id: 'mission-1',
    mapId: 'map-1',
    name: 'Shuttle',
    note: null,
    stepCount: 4,
    stationIds: ['a', 'b', 'c', 'd'],
    createdAt: '2026-10-01 08:00:00',
    updatedAt: '2026-10-01 08:00:00',
    ...overrides,
  }
}

function run(overrides: Partial<MissionRun> = {}): MissionRun {
  return {
    id: 'run-1',
    missionId: 'mission-1',
    missionName: 'Shuttle',
    robotId: 'robot-1',
    mode: 'laps',
    lapsTarget: 5,
    lap: 1,
    stepIndex: 1,
    reachedLap: null,
    reachedIndex: null,
    reachedAt: null,
    state: 'running',
    detail: null,
    startedAt: '2026-10-01 08:00:00',
    endedAt: null,
    ...overrides,
  }
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
  const wrapper = mount(MissionView, {
    attachTo: document.body,
    global: { stubs: { RouterLink: RouterLinkStub } },
  })
  await flushPromises()
  return wrapper
}

/** The phone list: the `md:hidden` one, not the skeleton. */
function phoneList(wrapper: VueWrapper) {
  return wrapper.get('ul[class~="md:hidden"]')
}

function buttonByText(
  scope: Pick<DOMWrapper<Element>, 'findAll'>,
  text: string,
): DOMWrapper<HTMLButtonElement> {
  const found = scope.findAll('button').find((button) => button.text().trim() === text)
  if (!found) throw new Error(`no button "${text}"`)
  return found as DOMWrapper<HTMLButtonElement>
}

async function openMenu(scope: Pick<DOMWrapper<Element>, 'get'>): Promise<Element> {
  await scope.get('button[aria-label^="More actions"]').trigger('click')
  await flushPromises()
  const menu = document.querySelector('[role="menu"]')
  if (!menu) throw new Error('row menu did not open')
  return menu
}

function menuItem(menu: Element, label: string): HTMLElement {
  const item = [...menu.querySelectorAll('[role="menuitem"]')].find(
    (element) => element.textContent?.trim() === label,
  )
  if (!item) throw new Error(`no menu item "${label}"`)
  return item as HTMLElement
}

enableAutoUnmount(afterEach)

beforeEach(() => {
  setActivePinia(createPinia())
  signInAs('admin')
  document.body.innerHTML = ''
  nav.route.query = {}
  nav.router.push.mockReset()
  nav.router.replace.mockReset()
  api.robots.mockReset().mockResolvedValue([robot()])
  api.maps.mockReset().mockResolvedValue([map('map-1', 'Floor A'), map('map-2', 'Floor B')])
  api.stations.mockReset().mockResolvedValue([])
  api.missions
    .mockReset()
    .mockResolvedValue([mission(), mission({ id: 'mission-2', name: 'Loop B' })])
  api.runs.mockReset().mockResolvedValue([])
})

describe('MissionView — phone list', () => {
  it('has one row per mission, each opening its editor', async () => {
    const wrapper = await mountView()
    const rows = phoneList(wrapper).findAll('li')
    expect(rows).toHaveLength(2)
    const links = phoneList(wrapper).findAllComponents(RouterLinkStub)
    expect(links.map((link: { props: () => { to?: unknown } }) => link.props().to)).toEqual([
      '/mission/edit/mission-1',
      '/mission/edit/mission-2',
    ])
    expect(rows[1]!.text()).toContain('Loop B')
    expect(rows[1]!.text()).toContain('Never run')
  })

  it('says which robot is running a mission and how far along', async () => {
    api.runs.mockResolvedValue([run()])
    const wrapper = await mountView()
    expect(phoneList(wrapper).findAll('li')[0]!.text()).toContain('Running · R1 · step 2 of 4')
  })

  it('disables Run with the reason when no robot has this map', async () => {
    api.robots.mockResolvedValue([robot({ activeMapId: 'map-2' })])
    // From the URL; left to itself the page would open on the robot's map.
    nav.route.query = { map: 'map-1' }
    const wrapper = await mountView()
    const runButton = buttonByText(phoneList(wrapper).findAll('li')[0]!, 'Run')
    expect(runButton.element.disabled).toBe(true)
    expect(runButton.attributes('title')).toBe('No robot is on this map')
  })

  it('opens the Run dialog from the row', async () => {
    const wrapper = await mountView()
    const runButton = buttonByText(phoneList(wrapper).findAll('li')[0]!, 'Run')
    expect(runButton.element.disabled).toBe(false)
    await runButton.trigger('click')
    await flushPromises()
    expect(document.body.textContent).toContain('Run Shuttle')
  })

  it('offers Edit and Remove in the row menu to an admin', async () => {
    const wrapper = await mountView()
    const menu = await openMenu(phoneList(wrapper).findAll('li')[0]!)
    expect(menuItem(menu, 'Edit')).toBeTruthy()
    expect(menuItem(menu, 'Remove').hasAttribute('data-disabled')).toBe(false)
  })

  it('offers View, and a disabled Remove, to a viewer', async () => {
    signInAs('viewer')
    const wrapper = await mountView()
    const menu = await openMenu(phoneList(wrapper).findAll('li')[0]!)
    expect(menuItem(menu, 'View')).toBeTruthy()
    expect(menuItem(menu, 'Remove').hasAttribute('data-disabled')).toBe(true)
  })

  it('keeps the table, with its own Run, Edit and menu', async () => {
    const wrapper = await mountView()
    const table = wrapper.get('table')
    expect(table.findAll('tbody tr')).toHaveLength(2)
    expect(buttonByText(table, 'Run')).toBeTruthy()
    expect(buttonByText(table, 'Edit')).toBeTruthy()
  })
})

describe('MissionView — map picker', () => {
  it('renders twice and either one switches the map', async () => {
    const wrapper = await mountView()
    const pickers = wrapper
      .findAllComponents(Select)
      .filter((s) => (s.props() as { label?: string }).label === 'Map')
    expect(pickers).toHaveLength(2)

    for (const picker of pickers) {
      api.missions.mockClear()
      nav.router.replace.mockClear()
      const target = picker === pickers[0] ? 'map-2' : 'map-1'
      picker.vm.$emit('update:modelValue', target)
      await flushPromises()
      expect(api.missions).toHaveBeenCalledWith(target)
      expect(nav.router.replace).toHaveBeenCalledWith({ query: { map: target } })
      nav.route.query = { map: target }
    }
  })
})

describe('MissionView — Running now', () => {
  it('offers Watch, Stop after lap and Cancel for a running run', async () => {
    api.runs.mockResolvedValue([run()])
    const wrapper = await mountView()
    const card = wrapper.findAll('div').find((div) => div.text().startsWith('Running now'))!
    expect(card.text()).toContain('Watch')
    expect(buttonByText(card, 'Stop after lap')).toBeTruthy()
    expect(buttonByText(card, 'Cancel')).toBeTruthy()
  })

  it('shows the stopping badge in place of Stop after lap', async () => {
    api.runs.mockResolvedValue([run({ state: 'stopping' })])
    const wrapper = await mountView()
    const card = wrapper.findAll('div').find((div) => div.text().startsWith('Running now'))!
    expect(card.text()).toContain('stopping after this lap')
    expect(card.findAll('button').some((b) => b.text().includes('Stop after lap'))).toBe(false)
    expect(buttonByText(card, 'Cancel')).toBeTruthy()
  })
})
