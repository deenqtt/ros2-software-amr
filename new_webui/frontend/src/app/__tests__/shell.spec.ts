/**
 * Shell smoke test.
 *
 * Typecheck and lint cannot see a template that throws at render time, so this
 * mounts the real shell against the real router and asserts the navigation and
 * header actually come up.
 */
import { describe, expect, it, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { createRouter, createMemoryHistory } from 'vue-router'
import AppShell from '../layouts/AppShell.vue'
import { NAV_GROUPS } from '../navigation'
import { useAlarmStore } from '@/stores/alarms'
import { useUiStore } from '@/stores/ui'

const EXPECTED_MENU = [
  'Dashboard',
  'Robot',
  'Maps',
  'Mission',
  'Station',
  'Zone',
  'Alarm',
]

function makeRouter() {
  return createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/', redirect: '/dashboard' },
      {
        path: '/dashboard',
        name: 'dashboard',
        component: { template: '<div>dashboard</div>' },
        meta: { title: 'Dashboard', subtitle: 'Fleet status at a glance' },
      },
      { path: '/robot', component: { template: '<div />' }, meta: { title: 'Robot' } },
      { path: '/maps', component: { template: '<div />' }, meta: { title: 'Maps' } },
      { path: '/mission', component: { template: '<div />' }, meta: { title: 'Mission' } },
      { path: '/station', component: { template: '<div />' }, meta: { title: 'Station' } },
      { path: '/zone', component: { template: '<div />' }, meta: { title: 'Zone' } },
      { path: '/alarm', component: { template: '<div />' }, meta: { title: 'Alarm' } },
    ],
  })
}

async function mountShell() {
  const router = makeRouter()
  await router.push('/dashboard')
  await router.isReady()
  const wrapper = mount(AppShell, { global: { plugins: [router] } })
  await router.isReady()
  return { wrapper, router }
}

describe('navigation model', () => {
  it('exposes exactly the seven destinations, with Alarm in its own group', () => {
    const labels = NAV_GROUPS.flatMap((g) => g.items.map((i) => i.label))
    expect(labels).toEqual(EXPECTED_MENU)

    const lastGroup = NAV_GROUPS.at(-1)
    expect(lastGroup?.items).toHaveLength(1)
    expect(lastGroup?.items[0]?.label).toBe('Alarm')
    expect(lastGroup?.items[0]?.badgeKey).toBe('alarms')
  })

  it('gives every item a route and an icon', () => {
    for (const item of NAV_GROUPS.flatMap((g) => g.items)) {
      expect(item.to.startsWith('/')).toBe(true)
      expect(item.icon).toBeTruthy()
    }
  })
})

describe('AppShell', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('renders every menu item in the sidebar', async () => {
    const { wrapper } = await mountShell()
    const text = wrapper.text()
    for (const label of EXPECTED_MENU) {
      expect(text).toContain(label)
    }
  })

  it('renders the page title from route meta in the header', async () => {
    const { wrapper } = await mountShell()
    expect(wrapper.find('h1').text()).toBe('Dashboard')
    expect(wrapper.text()).toContain('Fleet status at a glance')
  })

  it('updates the header title when the route changes', async () => {
    const { wrapper, router } = await mountShell()
    await router.push('/zone')
    await wrapper.vm.$nextTick()
    expect(wrapper.find('h1').text()).toBe('Zone')
  })

  it('shows no alarm count until an alarm is raised', async () => {
    const { wrapper } = await mountShell()
    const alarms = useAlarmStore()
    expect(alarms.activeCount).toBe(0)

    alarms.raise({ severity: 'fault', source: 'AMR-01', message: 'Navigation aborted' })
    await wrapper.vm.$nextTick()
    expect(alarms.activeCount).toBe(1)
    expect(wrapper.text()).toContain('1')
  })

  it('collapses and expands via the edge control, which stays mounted in both states', async () => {
    const { wrapper } = await mountShell()
    expect(wrapper.find('aside').classes()).toContain('w-sidebar')

    const toggle = wrapper.get('[aria-label="Collapse sidebar"]')
    expect(toggle.attributes('aria-expanded')).toBe('true')

    await toggle.trigger('click')
    expect(wrapper.find('aside').classes()).toContain('w-sidebar-collapsed')

    // Same control, same position — not a different button in the footer.
    const expand = wrapper.get('[aria-label="Expand sidebar"]')
    expect(expand.attributes('aria-expanded')).toBe('false')
    await expand.trigger('click')
    expect(wrapper.find('aside').classes()).toContain('w-sidebar')
  })

  it('offers light, dark and system themes, and applies the class to <html>', async () => {
    const { wrapper } = await mountShell()
    const ui = useUiStore()

    const group = wrapper.get('[role="radiogroup"]')
    expect(group.findAll('[role="radio"]')).toHaveLength(3)

    ui.setTheme('dark')
    await wrapper.vm.$nextTick()
    expect(document.documentElement.classList.contains('dark')).toBe(true)

    ui.setTheme('light')
    await wrapper.vm.$nextTick()
    expect(document.documentElement.classList.contains('dark')).toBe(false)
  })

  it('cycles light -> dark -> system -> light for the collapsed rail', async () => {
    await mountShell()
    const ui = useUiStore()

    ui.setTheme('light')
    ui.cycleTheme()
    expect(ui.theme).toBe('dark')
    ui.cycleTheme()
    expect(ui.theme).toBe('system')
    ui.cycleTheme()
    expect(ui.theme).toBe('light')
  })

  it('collapses the theme control to a single button when the rail is collapsed', async () => {
    const { wrapper } = await mountShell()
    const ui = useUiStore()

    ui.navCollapsed = true
    await wrapper.vm.$nextTick()
    expect(wrapper.find('[role="radiogroup"]').exists()).toBe(false)
  })
})
