/**
 * Stop & park is an operator action; a viewer sees it, disabled, with the reason.
 */
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { mount, RouterLinkStub } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import RobotBar from '../components/RobotBar.vue'
import { useAuthStore } from '@/stores/auth'
import type { Role } from '@/domain/auth'
import type { RobotConfig } from '@/domain/types'

vi.mock('vue-router', async (importOriginal) => ({
  ...(await importOriginal<typeof import('vue-router')>()),
  useRoute: () => ({ name: 'robot-nav', params: { robotId: 'r1' } }),
}))

const ROBOT: RobotConfig = {
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
}

function mountAs(role: Role) {
  const auth = useAuthStore()
  auth.user = { id: 'u', username: 't', displayName: null, role, sessionIdleMinutes: 720, mustChangePassword: false }
  auth.status = 'signed-in'
  return mount(RobotBar, {
    props: { robot: ROBOT, linkState: 'online', attempt: 0, stopPending: false },
    global: { stubs: { RouterLink: RouterLinkStub } },
  })
}

function stopButton(wrapper: ReturnType<typeof mountAs>) {
  return wrapper.findAll('button').find((b) => b.text().includes('Stop & park'))!
}

beforeEach(() => setActivePinia(createPinia()))

describe('RobotBar — Stop & park', () => {
  it('is disabled for a viewer, with the role as the reason', () => {
    const button = stopButton(mountAs('viewer'))
    expect(button.attributes('disabled')).toBeDefined()
    expect(button.element.parentElement?.getAttribute('title')).toBe('Needs the operator role')
  })

  it('is available to an operator', async () => {
    const wrapper = mountAs('operator')
    const button = stopButton(wrapper)
    expect(button.attributes('disabled')).toBeUndefined()
    await button.trigger('click')
    expect(wrapper.emitted('stop')).toHaveLength(1)
  })
})
