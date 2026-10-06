/**
 * Agent token controls on the robot detail page.
 *
 * The plaintext is shown once, so the tests pin who may ask for it, that it
 * reaches the dialog, and that it does not outlive the dialog.
 */
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { enableAutoUnmount, flushPromises, mount, RouterLinkStub } from '@vue/test-utils'
import { ref } from 'vue'
import { createPinia, setActivePinia } from 'pinia'
import RobotDetailView from '../views/RobotDetailView.vue'
import AgentTokenDialog from '../components/AgentTokenDialog.vue'
import { useFleetStore } from '@/stores/fleet'
import { useAuthStore } from '@/stores/auth'
import type { Role } from '@/domain/auth'
import type { RobotConfig } from '@/domain/types'

vi.mock('vue-sonner', () => ({
  toast: { success: vi.fn(), error: vi.fn(), info: vi.fn(), warning: vi.fn() },
}))

vi.mock('vue-router', async (importOriginal) => ({
  ...(await importOriginal<typeof import('vue-router')>()),
  useRoute: () => ({ params: { robotId: 'robot-1' } }),
}))

vi.mock('@/features/mapping/useRobotTelemetry', () => ({
  useRobotTelemetry: () => ({ agent: ref(null) }),
}))

const apiMock = vi.hoisted(() => ({
  list: vi.fn(),
  createAgentToken: vi.fn(),
  revokeAgentToken: vi.fn(),
}))

vi.mock('@/shared/api/robots', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@/shared/api/robots')>()
  return { ...actual, robotsApi: apiMock }
})

const poolMock = vi.hoisted(() => ({
  sync: vi.fn(),
  focus: vi.fn(),
  setMuted: vi.fn(),
  isMuted: vi.fn(() => false),
  clientFor: vi.fn(() => null),
  onSnapshot: vi.fn(() => () => {}),
  dispose: vi.fn(),
}))
vi.mock('@/app/ros/pool', () => ({ useRosPool: () => poolMock, resetRosPool: () => {} }))

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
    agentTokenSet: false,
    agentTokenCreatedAt: null,
    ...overrides,
  }
}

function signInAs(role: Role) {
  const auth = useAuthStore()
  auth.user = { id: 'u', username: 't', displayName: null, role, sessionIdleMinutes: 720, mustChangePassword: false }
  auth.status = 'signed-in'
}

async function mountView(role: Role, row: RobotConfig = robot()) {
  signInAs(role)
  apiMock.list.mockResolvedValue([row])
  const wrapper = mount(RobotDetailView, {
    attachTo: document.body,
    global: { stubs: { RouterLink: RouterLinkStub, RobotBar: true } },
  })
  await flushPromises()
  return wrapper
}

const TOKEN = 'tok_super_secret_value'

enableAutoUnmount(afterEach)

beforeEach(() => {
  setActivePinia(createPinia())
  localStorage.clear()
  document.body.innerHTML = ''
  apiMock.list.mockReset().mockResolvedValue([])
  apiMock.createAgentToken.mockReset().mockResolvedValue({ token: TOKEN, createdAt: '2026-10-06T00:00:00Z' })
  apiMock.revokeAgentToken.mockReset().mockResolvedValue(undefined)
})

describe('agent token on the robot detail page', () => {
  it('shows "Not set" and a Generate button', async () => {
    const wrapper = await mountView('admin')
    expect(wrapper.get('[data-testid="agent-token-status"]').text()).toBe('Not set')
    expect(wrapper.get('[data-testid="agent-token-generate"]').text()).toBe('Generate token')
    expect(wrapper.find('[data-testid="agent-token-revoke"]').exists()).toBe(false)
  })

  it('does not enable Generate for a viewer, and explains why', async () => {
    const wrapper = await mountView('viewer')
    const button = wrapper.get('[data-testid="agent-token-generate"]')
    expect(button.attributes('disabled')).toBeDefined()
    expect(button.element.closest('[title]')?.getAttribute('title')).toBeTruthy()
    await button.trigger('click')
    expect(apiMock.createAgentToken).not.toHaveBeenCalled()
  })

  it('generates as admin, shows the token once, then clears it on close', async () => {
    const wrapper = await mountView('admin')
    await wrapper.get('[data-testid="agent-token-generate"]').trigger('click')
    await flushPromises()

    expect(apiMock.createAgentToken).toHaveBeenCalledWith('robot-1')
    const shown = document.querySelector('[data-testid="agent-token"]')
    expect(shown?.textContent).toContain(TOKEN)
    expect(document.body.textContent).toContain('shown only once')
    // Reloaded so the status row reflects the new token.
    expect(apiMock.list).toHaveBeenCalledTimes(2)

    const done = [...document.querySelectorAll('button')].find((b) => b.textContent?.trim() === 'Done')
    done!.click()
    await flushPromises()
    expect(document.body.textContent).not.toContain(TOKEN)
  })

  it('asks for confirmation before rotating, and rotates on confirm', async () => {
    const wrapper = await mountView(
      'admin',
      robot({ agentTokenSet: true, agentTokenCreatedAt: '2026-10-01T08:00:00Z' }),
    )
    expect(wrapper.get('[data-testid="agent-token-status"]').text()).toMatch(/^Set on /)
    await wrapper.get('[data-testid="agent-token-generate"]').trigger('click')
    await flushPromises()
    expect(apiMock.createAgentToken).not.toHaveBeenCalled()
    expect(document.body.textContent).toContain('AMR_AGENT_TOKEN')

    const confirm = [...document.querySelectorAll('button')].find((b) => b.textContent?.trim() === 'Rotate')
    confirm!.click()
    await flushPromises()
    expect(apiMock.createAgentToken).toHaveBeenCalledWith('robot-1')
  })

  it('revokes only after confirmation', async () => {
    const wrapper = await mountView('admin', robot({ agentTokenSet: true, agentTokenCreatedAt: null }))
    await wrapper.get('[data-testid="agent-token-revoke"]').trigger('click')
    await flushPromises()
    expect(apiMock.revokeAgentToken).not.toHaveBeenCalled()

    // The page's own Revoke button is also in the DOM; the dialog's is last.
    const confirm = [...document.querySelectorAll('button')].filter((b) => b.textContent?.trim() === 'Revoke').at(-1)
    confirm!.click()
    await flushPromises()
    expect(apiMock.revokeAgentToken).toHaveBeenCalledWith('robot-1')
    expect(useFleetStore().loaded).toBe(true)
  })
})

describe('AgentTokenDialog', () => {
  it('falls back to selecting the token when the clipboard is unavailable', async () => {
    Object.defineProperty(navigator, 'clipboard', { value: undefined, configurable: true })
    const wrapper = mount(AgentTokenDialog, { props: { open: true, token: TOKEN }, attachTo: document.body })
    await flushPromises()
    const copy = [...document.querySelectorAll('button')].find((b) => b.textContent?.includes('Copy'))
    copy!.click()
    await flushPromises()
    expect(document.body.textContent).toContain('Could not copy automatically')
    wrapper.unmount()
  })

  it('copies through the clipboard when it exists', async () => {
    const writeText = vi.fn().mockResolvedValue(undefined)
    Object.defineProperty(navigator, 'clipboard', { value: { writeText }, configurable: true })
    mount(AgentTokenDialog, { props: { open: true, token: TOKEN }, attachTo: document.body })
    await flushPromises()
    const copy = [...document.querySelectorAll('button')].find((b) => b.textContent?.includes('Copy'))
    copy!.click()
    await flushPromises()
    expect(writeText).toHaveBeenCalledWith(TOKEN)
  })
})
