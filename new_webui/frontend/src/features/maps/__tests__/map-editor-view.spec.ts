/**
 * Map editor page on a phone.
 *
 * Painting cells wants a precise pointer, so a phone is advised to use a
 * larger screen first — but only advised: "Open anyway" has to get through.
 */
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { enableAutoUnmount, flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { createMemoryHistory, createRouter } from 'vue-router'
import MapEditorView from '../views/MapEditorView.vue'
import { useAuthStore } from '@/stores/auth'
import { CELL, encodePgm } from '@/domain/map/pgm'
import type { Role } from '@/domain/auth'
import type { MapRecord } from '@/domain/types'

vi.mock('vue-sonner', () => ({
  toast: { success: vi.fn(), error: vi.fn(), info: vi.fn(), warning: vi.fn() },
}))

const mapsMock = vi.hoisted(() => ({
  list: vi.fn(),
  fetchFile: vi.fn(),
  upload: vi.fn(),
  replaceImage: vi.fn(),
}))

vi.mock('@/shared/api/maps', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@/shared/api/maps')>()
  return { ...actual, mapsApi: mapsMock }
})

const robotsMock = vi.hoisted(() => ({ list: vi.fn() }))

vi.mock('@/shared/api/robots', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@/shared/api/robots')>()
  return { ...actual, robotsApi: robotsMock }
})

const record: MapRecord = {
  id: 'm1',
  name: 'Warehouse A',
  version: 1,
  contentHash: 'abc123',
  yamlFile: 'map.yaml',
  imageFile: 'map.pgm',
  imageBytes: 100,
  resolution: 0.05,
  width: 10,
  height: 10,
  originX: 0,
  originY: 0,
  originYaw: 0,
  negate: 0,
  occupiedThresh: 0.65,
  freeThresh: 0.196,
  createdByRobotId: null,
  note: null,
  createdAt: '2026-09-28 08:00:00',
}

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

async function mountEditor() {
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/maps', component: { template: '<div />' } },
      { path: '/maps/edit/:mapId', component: MapEditorView },
    ],
  })
  await router.push('/maps/edit/m1')
  await router.isReady()
  const wrapper = mount(MapEditorView, {
    attachTo: document.body,
    global: { plugins: [router], stubs: { MapEditCanvas: true } },
  })
  await flushPromises()
  return wrapper
}

function button(wrapper: Awaited<ReturnType<typeof mountEditor>>, label: string) {
  return wrapper.findAll('button').find((b) => b.text().trim() === label)
}

enableAutoUnmount(afterEach)

beforeEach(() => {
  setActivePinia(createPinia())
  signInAs('admin')
  document.body.innerHTML = ''
  mapsMock.list.mockReset().mockResolvedValue([record])
  mapsMock.fetchFile.mockReset().mockImplementation(async (_id: string, which: string) =>
    which === 'image'
      ? encodePgm({ width: 10, height: 10, cells: new Uint8Array(100).fill(CELL.free) })
      : new TextEncoder().encode('image: map.pgm\n'),
  )
  robotsMock.list.mockReset().mockResolvedValue([])
})

afterEach(() => delete (window as { matchMedia?: unknown }).matchMedia)

describe('MapEditorView — screen size', () => {
  it('advises a larger screen on a phone instead of opening the editor', async () => {
    screenWidth(390)
    const wrapper = await mountEditor()
    expect(wrapper.text()).toContain('Best on a tablet or laptop')
    expect(wrapper.findComponent({ name: 'MapEditCanvas' }).exists()).toBe(false)
    // The page still says which map this is.
    expect(wrapper.text()).toContain('Warehouse A v1')
  })

  it('points the way back at the map list', async () => {
    screenWidth(390)
    const wrapper = await mountEditor()
    const back = wrapper.findAll('a').find((a) => a.text().includes('Back to maps'))
    expect(back?.attributes('href')).toBe('/maps')
  })

  it('opens the editor anyway when asked', async () => {
    screenWidth(390)
    const wrapper = await mountEditor()
    await button(wrapper, 'Open anyway')!.trigger('click')
    expect(wrapper.text()).not.toContain('Best on a tablet or laptop')
    expect(wrapper.findComponent({ name: 'MapEditCanvas' }).exists()).toBe(true)
    expect(button(wrapper, 'Save')).toBeTruthy()
  })

  it('opens the editor directly on a laptop', async () => {
    screenWidth(1366)
    const wrapper = await mountEditor()
    expect(wrapper.text()).not.toContain('Best on a tablet or laptop')
    expect(wrapper.findComponent({ name: 'MapEditCanvas' }).exists()).toBe(true)
  })

  it('keeps a viewer from painting after opening anyway', async () => {
    signInAs('operator')
    screenWidth(390)
    const wrapper = await mountEditor()
    expect(wrapper.text()).toContain('Best on a tablet or laptop')

    await button(wrapper, 'Open anyway')!.trigger('click')
    const tool = (label: string) => wrapper.get(`button[aria-label="${label}"]`)
    expect(tool('Brush').attributes('disabled')).toBeDefined()
    expect(tool('Fill').attributes('disabled')).toBeDefined()
    expect(tool('Pan').attributes('disabled')).toBeUndefined()
  })
})
