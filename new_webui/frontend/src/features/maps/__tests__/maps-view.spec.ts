/**
 * Map registry page.
 *
 * The rules under test are the ones the old design broke: versions are never
 * silently replaced, a map in use cannot be deleted, and an assignment is per
 * robot rather than global.
 */
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { enableAutoUnmount, flushPromises, mount, RouterLinkStub } from '@vue/test-utils'
import type { VueWrapper } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import MapsView from '../views/MapsView.vue'
import { MapNameTakenError } from '@/shared/api/maps'
import { useMapStore } from '@/stores/maps'
import { useFleetStore } from '@/stores/fleet'
import type { MapRecord, RobotConfig } from '@/domain/types'

vi.mock('vue-sonner', () => ({
  toast: { success: vi.fn(), error: vi.fn(), info: vi.fn(), warning: vi.fn() },
}))

const mapsMock = vi.hoisted(() => ({
  list: vi.fn(),
  upload: vi.fn(),
  rename: vi.fn(),
  remove: vi.fn(),
  fileUrl: vi.fn((id: string, which: string) => `/api/maps/${id}/files/${which}`),
  archiveUrl: vi.fn((id: string) => `/api/maps/${id}/archive`),
}))

vi.mock('@/shared/api/maps', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@/shared/api/maps')>()
  return { ...actual, mapsApi: mapsMock }
})

const robotsMock = vi.hoisted(() => ({
  list: vi.fn(),
  create: vi.fn(),
  update: vi.fn(),
  remove: vi.fn(),
  assignMap: vi.fn(),
}))

vi.mock('@/shared/api/robots', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@/shared/api/robots')>()
  return { ...actual, robotsApi: robotsMock }
})

function mapRecord(overrides: Partial<MapRecord> = {}): MapRecord {
  return {
    id: 'm1',
    name: 'Warehouse A',
    version: 1,
    contentHash: 'abc123',
    yamlFile: 'map.yaml',
    imageFile: 'map.pgm',
    imageBytes: 38233,
    resolution: 0.05,
    width: 200,
    height: 100,
    originX: -5,
    originY: -5,
    originYaw: 0,
    negate: 0,
    occupiedThresh: 0.65,
    freeThresh: 0.196,
    createdByRobotId: null,
    note: null,
    createdAt: '2026-09-28 08:00:00',
    ...overrides,
  }
}

function robot(overrides: Partial<RobotConfig> = {}): RobotConfig {
  return {
    id: 'r1',
    name: 'AMR-01',
    bridgeUrl: 'ws://10.0.0.1:8765',
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

const mountOptions = {
  attachTo: document.body,
  global: { stubs: { RouterLink: RouterLinkStub } },
}

async function mountView(maps: MapRecord[], robots: RobotConfig[] = []) {
  mapsMock.list.mockResolvedValue(maps)
  robotsMock.list.mockResolvedValue(robots)
  const wrapper = mount(MapsView, mountOptions)
  await flushPromises()
  await wrapper.vm.$nextTick()
  return { wrapper, maps: useMapStore(), fleet: useFleetStore() }
}

/**
 * Open a row's overflow menu and return it.
 *
 * Rename, edit, download and remove live behind the "…" trigger now, so a test
 * that reaches for them has to open the menu the way an operator does.
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

/** Open the menu and activate one item, which is what a click on a row action is. */
/** Reveal a map's older versions, which are collapsed by default. */
async function expandGroup(wrapper: VueWrapper, index = 0): Promise<void> {
  // Not [aria-expanded]: reka-ui puts that on the row's "…" trigger too.
  const expanders = wrapper.findAll('button[aria-label^="Show older versions"]')
  await expanders[index]!.trigger('click')
  await flushPromises()
}

async function chooseRowAction(wrapper: VueWrapper, label: string, index = 0): Promise<void> {
  const menu = await openRowMenu(wrapper, index)
  menuItem(menu, label).click()
  await flushPromises()
}

enableAutoUnmount(afterEach)

beforeEach(() => {
  setActivePinia(createPinia())
  document.body.innerHTML = ''
  mapsMock.list.mockReset().mockResolvedValue([])
  mapsMock.upload.mockReset()
  mapsMock.remove.mockReset().mockResolvedValue(undefined)
  mapsMock.rename.mockReset().mockResolvedValue(mapRecord({ name: 'Warehouse B' }))
  robotsMock.list.mockReset().mockResolvedValue([])
  robotsMock.assignMap.mockReset().mockResolvedValue(robot())
})

describe('MapsView — table', () => {
  it('shows one row per map, not one per version', async () => {
    // Three edits used to produce three peer rows, which reads as three maps.
    const { wrapper } = await mountView([
      mapRecord({ id: 'a', name: 'Warehouse A', version: 2 }),
      mapRecord({ id: 'b', name: 'Warehouse A', version: 1 }),
    ])
    expect(wrapper.findAll('tbody tr')).toHaveLength(1)
    // The newest is the one shown, and the history is advertised rather than hidden.
    expect(wrapper.text()).toContain('v2')
    expect(wrapper.text()).toContain('+1 older')
  })

  it('reveals the older versions on request', async () => {
    // They are still assignable: they are what robots running them are running.
    const { wrapper } = await mountView([
      mapRecord({ id: 'a', name: 'Warehouse A', version: 2 }),
      mapRecord({ id: 'b', name: 'Warehouse A', version: 1 }),
    ])

    await expandGroup(wrapper)

    expect(wrapper.findAll('tbody tr')).toHaveLength(2)
    expect(wrapper.text()).toContain('v1')
  })

  it('keeps maps with different names as separate rows', async () => {
    const { wrapper } = await mountView([
      mapRecord({ id: 'a', name: 'Warehouse A' }),
      mapRecord({ id: 'b', name: 'Loading Bay' }),
    ])
    expect(wrapper.findAll('tbody tr')).toHaveLength(2)
    // A single-version map has no history to offer, so no expander.
    expect(wrapper.findAll('button[aria-label^="Show older versions"]')).toHaveLength(0)
  })

  it('pages over maps rather than versions', async () => {
    // Otherwise an expanded group could straddle a page boundary.
    const { wrapper } = await mountView([
      mapRecord({ id: 'a', name: 'Warehouse A', version: 3 }),
      mapRecord({ id: 'b', name: 'Warehouse A', version: 2 }),
      mapRecord({ id: 'c', name: 'Warehouse A', version: 1 }),
    ])
    expect(wrapper.text()).toContain('3 versions across 1 map')
    expect(wrapper.findAll('tbody tr')).toHaveLength(1)
  })

  it('shows physical extent in metres, not just pixels', async () => {
    const { wrapper } = await mountView([mapRecord({ width: 200, height: 100, resolution: 0.05 })])
    // 200 px * 0.05 m = 10 m across.
    expect(wrapper.text()).toContain('10.0 × 5.0 m')
    expect(wrapper.text()).toContain('200×100 px')
  })

  it('has a header cell for every column the rows render', async () => {
    const { wrapper } = await mountView([mapRecord()])
    const columns = wrapper.findAll('thead th').length
    expect(wrapper.findAll('tbody tr').at(0)?.findAll('td')).toHaveLength(columns)
  })

  it('shows an empty state when the registry has nothing', async () => {
    const { wrapper } = await mountView([])
    expect(wrapper.text()).toContain('No maps yet')
  })

  it('shows an error state instead of a stale table when the load fails', async () => {
    mapsMock.list.mockRejectedValue(new Error('Backend unreachable'))
    const wrapper = mount(MapsView, mountOptions)
    await flushPromises()
    expect(wrapper.text()).toContain('Could not load the registry')
    expect(wrapper.find('table').exists()).toBe(false)
  })

  it('names the robots currently running each map', async () => {
    const { wrapper } = await mountView(
      [mapRecord({ id: 'm1' })],
      [robot({ id: 'r1', name: 'AMR-01', activeMapId: 'm1' }), robot({ id: 'r2', name: 'AMR-02' })],
    )
    // Written out, not only in a tooltip: hover does not exist on a touch screen.
    const row = wrapper.findAll('tbody tr').at(0)!
    expect(row.text()).toContain('AMR-01')
    expect(row.text()).not.toContain('AMR-02')
  })

  it('lists two robots by name and counts the rest', async () => {
    const { wrapper } = await mountView(
      [mapRecord({ id: 'm1' })],
      ['AMR-01', 'AMR-02', 'AMR-03', 'AMR-04'].map((name, i) =>
        robot({ id: `r${i}`, name, activeMapId: 'm1' }),
      ),
    )
    const row = wrapper.findAll('tbody tr').at(0)!
    expect(row.text()).toContain('AMR-02')
    expect(row.text()).not.toContain('AMR-03')
    expect(row.text()).toContain('+2')
  })

  it('hides the pager while everything fits on one page', async () => {
    const one = await mountView([mapRecord({ id: 'm1' })])
    expect(one.wrapper.text()).not.toContain('Page 1 of 1')

    const many = await mountView(
      Array.from({ length: 11 }, (_, i) => mapRecord({ id: `m${i}`, name: `Map ${i}` })),
    )
    expect(many.wrapper.text()).toContain('Page 1 of 2')
  })

  it('reports a retired surveying robot rather than a dangling id', async () => {
    // The backend nulls created_by_robot_id when a robot is deleted, so the map
    // outlives its surveyor and the column has to say something truthful.
    const { wrapper } = await mountView([mapRecord({ createdByRobotId: 'gone' })])
    expect(wrapper.text()).toContain('retired robot')
  })
})

describe('MapsView — deleting', () => {
  it('warns which robots hold a map before deleting it', async () => {
    const { wrapper } = await mountView(
      [mapRecord({ id: 'm1', name: 'Warehouse A' })],
      [robot({ id: 'r1', name: 'AMR-01', activeMapId: 'm1' })],
    )
    await chooseRowAction(wrapper, 'Remove')

    const dialog = document.querySelector('[role="alertdialog"]')
    expect(dialog?.textContent).toContain('Remove Warehouse A v1?')
    expect(dialog?.textContent).toContain('AMR-01')
    // Nothing reaches the server until the dialog is answered.
    expect(mapsMock.remove).not.toHaveBeenCalled()
  })

  function confirmButton() {
    const dialog = document.querySelector('[role="alertdialog"]')!
    return [...dialog.querySelectorAll('button')].find(
      (b) => b.textContent?.trim() === 'Remove',
    ) as HTMLButtonElement
  }

  it('does not offer a delete the server is certain to refuse', async () => {
    // The precondition is already known here. Letting the click through turns it
    // into a failed request and a toast, with the dialog left as it was.
    const { wrapper } = await mountView(
      [mapRecord({ id: 'm1' })],
      [robot({ id: 'r1', name: 'AMR-01', activeMapId: 'm1' })],
    )
    await chooseRowAction(wrapper, 'Remove')

    expect(confirmButton().disabled).toBe(true)
  })

  it('still allows a delete when no robot holds the map', async () => {
    const { wrapper } = await mountView([mapRecord({ id: 'm1' })], [robot({ activeMapId: null })])
    await chooseRowAction(wrapper, 'Remove')

    expect(confirmButton().disabled).toBe(false)
  })

  it('hands the operator the assignment dialog as the way out', async () => {
    const { wrapper } = await mountView(
      [mapRecord({ id: 'm1', name: 'Warehouse A' })],
      [robot({ id: 'r1', name: 'AMR-01', activeMapId: 'm1' })],
    )
    await chooseRowAction(wrapper, 'Remove')

    const reassign = [...document.querySelectorAll('[role="alertdialog"] button')].find((b) =>
      b.textContent?.includes('Reassign'),
    ) as HTMLElement
    reassign.click()
    await flushPromises()

    // The delete is abandoned and the assignment dialog is open on the same map.
    expect(document.querySelector('[role="alertdialog"]')).toBeNull()
    expect(document.querySelector('[role="dialog"]')?.textContent).toContain('Warehouse A')
    expect(mapsMock.remove).not.toHaveBeenCalled()
  })

  it('drops a row the server says is already gone', async () => {
    // Otherwise the row is unremovable: every retry 404s against the same
    // missing map, and the operator is stuck with a map that does not exist.
    const { ApiError } = await import('@/shared/api/client')
    mapsMock.remove.mockRejectedValue(new ApiError('Map not found', 404, '/maps/m1'))

    const { wrapper, maps } = await mountView([mapRecord({ id: 'm1' })])
    await chooseRowAction(wrapper, 'Remove')

    await maps.remove('m1')
    expect(maps.count).toBe(0)
  })

  it('keeps the row when the server refuses the delete', async () => {
    const { MapInUseError } = await import('@/shared/api/maps')
    mapsMock.remove.mockRejectedValue(new MapInUseError(['AMR-01'], 'Still assigned to: AMR-01'))

    const { wrapper, maps } = await mountView([mapRecord({ id: 'm1' })])
    await chooseRowAction(wrapper, 'Remove')

    await maps.remove('m1').catch(() => {})
    expect(maps.count).toBe(1)
  })
})

describe('MapsView — assigning', () => {
  it('opens with the robots already on the map pre-selected', async () => {
    const { wrapper } = await mountView(
      [mapRecord({ id: 'm1' })],
      [robot({ id: 'r1', name: 'AMR-01', activeMapId: 'm1' }), robot({ id: 'r2', name: 'AMR-02' })],
    )
    await wrapper.find('button[title^="Assign"]').trigger('click')
    await flushPromises()

    const dialog = document.querySelector('[role="dialog"]')
    expect(dialog?.textContent).toContain('Already on this map')
    expect(dialog?.textContent).toContain('No map assigned')

    const pressed = dialog?.querySelectorAll('[aria-pressed="true"]')
    expect(pressed).toHaveLength(1)
  })

  it('only writes the robots whose assignment actually changes', async () => {
    const { wrapper } = await mountView(
      [mapRecord({ id: 'm1' })],
      [robot({ id: 'r1', name: 'AMR-01', activeMapId: 'm1' }), robot({ id: 'r2', name: 'AMR-02' })],
    )
    await wrapper.find('button[title^="Assign"]').trigger('click')
    await flushPromises()

    const dialog = document.querySelector('[role="dialog"]')!
    const rows = dialog.querySelectorAll('[aria-pressed]')
    // Tick AMR-02; AMR-01 was already on this map and must not be rewritten.
    ;(rows[1] as HTMLElement).click()
    await flushPromises()

    const apply = [...dialog.querySelectorAll('button')].find((b) =>
      b.textContent?.includes('Apply to'),
    )
    expect(apply?.textContent).toContain('1 robot')
    ;(apply as HTMLElement).click()
    await flushPromises()

    expect(robotsMock.assignMap).toHaveBeenCalledTimes(1)
    expect(robotsMock.assignMap).toHaveBeenCalledWith('r2', 'm1')
  })

  it('clears the assignment by sending null, not by omitting the robot', async () => {
    const { wrapper } = await mountView(
      [mapRecord({ id: 'm1' })],
      [robot({ id: 'r1', name: 'AMR-01', activeMapId: 'm1' })],
    )
    await wrapper.find('button[title^="Assign"]').trigger('click')
    await flushPromises()

    const dialog = document.querySelector('[role="dialog"]')!
    ;(dialog.querySelector('[aria-pressed="true"]') as HTMLElement).click()
    await flushPromises()

    const apply = [...dialog.querySelectorAll('button')].find((b) =>
      b.textContent?.includes('Apply to'),
    )
    ;(apply as HTMLElement).click()
    await flushPromises()

    expect(robotsMock.assignMap).toHaveBeenCalledWith('r1', null)
  })

  it('disables apply when nothing would change', async () => {
    const { wrapper } = await mountView(
      [mapRecord({ id: 'm1' })],
      [robot({ id: 'r1', activeMapId: 'm1' })],
    )
    await wrapper.find('button[title^="Assign"]').trigger('click')
    await flushPromises()

    const dialog = document.querySelector('[role="dialog"]')!
    const apply = [...dialog.querySelectorAll('button')].find((b) =>
      b.textContent?.includes('No changes'),
    )
    expect(apply).toBeTruthy()
    expect((apply as HTMLButtonElement).disabled).toBe(true)
  })
})

describe('MapsView — uploading', () => {
  it('requires both halves of the pair', async () => {
    const { wrapper } = await mountView([])
    const openers = wrapper.findAll('button').filter((b) => b.text().includes('Upload map'))
    await openers[0]?.trigger('click')
    await flushPromises()

    const dialog = document.querySelector('[role="dialog"]')!
    const submit = [...dialog.querySelectorAll('button')].find((b) => b.textContent === 'Upload')
    ;(submit as HTMLElement).click()
    await flushPromises()

    // A yaml without its image produces a registry entry no robot can load.
    expect(dialog.textContent).toContain('Both the .yaml and the image are required.')
    expect(mapsMock.upload).not.toHaveBeenCalled()
  })

  it('warns that an existing name creates a version rather than replacing', async () => {
    const { wrapper } = await mountView([mapRecord({ name: 'Warehouse A' })])
    await wrapper.find('button[title="Upload map"], button').trigger('click')
    const openers = wrapper.findAll('button').filter((b) => b.text().includes('Upload map'))
    await openers[0]?.trigger('click')
    await flushPromises()

    const dialog = document.querySelector('[role="dialog"]')!
    const input = dialog.querySelector('input[type="text"], input:not([type])') as HTMLInputElement
    input.value = 'Warehouse A'
    input.dispatchEvent(new Event('input'))
    await flushPromises()

    expect(dialog.textContent).toContain('creates the next version')
  })
})

describe('MapsView — renaming', () => {
  /** Open the rename dialog on the first row and return its DOM node. */
  async function openRename(wrapper: VueWrapper) {
    await chooseRowAction(wrapper, 'Rename')
    return document.querySelector('[role="dialog"]')!
  }

  function field(dialog: Element) {
    return dialog.querySelector('input') as HTMLInputElement
  }

  function renameButton(dialog: Element) {
    return [...dialog.querySelectorAll('button')].find(
      (b) => b.textContent?.trim() === 'Rename',
    ) as HTMLButtonElement
  }

  async function type(dialog: Element, value: string) {
    const input = field(dialog)
    input.value = value
    input.dispatchEvent(new Event('input'))
    await flushPromises()
  }

  it('offers a rename action on every row', async () => {
    const { wrapper } = await mountView([mapRecord()])
    const menu = await openRowMenu(wrapper)
    expect(menuItem(menu, 'Rename')).toBeTruthy()
  })

  it('opens with the current name already in the field', async () => {
    const { wrapper } = await mountView([mapRecord({ name: 'Warehouse A' })])
    const dialog = await openRename(wrapper)
    expect(field(dialog).value).toBe('Warehouse A')
  })

  it('sends the trimmed new name', async () => {
    const { wrapper } = await mountView([mapRecord({ id: 'm1' })])
    const dialog = await openRename(wrapper)

    await type(dialog, '  Warehouse B  ')
    renameButton(dialog).click()
    await flushPromises()

    expect(mapsMock.rename).toHaveBeenCalledWith('m1', 'Warehouse B')
  })

  it('reloads the list, because a rename moves every version', async () => {
    const { wrapper } = await mountView([mapRecord({ id: 'm1' })])
    mapsMock.list.mockClear()
    const dialog = await openRename(wrapper)

    await type(dialog, 'Warehouse B')
    renameButton(dialog).click()
    await flushPromises()

    expect(mapsMock.list).toHaveBeenCalled()
  })

  it('says how many versions a rename will move', async () => {
    const { wrapper } = await mountView([
      mapRecord({ id: 'a', name: 'Warehouse A', version: 2 }),
      mapRecord({ id: 'b', name: 'Warehouse A', version: 1 }),
    ])
    const dialog = await openRename(wrapper)
    expect(dialog.textContent).toContain('2 versions')
  })

  it('refuses a name another map already holds, without asking the server', async () => {
    const { wrapper } = await mountView([
      mapRecord({ id: 'a', name: 'Warehouse A' }),
      mapRecord({ id: 'b', name: 'Loading Bay' }),
    ])
    const dialog = await openRename(wrapper)

    await type(dialog, 'Loading Bay')

    expect(renameButton(dialog).disabled).toBe(true)
    expect(dialog.textContent).toContain('already uses this name')
    expect(mapsMock.rename).not.toHaveBeenCalled()
  })

  it('allows a case-only correction, which is not a collision', async () => {
    const { wrapper } = await mountView([mapRecord({ id: 'm1', name: 'warehouse a' })])
    const dialog = await openRename(wrapper)

    await type(dialog, 'Warehouse A')

    expect(renameButton(dialog).disabled).toBe(false)
  })

  it('does not submit an unchanged name', async () => {
    const { wrapper } = await mountView([mapRecord({ name: 'Warehouse A' })])
    const dialog = await openRename(wrapper)
    expect(renameButton(dialog).disabled).toBe(true)
  })

  it('does not submit a blank name', async () => {
    const { wrapper } = await mountView([mapRecord()])
    const dialog = await openRename(wrapper)

    await type(dialog, '   ')

    expect(renameButton(dialog).disabled).toBe(true)
  })

  it('keeps the dialog open and shows why when the server refuses', async () => {
    mapsMock.rename.mockRejectedValue(new MapNameTakenError('Warehouse B'))
    const { wrapper } = await mountView([mapRecord({ id: 'm1' })])
    const dialog = await openRename(wrapper)

    await type(dialog, 'Warehouse B')
    renameButton(dialog).click()
    await flushPromises()

    expect(document.querySelector('[role="dialog"]')).not.toBeNull()
    expect(document.querySelector('[role="dialog"]')!.textContent).toContain('already exists')
  })
})

describe('MapsView — table width', () => {
  const LONG_NOTE =
    'recovered from robot staging after the agent was started without AMR_BACKEND_URL'

  it('truncates a long note instead of widening the table', async () => {
    // A note is a sentence. Left unconstrained it sized the column, and the
    // whole table went behind a horizontal scrollbar the moment a group opened.
    const { wrapper } = await mountView([
      mapRecord({ id: 'a', name: 'Warehouse A', version: 2 }),
      mapRecord({ id: 'b', name: 'Warehouse A', version: 1, note: LONG_NOTE }),
    ])
    await expandGroup(wrapper)

    const note = wrapper.findAll('tbody tr')[1]!.find('p')
    expect(note.classes()).toContain('truncate')
    // Truncated text still has to be readable somehow.
    expect(note.attributes('title')).toBe(LONG_NOTE)
  })

  it('lets the name column absorb the slack rather than the note', async () => {
    const { wrapper } = await mountView([mapRecord()])
    const first = wrapper.find('tbody tr td')
    expect(first.classes()).toEqual(expect.arrayContaining(['w-full', 'max-w-0']))
  })

  it('keeps measurements on one line when the row is squeezed', async () => {
    const { wrapper } = await mountView([mapRecord()])
    const cells = wrapper.findAll('tbody tr td')
    // Extent and size are one value each, not two lines of one.
    expect(cells[1]!.find('span').classes()).toContain('whitespace-nowrap')
    expect(cells[2]!.find('span').classes()).toContain('whitespace-nowrap')
  })
})

describe('MapsView — editing cells', () => {
  it('links each row to its own editor', async () => {
    const { wrapper } = await mountView([mapRecord({ id: 'm1' })])
    const menu = await openRowMenu(wrapper)
    // A real link, not a button that pushes: the operator has to be able to open
    // an editor in a second tab while keeping the list in the first.
    expect(menuItem(menu, 'Edit cells').querySelector('a')).toBeTruthy()
  })

  it('lets an older version be edited too', async () => {
    // Editing v1 is legitimate — it saves as the next version and leaves v1 be.
    const { wrapper } = await mountView([
      mapRecord({ id: 'new', version: 2 }),
      mapRecord({ id: 'old', version: 1 }),
    ])
    await expandGroup(wrapper)
    await openRowMenu(wrapper, 1)
    const targets = wrapper
      .findAllComponents(RouterLinkStub)
      .map((component) => String(component.props('to')))
      .filter((to) => to.includes('/maps/edit/'))
    expect(targets).toEqual(['/maps/edit/old'])
  })
})

describe('MapsView — downloading', () => {
  it('downloads both halves as an archive, not a lone yaml', async () => {
    // A yaml names its image, so a yaml-only download will not load.
    const { wrapper } = await mountView([mapRecord({ id: 'm1' })])
    const menu = await openRowMenu(wrapper)
    const anchor = menuItem(menu, 'Download').querySelector('a')
    expect(anchor?.getAttribute('href')).toBe('/api/maps/m1/archive')
    // Without the attribute the browser navigates to the zip instead of saving it.
    expect(anchor?.hasAttribute('download')).toBe(true)
  })
})

describe('MapsView — row actions menu', () => {
  it('keeps Assign outside the menu, reachable in one click', async () => {
    // It is the only action that changes what a robot does.
    const { wrapper } = await mountView([mapRecord()])
    expect(wrapper.find('button[title^="Assign"]').exists()).toBe(true)
  })

  it('labels every item in words rather than an icon alone', async () => {
    const { wrapper } = await mountView([mapRecord()])
    const menu = await openRowMenu(wrapper)
    const labels = [...menu.querySelectorAll('[role="menuitem"]')].map((element) =>
      element.textContent?.trim(),
    )
    expect(labels).toEqual(['Rename', 'Edit cells', 'Download', 'Remove'])
  })

  it('gives each row its own trigger, named for that map and version', async () => {
    const { wrapper } = await mountView([
      mapRecord({ id: 'a', name: 'Warehouse A', version: 2 }),
      mapRecord({ id: 'b', name: 'Warehouse A', version: 1 }),
    ])
    await expandGroup(wrapper)

    const labels = wrapper
      .findAll('button[aria-label^="More actions"]')
      .map((button) => button.attributes('aria-label'))
    expect(labels).toEqual([
      'More actions for Warehouse A v2',
      'More actions for Warehouse A v1',
    ])
  })
})
