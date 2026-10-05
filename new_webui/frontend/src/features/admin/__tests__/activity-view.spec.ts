/**
 * Activity log: paged on the server, pinned while paging, filters in the URL.
 */
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { createMemoryHistory, createRouter } from 'vue-router'
import ActivityView from '../views/ActivityView.vue'

function json(body: unknown): Response {
  return new Response(JSON.stringify(body), {
    status: 200,
    headers: { 'Content-Type': 'application/json' },
  })
}

function entry(id: number) {
  return {
    id,
    at: '2026-10-05 02:00:00',
    user_id: 'u1',
    username: 'dina',
    role: 'operator',
    action: 'POST /api/runs',
    method: 'POST',
    path: '/api/runs',
    status: 201,
    detail: null,
    ip: '10.0.0.5',
  }
}

let auditCalls: URL[] = []

beforeEach(() => {
  setActivePinia(createPinia())
  auditCalls = []
  vi.spyOn(globalThis, 'fetch').mockImplementation(async (input) => {
    const url = new URL(String(input), 'http://test')
    if (url.pathname.endsWith('/users')) return json([])
    auditCalls.push(url)
    const offset = Number(url.searchParams.get('offset'))
    const limit = Number(url.searchParams.get('limit'))
    const items = Array.from({ length: Math.max(0, Math.min(limit, 60 - offset)) }, (_, i) =>
      entry(100 - offset - i),
    )
    return json({ items, total: 60, upto_id: 100 })
  })
})

afterEach(() => vi.restoreAllMocks())

async function mountView(path = '/activity') {
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [{ path: '/activity', component: ActivityView }],
  })
  await router.push(path)
  await router.isReady()
  const wrapper = mount(ActivityView, { global: { plugins: [router] } })
  await flushPromises()
  return { wrapper, router }
}

describe('ActivityView', () => {
  it('shows a page from the server with the total, and the words for each row', async () => {
    const { wrapper } = await mountView()
    expect(wrapper.text()).toContain('1–25 of 60')
    expect(wrapper.text()).toContain('Started a mission')
    const first = auditCalls[0]!
    expect(first.searchParams.get('offset')).toBe('0')
    expect(first.searchParams.get('upto_id')).toBeNull()
    expect(first.searchParams.get('since')).toBeTruthy()
  })

  it('pins the reading when paging, and puts the page in the URL', async () => {
    const { wrapper, router } = await mountView()
    await wrapper.get('button[aria-label="Next page"]').trigger('click')
    await flushPromises()

    const next = auditCalls.at(-1)!
    expect(next.searchParams.get('offset')).toBe('25')
    expect(next.searchParams.get('upto_id')).toBe('100')
    expect(router.currentRoute.value.query.page).toBe('2')
    expect(wrapper.text()).toContain('26–50 of 60')
  })

  it('starts a fresh reading from page 1 when the search changes', async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true })
    const { wrapper, router } = await mountView('/activity?page=2')
    expect(auditCalls[0]!.searchParams.get('offset')).toBe('25')

    await wrapper.get('input[type="search"]').setValue('dina')
    vi.advanceTimersByTime(350)
    await flushPromises()

    const searched = auditCalls.at(-1)!
    expect(searched.searchParams.get('q')).toBe('dina')
    expect(searched.searchParams.get('offset')).toBe('0')
    expect(searched.searchParams.get('upto_id')).toBeNull()
    expect(router.currentRoute.value.query).toEqual({ q: 'dina' })
    vi.useRealTimers()
  })

  it('offers the filtered log as a CSV download', async () => {
    const { wrapper } = await mountView('/activity?kind=refused&range=all')
    const href = wrapper.get('a[download]').attributes('href')!
    expect(href).toContain('/audit/export.csv')
    expect(href).toContain('kind=refused')
    expect(href).not.toContain('since=')
  })
})
