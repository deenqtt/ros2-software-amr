/**
 * Station page by role.
 *
 * A viewer can look at every station and its numbers, and change none of
 * them: the controls stay in place, disabled, so the page still shows what
 * would be possible with the right role.
 */
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { enableAutoUnmount, flushPromises, mount, RouterLinkStub } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { ref } from 'vue'
import StationView from '../views/StationView.vue'
import { useAuthStore } from '@/stores/auth'
import { useStationStore } from '@/stores/stations'
import type { Role } from '@/domain/auth'
import type { Station } from '@/domain/types'

vi.mock('vue-sonner', () => ({
  toast: { success: vi.fn(), error: vi.fn(), info: vi.fn(), warning: vi.fn() },
}))

vi.mock('@/features/mapping/useRobotTelemetry', () => ({
  useRobotTelemetry: () => ({ pose: ref(null) }),
}))

vi.mock('@/shared/api/maps', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@/shared/api/maps')>()
  return { ...actual, mapsApi: { list: vi.fn().mockResolvedValue([]), fetchFile: vi.fn() } }
})

vi.mock('@/shared/api/robots', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@/shared/api/robots')>()
  return { ...actual, robotsApi: { list: vi.fn().mockResolvedValue([]) } }
})

function station(): Station {
  return {
    id: 's1',
    mapId: 'm1',
    name: 'Dock 1',
    type: 'pick',
    x: 1,
    y: 2,
    yaw: 0,
    note: null,
    taughtByRobotId: null,
    createdAt: '2026-09-28 08:00:00',
    updatedAt: '2026-09-28 08:00:00',
  }
}

async function mountAs(role: Role) {
  setActivePinia(createPinia())
  const auth = useAuthStore()
  auth.user = { id: 'u', username: 't', displayName: null, role, sessionIdleMinutes: 720, mustChangePassword: false }
  auth.status = 'signed-in'
  // No map in the registry, so nothing reloads the list set here.
  useStationStore().stations = [station()]
  const wrapper = mount(StationView, {
    attachTo: document.body,
    // The canvas needs a real layout engine; the controls under test do not.
    global: { stubs: { RouterLink: RouterLinkStub, StationMapCanvas: true } },
  })
  await flushPromises()
  return wrapper
}

async function rowMenu(wrapper: Awaited<ReturnType<typeof mountAs>>) {
  await wrapper.find('button[aria-label^="More actions"]').trigger('click')
  await flushPromises()
  const items = [...document.querySelectorAll('[role="menuitem"]')]
  return (label: string) => items.find((item) => item.textContent?.trim() === label)!
}

enableAutoUnmount(afterEach)

beforeEach(() => {
  document.body.innerHTML = ''
})

describe('StationView — roles', () => {
  it('shows a viewer Edit and Remove, disabled, with the reason', async () => {
    const wrapper = await mountAs('viewer')
    const item = await rowMenu(wrapper)
    for (const label of ['Edit', 'Remove']) {
      expect(item(label).hasAttribute('data-disabled')).toBe(true)
      expect(item(label).getAttribute('title')).toBe('Needs the admin role')
    }
    const add = wrapper.findAll('button').find((b) => b.text().includes('Add station'))!
    expect(add.attributes('disabled')).toBeDefined()
  })

  it('leaves them to an admin', async () => {
    const wrapper = await mountAs('admin')
    const item = await rowMenu(wrapper)
    expect(item('Remove').hasAttribute('data-disabled')).toBe(false)
    expect(item('Remove').hasAttribute('title')).toBe(false)
  })
})
