<script setup lang="ts">
/**
 * Sign in: the control room.
 *
 * In the app's own theme, light or dark, as chosen on this device. Form on the
 * left; on wide
 * screens the floor on the right, with the site, the time, and the one thing
 * someone may need without signing in at all: how to stop a robot.
 *
 * Every way a sign-in can fail has its own words and its own look, so nobody
 * has to guess which of them happened:
 * - wrong name or password: under the password field, and the field clears;
 * - too many tries: a notice, and the button counts down the server's pause;
 * - session ended: a notice saying so, before they type anything;
 * - server down: a notice, the form disabled, and a retry every 10 s.
 *
 * The last username is remembered on this screen, so a shared terminal asks
 * only for the password; it is a name, not a secret.
 */
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import {
  CircleAlert,
  Clock,
  Hourglass,
  LoaderCircle,
  Lock,
  OctagonX,
  WifiOff,
} from 'lucide-vue-next'
import { useAuthStore } from '@/stores/auth'
import { safeNext } from '@/app/router'
import { config } from '@/app/config'
import { ApiError } from '@/shared/api/client'
import { serverReachable } from '@/shared/api/auth'
import { cn } from '@/shared/lib/utils'
import floorPhoto from '@/assets/images/login-floor.jpg'

const LAST_USERNAME_KEY = 'amr.lastUsername'
const HEALTH_RETRY_MS = 10_000

const auth = useAuthStore()
const route = useRoute()
const router = useRouter()

const host = window.location.host
const site = config.siteName

const username = ref('')
const password = ref('')
const showPassword = ref(false)
const capsLock = ref(false)
const pending = ref(false)
/** Wrong name or password: shown under the field, not as a banner. */
const credentialsError = ref(false)
/** Anything else that went wrong on submit. */
const otherError = ref<string | null>(null)
/** null until the first health check answers. */
const reachable = ref<boolean | null>(null)
/** Seconds left in a sign-in pause, counting down. */
const pausedFor = ref(0)

const usernameInput = ref<HTMLInputElement | null>(null)
const passwordInput = ref<HTMLInputElement | null>(null)

// Read once: the store hands the reason over and forgets it.
const reason = route.query.reason ?? auth.takeReason()
const returnTo = computed(() => {
  const next = safeNext(route.query.next)
  if (next === '/dashboard') return null
  const resolved = router.resolve(next)
  return typeof resolved.meta.title === 'string' ? resolved.meta.title : null
})

const offline = computed(() => reachable.value === false)
const paused = computed(() => pausedFor.value > 0)
const locked = computed(() => pending.value || offline.value)

type Tone = 'red' | 'amber' | 'blue'

const notice = computed(() => {
  if (offline.value) {
    return {
      tone: 'red' as Tone,
      icon: WifiOff,
      title: 'Can’t reach the server',
      body: `Check this terminal’s network, or whether the server at ${host} is on. Retrying every 10 s.`,
    }
  }
  if (paused.value) {
    return {
      tone: 'amber' as Tone,
      icon: Hourglass,
      title: 'Sign-in paused for this name',
      body: 'Too many wrong passwords in a row. Wait for the countdown, or ask an admin to reset it.',
    }
  }
  if (reason === 'expired') {
    return {
      tone: 'blue' as Tone,
      icon: Clock,
      title: 'Your session ended',
      body: returnTo.value
        ? `Sign in again to go back to ${returnTo.value}.`
        : 'Sign in again to carry on.',
    }
  }
  if (reason === 'signed-out') {
    return { tone: 'blue' as Tone, icon: Clock, title: 'You have signed out', body: '' }
  }
  return null
})

const NOTICE_TONE: Record<Tone, string> = {
  red: 'border-status-fault/30 bg-status-fault/[0.06] text-status-fault',
  amber: 'border-status-warn/30 bg-status-warn/[0.08] text-status-warn',
  blue: 'border-primary/30 bg-primary/[0.06] text-ink',
}

function countdown(seconds: number): string {
  const m = Math.floor(seconds / 60)
  const s = seconds % 60
  return `${m}:${String(s).padStart(2, '0')}`
}

// ── Clock ──────────────────────────────────────────────────────────────────────

const now = ref(new Date())
const time = computed(() =>
  now.value.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', hour12: false }),
)
const date = computed(() =>
  now.value.toLocaleDateString(undefined, { weekday: 'long', day: 'numeric', month: 'long' }),
)

// ── Timers ─────────────────────────────────────────────────────────────────────

let clockTimer: ReturnType<typeof setInterval> | undefined
let healthTimer: ReturnType<typeof setTimeout> | undefined
let pauseTimer: ReturnType<typeof setInterval> | undefined
let alive = true

async function checkHealth(): Promise<void> {
  clearTimeout(healthTimer)
  reachable.value = await serverReachable()
  if (!alive) return
  // Keep checking while it is down, so the form comes back by itself.
  if (!reachable.value) healthTimer = setTimeout(checkHealth, HEALTH_RETRY_MS)
}

function startPause(seconds: number): void {
  pausedFor.value = Math.max(1, Math.round(seconds))
  clearInterval(pauseTimer)
  pauseTimer = setInterval(() => {
    pausedFor.value = Math.max(0, pausedFor.value - 1)
    if (pausedFor.value === 0) clearInterval(pauseTimer)
  }, 1000)
}

onMounted(() => {
  username.value = readLastUsername()
  // Straight to the password when the name is already there.
  ;(username.value ? passwordInput.value : usernameInput.value)?.focus()
  clockTimer = setInterval(() => (now.value = new Date()), 15_000)
  void checkHealth()
})

onBeforeUnmount(() => {
  alive = false
  clearInterval(clockTimer)
  clearTimeout(healthTimer)
  clearInterval(pauseTimer)
})

// ── Remembered username ────────────────────────────────────────────────────────

function readLastUsername(): string {
  try {
    return window.localStorage.getItem(LAST_USERNAME_KEY) ?? ''
  } catch {
    return ''
  }
}

function rememberUsername(name: string): void {
  try {
    window.localStorage.setItem(LAST_USERNAME_KEY, name)
  } catch {
    // Private window or blocked storage: only a convenience is lost.
  }
}

// ── Submit ─────────────────────────────────────────────────────────────────────

function trackCapsLock(event: KeyboardEvent): void {
  capsLock.value = event.getModifierState?.('CapsLock') ?? false
}

async function onSubmit(): Promise<void> {
  credentialsError.value = false
  otherError.value = null
  if (!username.value.trim() || !password.value) {
    otherError.value = 'Enter a username and a password.'
    return
  }
  pending.value = true
  try {
    await auth.signIn(username.value.trim(), password.value)
    rememberUsername(username.value.trim())
    await router.replace(safeNext(route.query.next))
  } catch (cause) {
    password.value = ''
    if (cause instanceof ApiError && cause.isOffline) {
      reachable.value = false
      healthTimer = setTimeout(checkHealth, HEALTH_RETRY_MS)
    } else if (cause instanceof ApiError && cause.status === 429) {
      startPause(cause.retryAfter ?? 300)
    } else if (cause instanceof ApiError && cause.status === 401) {
      credentialsError.value = true
    } else {
      otherError.value =
        cause instanceof ApiError
          ? `Sign-in failed (${cause.status}). Try again.`
          : 'Sign-in failed. Try again.'
    }
  } finally {
    pending.value = false
  }
  passwordInput.value?.focus()
}

const FIELD =
  'h-12 w-full rounded-lg border bg-surface px-[14px] text-[15px] text-ink outline-none transition ' +
  'placeholder:text-muted-soft hover:border-primary/60 focus:ring-4 disabled:cursor-not-allowed disabled:opacity-50'
const FIELD_OK = 'border-hairline focus:border-primary focus:ring-primary/20'
const FIELD_BAD = 'border-status-fault/60 focus:border-status-fault focus:ring-status-fault/15'
</script>

<template>
  <div class="min-h-full bg-canvas text-ink">
    <div class="grid min-h-screen lg:grid-cols-[minmax(26rem,1fr)_1.2fr]">
      <main class="flex flex-col px-lg py-lg sm:px-xl lg:pt-xl">
        <div class="flex items-center justify-between gap-sm">
          <div class="flex items-center gap-sm">
            <span
              class="flex h-9 w-9 items-center justify-center rounded-lg border border-hairline bg-surface text-[13px] font-semibold tracking-tighter"
            >
              AC
            </span>
            <span class="text-[15px] font-semibold tracking-tight">AMR Control</span>
          </div>

          <span
            v-if="reachable !== null"
            :class="
              cn(
                'inline-flex items-center gap-xs rounded-full border px-[10px] py-[3px] text-[12px]',
                offline
                  ? 'border-status-fault/30 bg-status-fault/[0.06] text-status-fault'
                  : 'border-status-ok/30 bg-status-ok/[0.06] text-status-ok',
              )
            "
          >
            <span class="relative flex h-1.5 w-1.5">
              <span
                v-if="!offline"
                class="absolute inline-flex h-full w-full rounded-full bg-status-ok opacity-60 motion-safe:animate-ping"
              />
              <span
                :class="
                  cn(
                    'relative inline-flex h-1.5 w-1.5 rounded-full',
                    offline ? 'bg-status-fault' : 'bg-status-ok',
                  )
                "
              />
            </span>
            {{ offline ? 'Server unreachable' : 'Server reachable' }}
          </span>
        </div>

        <!-- Centred while the photo is hidden (below lg), so a tablet is not half empty. -->
        <div class="mx-auto my-auto w-full max-w-[24rem] py-xl lg:mx-0">
          <h1 class="text-[32px] font-semibold leading-tight tracking-tight">
            Sign in to the control room
          </h1>
          <p class="mt-xs text-[14px] leading-relaxed text-body">
            Operators run missions and drive robots. Admins also edit maps, zones and people.
          </p>

          <div
            v-if="notice"
            :class="
              cn(
                'mt-lg flex items-start gap-sm rounded-xl border px-base py-sm',
                NOTICE_TONE[notice.tone],
              )
            "
            :role="notice.tone === 'blue' ? 'status' : 'alert'"
          >
            <component :is="notice.icon" :size="16" class="mt-[2px] shrink-0" />
            <div>
              <p class="text-[13px] font-medium">{{ notice.title }}</p>
              <p v-if="notice.body" class="mt-[2px] text-[13px] opacity-80">{{ notice.body }}</p>
            </div>
          </div>

          <form class="mt-lg space-y-base" novalidate @submit.prevent="onSubmit">
            <div>
              <label for="login-username" class="text-[13px] font-medium text-ink">
                Username
              </label>
              <input
                id="login-username"
                ref="usernameInput"
                v-model="username"
                :class="cn(FIELD, FIELD_OK, 'mt-[6px]')"
                autocomplete="username"
                autocapitalize="none"
                spellcheck="false"
                :disabled="locked"
              />
            </div>

            <div>
              <label for="login-password" class="text-[13px] font-medium text-ink">
                Password
              </label>
              <div class="relative mt-[6px]">
                <input
                  id="login-password"
                  ref="passwordInput"
                  v-model="password"
                  :type="showPassword ? 'text' : 'password'"
                  :class="cn(FIELD, credentialsError ? FIELD_BAD : FIELD_OK, 'pr-[4.5rem]')"
                  autocomplete="current-password"
                  :aria-invalid="credentialsError || undefined"
                  :aria-describedby="credentialsError ? 'login-credentials-error' : undefined"
                  :disabled="locked || paused"
                  @keydown="trackCapsLock"
                  @keyup="trackCapsLock"
                  @input="credentialsError = false"
                />
                <!-- A word, not only an eye: NN/g found a labelled control is
                     understood where a bare glyph is guessed at. -->
                <button
                  type="button"
                  :aria-pressed="showPassword"
                  class="absolute right-[6px] top-1/2 -translate-y-1/2 rounded-md px-[10px] py-[4px] text-[12px] font-medium text-primary transition hover:bg-surface-strong focus:outline-none focus-visible:ring-2 focus-visible:ring-primary/40"
                  @click="showPassword = !showPassword"
                >
                  {{ showPassword ? 'Hide' : 'Show' }}
                </button>
              </div>
              <p
                v-if="credentialsError"
                id="login-credentials-error"
                class="mt-xs flex items-center gap-[6px] text-[12px] text-status-fault"
                role="alert"
              >
                <CircleAlert :size="14" />Wrong username or password
              </p>
              <p v-else-if="capsLock" class="mt-xs text-[12px] text-status-warn">Caps Lock is on.</p>
            </div>

            <p v-if="otherError" class="text-[13px] text-status-fault" role="alert">{{ otherError }}</p>

            <button
              type="submit"
              :disabled="locked || paused"
              class="flex h-12 w-full items-center justify-center gap-xs rounded-full bg-primary text-[15px] font-medium text-on-primary transition hover:bg-primary-active focus:outline-none focus-visible:ring-4 focus-visible:ring-primary/30 disabled:cursor-not-allowed disabled:bg-surface-strong disabled:text-muted-soft"
            >
              <template v-if="pending">
                <LoaderCircle :size="16" class="motion-safe:animate-spin" />Signing in…
              </template>
              <template v-else-if="paused">
                <Lock :size="16" />Try again in {{ countdown(pausedFor) }}
              </template>
              <template v-else>Sign in</template>
            </button>
          </form>

          <p class="mt-lg text-[13px] text-muted">
            No account, or forgot your password? Ask an admin.
          </p>
        </div>

        <p class="text-center text-[12px] text-muted lg:text-left">
          Signing in to <span class="font-ident text-body">{{ host }}</span>
        </p>
      </main>

      <!-- The floor: site, time, and how to stop a robot without signing in. -->
      <aside class="relative hidden overflow-hidden border-l border-hairline bg-[#08090b] text-white lg:block">
        <img
          :src="floorPhoto"
          alt=""
          class="absolute inset-0 h-full w-full object-cover opacity-55"
        />
        <div
          class="absolute inset-0 bg-gradient-to-t from-[#08090b] via-[#08090b]/30 to-[#08090b]/20"
        />
        <div class="absolute inset-0 bg-gradient-to-r from-[#08090b]/70 to-transparent" />

        <div class="absolute inset-x-12 bottom-12 max-w-xl">
          <p v-if="site" class="text-[13px] text-white/50">{{ site }}</p>
          <p class="mt-xxs text-[56px] font-semibold leading-none tracking-tight tabular-nums">
            {{ time }}
          </p>
          <p class="mt-xs text-[14px] text-white/55">{{ date }}</p>
          <div
            class="mt-xl flex items-start gap-sm rounded-xl border border-white/10 bg-black/40 p-base backdrop-blur-md"
          >
            <OctagonX :size="20" class="mt-[2px] shrink-0 text-red-400" />
            <p class="text-[13px] leading-relaxed text-white/70">
              Need to stop a robot right now? Press the red emergency button on the robot. You
              don’t need to sign in for that.
            </p>
          </div>
        </div>
      </aside>
    </div>
  </div>
</template>
