/**
 * Who is signed in.
 *
 * `restore()` asks the server once per page load; the router waits for it
 * before deciding where to go, so a refresh lands back on the same page instead
 * of flashing the sign-in screen.
 */
import { defineStore } from 'pinia'
import { computed, ref } from 'vue'
import { authApi } from '@/shared/api/auth'
import { setUnauthorizedHandler } from '@/shared/api/client'
import { atLeast, roleBlocker, type CurrentUser, type Role } from '@/domain/auth'

export type AuthStatus = 'unknown' | 'signed-in' | 'signed-out'

/** Why the sign-in page is showing, so it can say so. */
export type SignedOutReason = 'expired' | 'signed-out' | null

export const useAuthStore = defineStore('auth', () => {
  const user = ref<CurrentUser | null>(null)
  const status = ref<AuthStatus>('unknown')
  /** Set when a session ends under the page; read once by the sign-in page. */
  const reason = ref<SignedOutReason>(null)

  let restoring: Promise<void> | null = null

  const role = computed<Role | null>(() => user.value?.role ?? null)

  function can(needed: Role): boolean {
    return atLeast(role.value, needed)
  }

  /** '' when allowed, otherwise the reason to show on the disabled control. */
  function blocker(needed: Role): string {
    return roleBlocker(role.value, needed)
  }

  /** Ask the server once; later calls share the answer. */
  function restore(): Promise<void> {
    if (!restoring) {
      restoring = authApi
        .me()
        .then((me) => {
          user.value = me
          status.value = me ? 'signed-in' : 'signed-out'
        })
        .catch(() => {
          // Backend unreachable. Treated as signed out so the sign-in page can
          // say the server is down, rather than every page failing its own way.
          user.value = null
          status.value = 'signed-out'
        })
    }
    return restoring
  }

  async function signIn(username: string, password: string): Promise<void> {
    user.value = await authApi.login(username, password)
    status.value = 'signed-in'
    reason.value = null
    restoring = Promise.resolve()
  }

  /**
   * Sign out and reload into the sign-in page.
   *
   * A full reload rather than a route change: stores, live robot connections
   * and cached fleet data from this person's session must not still be in
   * memory when the next person signs in at the same screen.
   */
  async function signOut(): Promise<void> {
    try {
      await authApi.logout()
    } finally {
      window.location.assign('/login?reason=signed-out')
    }
  }

  /** The server said 401 mid-session. */
  function sessionEnded(): void {
    if (status.value !== 'signed-in') return
    user.value = null
    status.value = 'signed-out'
    reason.value = 'expired'
  }

  /** The temporary password has just been replaced. */
  function passwordChanged(): void {
    if (user.value) user.value = { ...user.value, mustChangePassword: false }
  }

  function takeReason(): SignedOutReason {
    const value = reason.value
    reason.value = null
    return value
  }

  return {
    user,
    status,
    role,
    can,
    blocker,
    restore,
    signIn,
    signOut,
    sessionEnded,
    passwordChanged,
    takeReason,
  }
})

/** Wire the API client's 401 hook to the store and the router. Called once. */
export function installSessionWatch(onEnded: () => void): void {
  setUnauthorizedHandler(() => {
    const auth = useAuthStore()
    if (auth.status !== 'signed-in') return
    auth.sessionEnded()
    onEnded()
  })
}
