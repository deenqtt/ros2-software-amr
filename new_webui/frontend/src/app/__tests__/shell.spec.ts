/**
 * Shell smoke test.
 *
 * Typecheck and lint cannot see a template that throws at render time, so this
 * mounts the real shell against the real router and asserts the navigation and
 * header actually come up.
 */
import { afterEach, describe, expect, it, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { createRouter, createMemoryHistory } from 'vue-router'
import AppShell from '../layouts/AppShell.vue'
import { NAV_GROUPS, navGroupsFor } from '../navigation'
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
  it('exposes exactly the seven destinations to everyone, with Alarm in its own group', () => {
    const everyone = navGroupsFor((role) => role === 'viewer')
    const labels = everyone.flatMap((g) => g.items.map((i) => i.label))
    expect(labels).toEqual(EXPECTED_MENU)

    const alerts = everyone.at(-1)
    expect(alerts?.items).toHaveLength(1)
    expect(alerts?.items[0]?.label).toBe('Alarm')
    expect(alerts?.items[0]?.badgeKey).toBe('alarms')
  })

  it('adds Users and Activity for admins only', () => {
    const admin = navGroupsFor(() => true).flatMap((g) => g.items.map((i) => i.label))
    expect(admin).toEqual([...EXPECTED_MENU, 'Users', 'Activity'])
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

describe('folding the rail for a page', () => {
  beforeEach(() => {
    localStorage.clear()
    setActivePinia(createPinia())
  })

  it('folds without changing the saved preference, and restores it', () => {
    const ui = useUiStore()
    expect(ui.navCollapsed).toBe(false)
    ui.foldNav(true)
    expect(ui.navCollapsed).toBe(true)
    expect(localStorage.getItem('amr.ui.navCollapsed')).not.toBe('true')
    ui.foldNav(false)
    expect(ui.navCollapsed).toBe(false)
  })

  it('lets the operator expand it while folded', () => {
    const ui = useUiStore()
    ui.foldNav(true)
    ui.toggleNav()
    expect(ui.navCollapsed).toBe(false)
  })
})

describe('the rail on phones and tablets', () => {
  function screenOf(width: number) {
    window.matchMedia = ((query: string) => {
      const max = Number(/max-width:\s*(\d+)px/.exec(query)?.[1] ?? Infinity)
      return {
        matches: width <= max,
        media: query,
        onchange: null,
        addEventListener: () => {},
        removeEventListener: () => {},
        addListener: () => {},
        removeListener: () => {},
        dispatchEvent: () => false,
      }
    }) as typeof window.matchMedia
    localStorage.clear()
    setActivePinia(createPinia())
    return useUiStore()
  }

  afterEach(() => {
    // jsdom has no matchMedia of its own; leave none behind.
    delete (window as { matchMedia?: unknown }).matchMedia
  })

  it('opens a drawer on a phone instead of a rail', () => {
    const ui = screenOf(390)
    expect(ui.screen).toBe('phone')
    expect(ui.navCollapsed).toBe(false) // the drawer always shows labels
    ui.toggleNav()
    expect(ui.drawerOpen).toBe(true)
    ui.closeNav()
    expect(ui.drawerOpen).toBe(false)
  })

  it('starts a tablet on icons, and opening it does not change the saved desktop choice', () => {
    const ui = screenOf(820)
    expect(ui.screen).toBe('tablet')
    expect(ui.navCollapsed).toBe(true)
    ui.toggleNav()
    expect(ui.navCollapsed).toBe(false)
    expect(localStorage.getItem('amr.ui.navCollapsed')).not.toBe('true')
    ui.closeNav()
    expect(ui.navCollapsed).toBe(true)
  })

  it('keeps the desktop rail as the operator left it', () => {
    const ui = screenOf(1440)
    expect(ui.screen).toBe('desktop')
    expect(ui.navCollapsed).toBe(false)
  })
})
