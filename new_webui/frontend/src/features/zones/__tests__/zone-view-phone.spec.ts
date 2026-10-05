/**
 * Zone page on a phone, and drawing on a bigger screen.
 *
 * On a phone the map keeps the full width and the list is the other half of a
 * Map/List switch. Drawing and reshaping are left to bigger screens, and the
 * page says so in words; switching a zone on or off still works, because that
 * needs no precision.
 */
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { enableAutoUnmount, flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import ZoneView from '../views/ZoneView.vue'
import ZoneMapCanvas from '../components/ZoneMapCanvas.vue'
import { useAuthStore } from '@/stores/auth'
import { zonesApi } from '@/shared/api/zones'
import type { Role } from '@/domain/auth'
import type { MapRecord, Zone } from '@/domain/types'

vi.mock('vue-sonner', () => ({
  toast: { success: vi.fn(), error: vi.fn(), info: vi.fn(), warning: vi.fn() },
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

function zone(id: string, name: string, enabled: boolean): Zone {
  return {
    id,
    mapId: 'm1',
    name,
    kind: 'keepout',
    polygon: [
      [0, 0],
      [1, 0],
      [1, 1],
    ],
    speedLimit: null,
    avoidCost: null,
    enabled,
    note: enabled ? 'Electrical panel' : null,
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

vi.mock('@/shared/api/zones', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@/shared/api/zones')>()
  return {
    ...actual,
    zonesApi: {
      list: vi.fn(async () => [zone('z1', 'Panel', true), zone('z2', 'Loading bay', false)]),
      update: vi.fn(async (id: string, patch: Partial<Zone>) => ({
        ...zone(id, id === 'z1' ? 'Panel' : 'Loading bay', true),
        ...patch,
      })),
    },
  }
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
  const wrapper = mount(ZoneView, {
    attachTo: document.body,
    global: { stubs: { ZoneMapCanvas: true } },
  })
  await flushPromises()
  return wrapper
}

type Wrapper = Awaited<ReturnType<typeof mountAs>>

const canvas = (wrapper: Wrapper) => wrapper.findComponent(ZoneMapCanvas)
const radio = (wrapper: Wrapper, label: string) =>
  wrapper.findAll('[role="radio"]').find((b) => b.text().startsWith(label))!
const buttonByText = (wrapper: Wrapper, text: string) =>
  wrapper.findAll('button').find((b) => b.text().trim() === text)

enableAutoUnmount(afterEach)

beforeEach(() => {
  document.body.innerHTML = ''
  vi.mocked(zonesApi.update).mockClear()
})

afterEach(() => delete (window as { matchMedia?: unknown }).matchMedia)

describe('ZoneView — phone', () => {
  it('gives the map the width and leaves drawing out', async () => {
    const wrapper = await mountAs('admin', 390)
    expect(radio(wrapper, 'List').text()).toBe('List (2)')
    expect(wrapper.find('aside').exists()).toBe(false)
    expect(canvas(wrapper).props('editable')).toBe(false)
    expect(buttonByText(wrapper, 'Keep out')).toBeUndefined()
  })

  it('says why drawing is off, and keeps the switch working', async () => {
    const wrapper = await mountAs('admin', 390)
    await radio(wrapper, 'List').trigger('click')
    expect(buttonByText(wrapper, 'Draw a zone')!.attributes('disabled')).toBeDefined()
    expect(wrapper.text()).toContain('Drawing zones needs a tablet or laptop.')

    const toggle = wrapper.get('button[aria-label="Panel active"]')
    expect(toggle.attributes('disabled')).toBeUndefined()
    await toggle.trigger('click')
    await flushPromises()
    expect(zonesApi.update).toHaveBeenCalledWith('z1', { enabled: false })
  })

  it('shows a tapped row on the map with its card, and Close clears it', async () => {
    const wrapper = await mountAs('admin', 390)
    await radio(wrapper, 'List').trigger('click')
    await wrapper.get('li button').trigger('click')

    expect(radio(wrapper, 'Map').attributes('aria-checked')).toBe('true')
    expect(canvas(wrapper).props('selectedId')).toBe('z1')
    expect(canvas(wrapper).props('hideLegend')).toBe(true)
    expect(wrapper.text()).toContain('Panel')
    expect(wrapper.text()).toContain('Electrical panel')
    expect(wrapper.find('button[aria-label="Panel active"]').exists()).toBe(true)

    await wrapper.get('button[aria-label="Close"]').trigger('click')
    expect(canvas(wrapper).props('selectedId')).toBe(null)
    expect(wrapper.find('button[aria-label="Panel active"]').exists()).toBe(false)
  })

  it('shows a viewer the role as the reason, with the switch off limits', async () => {
    const wrapper = await mountAs('viewer', 390)
    await radio(wrapper, 'List').trigger('click')
    expect(wrapper.text()).toContain('Needs the admin role')
    expect(wrapper.text()).not.toContain('needs a tablet or laptop')
    expect(wrapper.get('button[aria-label="Panel active"]').attributes('disabled')).toBeDefined()
  })
})

describe('ZoneView — bigger screens', () => {
  it('never lets a viewer reshape, at any width', async () => {
    const wrapper = await mountAs('viewer', 1366)
    expect(canvas(wrapper).props('editable')).toBe(false)
    expect(wrapper.get('button[aria-label="Panel active"]').attributes('disabled')).toBeDefined()
  })

  it('keeps the docked list and editable zones for an admin', async () => {
    const wrapper = await mountAs('admin', 1366)
    expect(wrapper.find('[role="radiogroup"]').exists()).toBe(false)
    expect(wrapper.find('aside').exists()).toBe(true)
    expect(canvas(wrapper).props('editable')).toBe(true)
  })

  it('finishes a drawing from the Finish button', async () => {
    const wrapper = await mountAs('admin', 1366)
    await buttonByText(wrapper, 'Keep out')!.trigger('click')
    const finish = () => buttonByText(wrapper, 'Finish')!
    expect(finish().attributes('disabled')).toBeDefined()

    for (const point of [
      [0, 0],
      [2, 0],
      [2, 2],
    ]) {
      canvas(wrapper).vm.$emit('addPoint', point)
    }
    await flushPromises()
    expect(finish().attributes('disabled')).toBeUndefined()

    await finish().trigger('click')
    await flushPromises()
    expect(document.body.textContent).toContain('New zone')
    expect(document.body.textContent).toContain('3 corners')
  })
})
