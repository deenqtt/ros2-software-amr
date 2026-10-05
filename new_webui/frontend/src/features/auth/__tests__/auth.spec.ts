/**
 * Sign-in: the store, the route guard, the 401 hook, and the page.
 *
 * fetch is stubbed per test with a tiny fake of the three auth endpoints, so
 * the guard is exercised against the real router table.
 */
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { RouterView } from 'vue-router'
import { router, safeNext } from '@/app/router'
import { installSessionWatch, useAuthStore } from '@/stores/auth'
import { api, setUnauthorizedHandler } from '@/shared/api/client'
import { atLeast, initials, roleBlocker } from '@/domain/auth'

const ME = {
  id: 'u-1',
  username: 'rifai',
  display_name: 'Rifai Hakim',
  role: 'operator',
  session_idle_minutes: 720,
}

function json(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  })
}

/** signedIn: what /auth/me answers. Login succeeds only for "right-password". */
function fakeBackend(signedIn: boolean) {
  return vi.spyOn(globalThis, 'fetch').mockImplementation(async (input, init) => {
    const url = String(input)
    if (url.endsWith('/auth/me')) {
      return signedIn ? json(ME) : json({ detail: 'Sign in to continue' }, 401)
    }
    if (url.endsWith('/auth/login')) {
      const body = JSON.parse(String(init?.body)) as { password: string }
      if (body.password !== 'right-password') {
        return json({ detail: 'Wrong username or password' }, 401)
      }
      signedIn = true
      return json(ME)
    }
    return json([])
  })
}

beforeEach(() => {
  setActivePinia(createPinia())
})

afterEach(() => {
  vi.restoreAllMocks()
  setUnauthorizedHandler(null)
})

describe('roles', () => {
  it('orders viewer < operator < admin', () => {
    expect(atLeast('admin', 'operator')).toBe(true)
    expect(atLeast('operator', 'admin')).toBe(false)
    expect(atLeast(null, 'viewer')).toBe(false)
  })

  it('explains a blocked control, and says nothing when allowed', () => {
    expect(roleBlocker('viewer', 'operator')).toBe('Needs the operator role')
    expect(roleBlocker('admin', 'operator')).toBe('')
  })

  it('makes initials from the full name, else the username', () => {
    expect(initials({ username: 'x', displayName: 'Budi Santoso' })).toBe('BS')
    expect(initials({ username: 'rifai', displayName: null })).toBe('RI')
  })
})

describe('safeNext', () => {
  it('only follows paths inside the app', () => {
    expect(safeNext('/mission?map=1')).toBe('/mission?map=1')
    expect(safeNext('//evil.example/x')).toBe('/dashboard')
    expect(safeNext('https://evil.example')).toBe('/dashboard')
    expect(safeNext('/login?next=/x')).toBe('/dashboard')
    expect(safeNext(undefined)).toBe('/dashboard')
  })
})

describe('route guard', () => {
  it('sends someone not signed in to sign-in, remembering where they were going', async () => {
    fakeBackend(false)
    await router.push('/station')
    expect(router.currentRoute.value.name).toBe('login')
    expect(router.currentRoute.value.query.next).toBe('/station')
  })

  it('keeps a non-admin out of admin pages', async () => {
    fakeBackend(true)
    await router.push('/dashboard')
    await router.push('/users')
    // Refused in place: still on the page they came from.
    expect(router.currentRoute.value.fullPath).toBe('/dashboard')
  })

  it('takes a signed-in person past the sign-in page', async () => {
    fakeBackend(true)
    await router.push('/login?next=/zone')
    expect(router.currentRoute.value.fullPath).toBe('/zone')
  })
})

describe('temporary passwords and super admins', () => {
  function signedInAs(me: Record<string, unknown>) {
    vi.spyOn(globalThis, 'fetch').mockImplementation(async (input) =>
      String(input).endsWith('/auth/me') ? json({ ...ME, ...me }) : json([]),
    )
  }

  it('sends someone on a temporary password to replace it, and nowhere else', async () => {
    signedInAs({ must_change_password: true })
    await router.push('/station')
    expect(router.currentRoute.value.name).toBe('set-password')
    expect(router.currentRoute.value.query.next).toBe('/station')
  })

  it('leaves the set-password page alone once the password is the person’s own', async () => {
    signedInAs({ must_change_password: false })
    await router.push('/set-password?next=/zone')
    expect(router.currentRoute.value.fullPath).toBe('/zone')
  })

  it('keeps a plain admin out of Users; lets a super admin in', async () => {
    signedInAs({ role: 'admin' })
    await router.push('/dashboard')
    await router.push('/users')
    expect(router.currentRoute.value.fullPath).toBe('/dashboard')

    setActivePinia(createPinia())
    vi.restoreAllMocks()
    signedInAs({ role: 'super_admin' })
    await router.push('/users')
    expect(router.currentRoute.value.fullPath).toBe('/users')
  })
})

describe('session ending under the page', () => {
  it('marks the session expired and calls back once on a 401', async () => {
    fakeBackend(true)
    const auth = useAuthStore()
    await auth.restore()
    const ended = vi.fn()
    installSessionWatch(ended)

    vi.spyOn(globalThis, 'fetch').mockResolvedValue(json({ detail: 'Sign in to continue' }, 401))
    await expect(api.get('/robots')).rejects.toMatchObject({ status: 401 })
    await expect(api.get('/maps')).rejects.toMatchObject({ status: 401 })

    expect(ended).toHaveBeenCalledTimes(1)
    expect(auth.status).toBe('signed-out')
    expect(auth.takeReason()).toBe('expired')
  })

  it('turns a 403 into the server’s sentence', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      json({ detail: { message: 'This needs the admin role', required_role: 'admin' } }, 403),
    )
    await expect(api.del('/stations/1')).rejects.toMatchObject({
      status: 403,
      message: 'This needs the admin role',
    })
  })
})

describe('sign-in page', () => {
  async function mountLogin() {
    await router.push('/login?next=/mission')
    await router.isReady()
    const wrapper = mount(RouterView, { global: { plugins: [router] }, attachTo: document.body })
    await flushPromises()
    return wrapper
  }

  it('shows the refusal and stays put on a wrong password', async () => {
    fakeBackend(false)
    const wrapper = await mountLogin()
    await wrapper.get('input[autocomplete="username"]').setValue('rifai')
    await wrapper.get('input[autocomplete="current-password"]').setValue('nope-nope')
    await wrapper.find('form').trigger('submit')
    await flushPromises()

    expect(wrapper.get('[role="alert"]').text()).toBe('Wrong username or password')
    expect(router.currentRoute.value.name).toBe('login')
    wrapper.unmount()
  })

  it('signs in and goes where the person was heading', async () => {
    fakeBackend(false)
    const wrapper = await mountLogin()
    await wrapper.get('input[autocomplete="username"]').setValue('rifai')
    await wrapper.get('input[autocomplete="current-password"]').setValue('right-password')
    await wrapper.find('form').trigger('submit')
    await flushPromises()

    // The destination is lazy-loaded, so the navigation outlives one flush.
    await vi.waitFor(() => expect(router.currentRoute.value.fullPath).toBe('/mission'), {
      timeout: 5000,
    })
    expect(useAuthStore().user?.username).toBe('rifai')
    wrapper.unmount()
  })

  it('counts down the server’s pause after too many tries', async () => {
    fakeBackend(false)
    const wrapper = await mountLogin()
    vi.spyOn(globalThis, 'fetch').mockImplementation(async (input) =>
      String(input).endsWith('/auth/login')
        ? new Response(JSON.stringify({ detail: 'Too many failed sign-ins.' }), {
            status: 429,
            headers: { 'Content-Type': 'application/json', 'Retry-After': '125' },
          })
        : json({ status: 'ok' }),
    )
    await wrapper.get('input[autocomplete="username"]').setValue('rifai')
    await wrapper.get('input[autocomplete="current-password"]').setValue('guess-guess')
    await wrapper.find('form').trigger('submit')
    await flushPromises()

    const submit = wrapper.get('button[type="submit"]')
    expect(submit.text()).toContain('Try again in 2:05')
    expect(submit.attributes('disabled')).toBeDefined()
    expect(wrapper.text()).toContain('Sign-in paused for this name')
    wrapper.unmount()
  })

  it('says the server is down and holds the form until it answers', async () => {
    vi.spyOn(globalThis, 'fetch').mockImplementation(async (input) => {
      if (String(input).endsWith('/auth/me')) return json({ detail: 'x' }, 401)
      throw new TypeError('Failed to fetch')
    })
    const wrapper = await mountLogin()

    expect(wrapper.text()).toContain('Can’t reach the server')
    expect(wrapper.text()).toContain('Server unreachable')
    expect(wrapper.get('button[type="submit"]').attributes('disabled')).toBeDefined()
    wrapper.unmount()
  })
})
