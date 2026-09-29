/**
 * Robot page behaviour.
 *
 * Covers the three things a table + modal screen gets wrong most often: the
 * skeleton not matching the real column count, the edit dialog opening with
 * stale values, and an unset optional field rendering as a value.
 */
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { enableAutoUnmount, flushPromises, mount, RouterLinkStub } from '@vue/test-utils'
import type { VueWrapper } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import RobotView from '../views/RobotView.vue'
import { useFleetStore } from '@/stores/fleet'
import { useLinkStore } from '@/stores/links'
import { ApiError } from '@/shared/api/client'
import { RobotConflictError } from '@/shared/api/robots'
import type { RobotConfig } from '@/domain/types'

vi.mock('vue-sonner', () => ({
  toast: { success: vi.fn(), error: vi.fn(), info: vi.fn(), warning: vi.fn() },
}))

/**
 * Stub the transport, keep everything else real.
 *
 * importActual preserves RobotConflictError, which the view imports and
 * matches on — replacing the whole module would make `instanceof` silently
 * false and hide the very branch these tests exist to cover.
 */
// vi.hoisted, because vi.mock is lifted above ordinary const declarations —
// a plain object here is still in its temporal dead zone when the factory runs.
const apiMock = vi.hoisted(() => ({
  list: vi.fn(),
  create: vi.fn(),
  update: vi.fn(),
  remove: vi.fn(),
}))

vi.mock('@/shared/api/robots', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@/shared/api/robots')>()
  return { ...actual, robotsApi: apiMock }
})

/**
 * No real sockets. roslibjs would open a WebSocket per robot against an
 * address nothing is listening on, which in jsdom means a pile of async
 * failures unrelated to anything these tests assert.
 */
const poolMock = vi.hoisted(() => ({
  sync: vi.fn(),
  focus: vi.fn(),
  setMuted: vi.fn(),
  isMuted: vi.fn(() => false),
  clientFor: vi.fn(() => null),
  onSnapshot: vi.fn(() => () => {}),
  dispose: vi.fn(),
}))

vi.mock('@/app/ros/pool', () => ({
  useRosPool: () => poolMock,
  resetRosPool: () => {},
}))

const COLUMNS = 6

function robot(overrides: Partial<RobotConfig> = {}): RobotConfig {
  return {
    id: 'robot-1',
    name: 'AMR-01',
    bridgeUrl: 'ws://192.168.1.50:8765',
    rosDomainId: null,
    cameraUrl: null,
    namespace: '',
    accent: 1,
    serial: null,
    activeMapId: null,
    desiredMode: 'nav',
    ...overrides,
  }
}

/** Mount and let the component's own load() populate the store from the API. */
// RouterLink needs a router; stubbing it keeps these tests about the table
// rather than about routing, which shell.spec.ts already covers.
const mountOptions = {
  attachTo: document.body,
  global: { stubs: { RouterLink: RouterLinkStub } },
}

async function mountView(robots: RobotConfig[]) {
  apiMock.list.mockResolvedValue(robots)
  const wrapper = mount(RobotView, mountOptions)
  await flushPromises()
  await wrapper.vm.$nextTick()
  return { wrapper, fleet: useFleetStore() }
}

/**
 * Open a row's overflow menu and return it.
 *
 * Mute, edit and remove live behind the "…" trigger, so a test that reaches for
 * them opens the menu the way an operator does.
 */
async function openRowMenu(wrapper: VueWrapper, index = 0): Promise<Element> {
  const triggers = wrapper.findAll('button[aria-label^="More actions"]')
  await triggers[index]!.trigger('click')
  await flushPromises()
  const menu = document.querySelector('[role="menu"]')
  if (!menu) throw new Error('row menu did not open')
  return menu
}

function menuItem(menu: Element, label: string): HTMLElement {
  const item = [...menu.querySelectorAll('[role="menuitem"]')].find(
    (element) => element.textContent?.trim() === label,
  )
  if (!item) throw new Error(`no menu item labelled "${label}"`)
  return item as HTMLElement
}

async function chooseRowAction(wrapper: VueWrapper, label: string, index = 0): Promise<void> {
  const menu = await openRowMenu(wrapper, index)
  menuItem(menu, label).click()
  await flushPromises()
}

// Dialogs render through a portal into document.body, which survives the
// component. Without this, one test reads the previous test's open dialog.
enableAutoUnmount(afterEach)

beforeEach(() => {
  setActivePinia(createPinia())
  localStorage.clear()
  document.body.innerHTML = ''
  apiMock.list.mockReset().mockResolvedValue([])
  apiMock.create.mockReset()
  apiMock.update.mockReset()
  apiMock.remove.mockReset().mockResolvedValue(undefined)
})

describe('RobotView — table', () => {
  it('renders one row per robot with its bridge URL', async () => {
    const { wrapper } = await mountView([
      robot({ id: 'a', name: 'AMR-01', bridgeUrl: 'ws://10.0.0.1:8765' }),
      robot({ id: 'b', name: 'AMR-02', bridgeUrl: 'ws://10.0.0.2:8765' }),
    ])

    const rows = wrapper.findAll('tbody tr')
    expect(rows).toHaveLength(2)
    expect(wrapper.text()).toContain('AMR-01')
    expect(wrapper.text()).toContain('ws://10.0.0.2:8765')
  })

  it('has a header cell for every column the rows render', async () => {
    const { wrapper } = await mountView([robot()])
    expect(wrapper.findAll('thead th')).toHaveLength(COLUMNS)
    expect(wrapper.findAll('tbody tr').at(0)?.findAll('td')).toHaveLength(COLUMNS)
  })

  it('renders an unset ROS domain as a dash, because 0 is a real domain', async () => {
    const { wrapper } = await mountView([robot({ rosDomainId: null })])
    const domainCell = wrapper.findAll('tbody td').at(2)
    expect(domainCell?.text()).toBe('—')
  })

  it('renders a zero ROS domain as 0, not as a dash', async () => {
    const { wrapper } = await mountView([robot({ rosDomainId: 0 })])
    expect(wrapper.findAll('tbody td').at(2)?.text()).toBe('0')
  })

  it('shows an empty state with its own add button when the registry is empty', async () => {
    const { wrapper } = await mountView([])
    expect(wrapper.text()).toContain('No robots registered')
    expect(wrapper.findAll('tbody tr')).toHaveLength(1)
  })
})

describe('RobotView — skeleton', () => {
  it('shows skeleton rows while loading and swaps them for data', async () => {
    // A request that never settles, so the loading state can be observed.
    apiMock.list.mockReturnValue(new Promise(() => {}))
    const wrapper = mount(RobotView, mountOptions)
    const fleet = useFleetStore()
    await wrapper.vm.$nextTick()

    const skeletonRows = wrapper.findAll('tbody tr')
    expect(skeletonRows.length).toBeGreaterThan(0)
    expect(wrapper.find('.animate-pulse').exists()).toBe(true)
    // Matching the real column count is what stops the layout jumping.
    expect(skeletonRows.at(0)?.findAll('td')).toHaveLength(COLUMNS)

    fleet.robots = [robot({ name: 'AMR-07' })]
    fleet.loading = false
    fleet.loaded = true
    await wrapper.vm.$nextTick()

    expect(wrapper.find('.animate-pulse').exists()).toBe(false)
    expect(wrapper.text()).toContain('AMR-07')
  })

  it('shows an error state instead of a stale table when the load fails', async () => {
    apiMock.list.mockRejectedValue(new ApiError('Backend unreachable', 0, '/robots'))
    const wrapper = mount(RobotView, mountOptions)
    await flushPromises()
    await wrapper.vm.$nextTick()

    expect(wrapper.text()).toContain('Could not load the registry')
    expect(wrapper.text()).toContain('Backend unreachable')
    expect(wrapper.find('table').exists()).toBe(false)
  })
})

describe('RobotView — pagination', () => {
  function manyRobots(count: number): RobotConfig[] {
    return Array.from({ length: count }, (_, i) =>
      robot({ id: `r${i}`, name: `AMR-${String(i + 1).padStart(2, '0')}`, bridgeUrl: `ws://10.0.0.${i}:8765` }),
    )
  }

  it('shows the range even when everything fits on one page', async () => {
    const { wrapper } = await mountView(manyRobots(3))
    expect(wrapper.text()).toContain('1\u20133 of 3')
    expect(wrapper.text()).toContain('Page 1 of 1')
  })

  it('caps the rows at the page size and pages through the rest', async () => {
    const { wrapper } = await mountView(manyRobots(23))
    expect(wrapper.findAll('tbody tr')).toHaveLength(10)
    expect(wrapper.text()).toContain('Page 1 of 3')

    await wrapper.get('[aria-label="Next page"]').trigger('click')
    expect(wrapper.text()).toContain('Page 2 of 3')
    expect(wrapper.text()).toContain('AMR-11')

    await wrapper.get('[aria-label="Next page"]').trigger('click')
    expect(wrapper.findAll('tbody tr')).toHaveLength(3)
    expect(wrapper.text()).toContain('21\u201323 of 23')
  })

  it('disables the controls at each end rather than hiding them', async () => {
    const { wrapper } = await mountView(manyRobots(23))
    expect(wrapper.get('[aria-label="Previous page"]').attributes('disabled')).toBeDefined()
    expect(wrapper.get('[aria-label="Next page"]').attributes('disabled')).toBeUndefined()
  })

  it('hides the page-size control when there is nothing to page through', async () => {
    const { wrapper } = await mountView(manyRobots(4))
    expect(wrapper.find('[aria-label="Rows per page"]').exists()).toBe(false)
  })

  it('keeps the first visible row visible when the page size changes', async () => {
    const { wrapper } = await mountView(manyRobots(60))
    await wrapper.get('[aria-label="Next page"]').trigger('click')
    await wrapper.get('[aria-label="Next page"]').trigger('click')
    expect(wrapper.text()).toContain('21\u201330 of 60')

    // Item 21 lives on page 1 of a 25-row layout.
    const sizeButtons = wrapper.get('[aria-label="Rows per page"]').findAll('button')
    await sizeButtons[1]?.trigger('click')
    expect(wrapper.text()).toContain('Page 1 of 3')
    expect(wrapper.text()).toContain('1\u201325 of 60')
  })

  it('falls back off a page that no longer exists after a removal', async () => {
    const { wrapper, fleet } = await mountView(manyRobots(11))
    await wrapper.get('[aria-label="Next page"]').trigger('click')
    expect(wrapper.text()).toContain('Page 2 of 2')

    // The only row on page 2 goes away.
    fleet.robots = manyRobots(10)
    await wrapper.vm.$nextTick()

    expect(wrapper.text()).toContain('Page 1 of 1')
    expect(wrapper.findAll('tbody tr')).toHaveLength(10)
  })
})

describe('RobotView — modals', () => {
  it('opens the add dialog empty', async () => {
    const { wrapper } = await mountView([robot()])
    const addButton = wrapper
      .findAll('button')
      .find((b) => b.text().includes('Add robot'))
    await addButton?.trigger('click')
    await flushPromises()

    const dialog = document.querySelector('[role="dialog"]')
    expect(dialog?.textContent).toContain('Add robot')
    const nameInput = dialog?.querySelector('input') as HTMLInputElement | null
    expect(nameInput?.value).toBe('')
  })

  it('opens the edit dialog pre-filled with that robot', async () => {
    const { wrapper } = await mountView([
      robot({ id: 'a', name: 'AMR-01', rosDomainId: 42 }),
      robot({ id: 'b', name: 'AMR-02' }),
    ])

    // The second row, so a menu that reported the wrong robot would be caught.
    await chooseRowAction(wrapper, 'Edit', 1)

    const dialog = document.querySelector('[role="dialog"]')
    expect(dialog?.textContent).toContain('Edit AMR-02')
    const inputs = dialog?.querySelectorAll('input')
    expect((inputs?.[0] as HTMLInputElement).value).toBe('AMR-02')
  })

  it('asks for confirmation before removing, naming the robot', async () => {
    const { wrapper, fleet } = await mountView([robot({ name: 'AMR-05' })])

    await chooseRowAction(wrapper, 'Remove')

    const dialog = document.querySelector('[role="alertdialog"]')
    expect(dialog?.textContent).toContain('Remove AMR-05?')
    // Nothing reaches the server until the dialog is answered.
    expect(apiMock.remove).not.toHaveBeenCalled()
    expect(fleet.count).toBe(1)
  })
})

describe('RobotView — table width', () => {
  it('truncates a long bridge URL instead of widening the table', async () => {
    const url = 'ws://amr-01.warehouse.internal.example.com:8765/rosbridge'
    const { wrapper } = await mountView([robot({ bridgeUrl: url })])

    const bridge = wrapper.findAll('tbody tr td')[1]!
    expect(bridge.classes()).toEqual(expect.arrayContaining(['w-full', 'max-w-0']))
    const text = bridge.find('span')
    expect(text.classes()).toContain('truncate')
    expect(text.attributes('title')).toBe(url)
  })
})

describe('RobotView — row actions menu', () => {
  it('opens technical detail outside the menu, reachable in one click', async () => {
    // The robot registry opens diagnostics; the dashboard owns the navigation shortcut.
    const { wrapper } = await mountView([robot({ id: 'r1' })])
    const link = wrapper
      .findAllComponents(RouterLinkStub)
      .find((component) => String(component.props('to')) === '/robot/r1/detail')
    expect(link).toBeTruthy()
  })

  it('labels every item in words rather than an icon alone', async () => {
    const { wrapper } = await mountView([robot()])
    const menu = await openRowMenu(wrapper)
    const labels = [...menu.querySelectorAll('[role="menuitem"]')].map((element) =>
      element.textContent?.trim(),
    )
    expect(labels).toEqual(['Stop monitoring', 'Edit', 'Remove'])
  })

  it('labels the mute item by what it will do, not by what is true now', async () => {
    // "Muted" as a label reads as a state and invites a click to confirm it. The
    // state itself is already on the row, in the Link column.
    const { wrapper } = await mountView([robot({ id: 'r1' })])
    const links = useLinkStore()
    links.setMuted('r1', true)
    await wrapper.vm.$nextTick()

    const menu = await openRowMenu(wrapper)
    expect(menuItem(menu, 'Resume monitoring')).toBeTruthy()
  })

  it('toggles monitoring from the menu', async () => {
    const { wrapper } = await mountView([robot({ id: 'r1' })])
    const links = useLinkStore()
    expect(links.isMuted('r1')).toBe(false)

    await chooseRowAction(wrapper, 'Stop monitoring')

    expect(links.isMuted('r1')).toBe(true)
  })

  it('gives each row its own trigger, named for that robot', async () => {
    const { wrapper } = await mountView([
      robot({ id: 'a', name: 'AMR-01' }),
      robot({ id: 'b', name: 'AMR-02' }),
    ])
    const labels = wrapper
      .findAll('button[aria-label^="More actions"]')
      .map((button) => button.attributes('aria-label'))
    expect(labels).toEqual(['More actions for AMR-01', 'More actions for AMR-02'])
  })
})

describe('RobotView — talking to the server', () => {
  it('loads the registry from the API on mount', async () => {
    await mountView([robot({ name: 'AMR-01' })])
    expect(apiMock.list).toHaveBeenCalledTimes(1)
  })

  it('sends a create and keeps the row the server returned', async () => {
    const { wrapper, fleet } = await mountView([])
    apiMock.create.mockResolvedValue(robot({ id: 'new', name: 'AMR-02' }))

    await fleet.add({ name: 'AMR-02', bridgeUrl: 'ws://10.0.0.2:8765', rosDomainId: null })
    await wrapper.vm.$nextTick()

    expect(apiMock.create).toHaveBeenCalledWith({
      name: 'AMR-02',
      bridgeUrl: 'ws://10.0.0.2:8765',
      rosDomainId: null,
    })
    expect(fleet.count).toBe(1)
    expect(wrapper.text()).toContain('AMR-02')
  })

  it('does not add the row when the server rejects the create', async () => {
    const { fleet } = await mountView([])
    apiMock.create.mockRejectedValue(new RobotConflictError('name', 'Another robot uses this name'))

    await expect(
      fleet.add({ name: 'AMR-01', bridgeUrl: 'ws://10.0.0.1:8765', rosDomainId: null }),
    ).rejects.toBeInstanceOf(RobotConflictError)

    // No optimistic insert: this registry decides which machine gets driven.
    expect(fleet.count).toBe(0)
  })

  it('does not drop the row when the server rejects the delete', async () => {
    const { fleet } = await mountView([robot({ id: 'a' })])
    apiMock.remove.mockRejectedValue(new ApiError('boom', 500, '/robots/a'))

    await expect(fleet.remove('a')).rejects.toBeInstanceOf(ApiError)
    expect(fleet.count).toBe(1)
  })
})
