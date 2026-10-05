/**
 * Users page: a phone list that shows status only when something is off, the
 * same row menu (with the self-guards) as the table, and the last sign-in one
 * tap deeper.
 */
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { enableAutoUnmount, flushPromises, mount, RouterLinkStub } from '@vue/test-utils'
import type { VueWrapper } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import UsersView from '../views/UsersView.vue'
import { useAuthStore } from '@/stores/auth'
import type { UserAccount } from '@/shared/api/auth'

vi.mock('vue-sonner', () => ({
  toast: { success: vi.fn(), error: vi.fn(), info: vi.fn(), warning: vi.fn() },
}))

const usersMock = vi.hoisted(() => ({
  list: vi.fn(),
  create: vi.fn(),
  update: vi.fn(),
  remove: vi.fn(),
}))

vi.mock('@/shared/api/auth', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@/shared/api/auth')>()
  return { ...actual, usersApi: usersMock }
})

function account(overrides: Partial<UserAccount> & Pick<UserAccount, 'id' | 'username'>): UserAccount {
  return {
    displayName: null,
    role: 'operator',
    disabled: false,
    mustChangePassword: false,
    createdAt: '2026-09-01 08:00:00',
    lastLoginAt: '2026-10-04 06:30:00',
    ...overrides,
  }
}

const USERS: UserAccount[] = [
  account({ id: 'u1', username: 'admin', displayName: 'Ayu Admin', role: 'super_admin' }),
  account({
    id: 'u2',
    username: 'budi.s',
    displayName: 'Budi Santoso',
    role: 'operator',
    mustChangePassword: true,
    lastLoginAt: null,
  }),
  account({ id: 'u3', username: 'citra', role: 'viewer', disabled: true }),
]

async function mountView(users: UserAccount[] | Error = USERS) {
  if (users instanceof Error) usersMock.list.mockRejectedValue(users)
  else usersMock.list.mockResolvedValue(users)
  const wrapper = mount(UsersView, {
    attachTo: document.body,
    global: { stubs: { RouterLink: RouterLinkStub } },
  })
  await flushPromises()
  return wrapper
}

/** jsdom applies no CSS, so both layouts render; the list is the md:hidden one. */
function phoneRows(wrapper: VueWrapper) {
  return wrapper.findAll('ul.md\\:hidden > li')
}

async function openMenu(row: { find: VueWrapper['find'] }): Promise<Element> {
  await row.find('button[aria-label^="Actions for"]').trigger('click')
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

enableAutoUnmount(afterEach)

beforeEach(() => {
  vi.clearAllMocks()
  setActivePinia(createPinia())
  useAuthStore().user = {
    id: 'u1',
    username: 'admin',
    displayName: 'Ayu Admin',
    role: 'super_admin',
    sessionIdleMinutes: 720,
    mustChangePassword: false,
  }
})

describe('UsersView on a phone', () => {
  it('shows who and their role, and status only when something is off', async () => {
    const wrapper = await mountView()
    const rows = phoneRows(wrapper)
    expect(rows).toHaveLength(3)
    expect(rows[0]!.text()).toContain('(you)')
    expect(rows[0]!.text()).toContain('admin · Super admin')
    expect(rows[1]!.text()).toContain('budi.s · Operator')
    expect(rows.filter((row) => row.text().includes('Temporary password'))).toEqual([rows[1]])
    expect(rows.filter((row) => row.text().includes('Disabled'))).toEqual([rows[2]])
    expect(wrapper.find('ul.md\\:hidden').text()).not.toContain('Active')
    expect(rows[2]!.classes()).toContain('opacity-60')
  })

  it('opens the account from the row, with its last sign-in', async () => {
    const wrapper = await mountView()
    await phoneRows(wrapper)[1]!.find('button:not([aria-label])').trigger('click')
    await flushPromises()
    const dialog = document.querySelector('[role="dialog"]')
    expect(dialog?.textContent).toContain('Edit Budi Santoso')
    expect(dialog?.textContent).toContain('Last sign-in: Never')
  })

  it('will not disable or delete your own account', async () => {
    const wrapper = await mountView()
    const menu = await openMenu(phoneRows(wrapper)[0]!)
    expect(menuItem(menu, 'Disable').hasAttribute('data-disabled')).toBe(true)
    expect(menuItem(menu, 'Delete').hasAttribute('data-disabled')).toBe(true)
    expect(menuItem(menu, 'Edit').hasAttribute('data-disabled')).toBe(false)
  })

  it('asks before deleting someone else', async () => {
    const wrapper = await mountView()
    const menu = await openMenu(phoneRows(wrapper)[1]!)
    menuItem(menu, 'Delete').click()
    await flushPromises()
    expect(document.querySelector('[role="alertdialog"]')?.textContent).toContain('Delete budi.s?')
    expect(usersMock.remove).not.toHaveBeenCalled()
  })
})

describe('UsersView table', () => {
  it('keeps last sign-in for wide screens only, and a menu on every row', async () => {
    const wrapper = await mountView()
    const table = wrapper.get('table')
    const head = table.findAll('th').find((th) => th.text() === 'Last sign-in')!
    expect(head.classes()).toContain('lg:table-cell')
    expect(head.classes()).not.toContain('md:table-cell')
    const bodyRows = table.findAll('tbody tr')
    expect(bodyRows).toHaveLength(3)
    USERS.forEach((user, index) => {
      expect(bodyRows[index]!.find(`button[aria-label="Actions for ${user.username}"]`).exists()).toBe(
        true,
      )
    })
  })
})

describe('UsersView when the list fails', () => {
  it('says so and offers a retry, with no rows', async () => {
    const wrapper = await mountView(new Error('Server unreachable'))
    expect(wrapper.text()).toContain('Could not load accounts')
    expect(wrapper.findAll('button').some((b) => b.text() === 'Try again')).toBe(true)
    expect(phoneRows(wrapper)).toHaveLength(0)
    expect(wrapper.find('table').exists()).toBe(false)
  })
})
