<script setup lang="ts">
/**
 * Replace a password someone else chose.
 *
 * Shown straight after signing in with one — the bootstrap account from .env,
 * a new account, an admin reset — and nothing else opens until it is done (the
 * route guard sends every other page here, and the server refuses everything
 * but this). Same layout as the sign-in page, so it reads as the second half
 * of signing in rather than as a page of the app. In the app's theme, like it.
 *
 * It asks for the temporary password again: the server needs it, and it proves
 * the person at the screen is the one who just signed in.
 */
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { CircleAlert, KeyRound, LoaderCircle, LogOut } from 'lucide-vue-next'
import { useAuthStore } from '@/stores/auth'
import { safeNext } from '@/app/router'
import { authApi, FieldError } from '@/shared/api/auth'
import { displayName, ROLE_LABEL } from '@/domain/auth'
import { cn } from '@/shared/lib/utils'

const PASSWORD_MIN = 10

const auth = useAuthStore()
const route = useRoute()
const router = useRouter()

const current = ref('')
const next = ref('')
const repeat = ref('')
const show = ref(false)
const attempted = ref(false)
const pending = ref(false)
const serverError = ref<{ field: string | null; message: string } | null>(null)
const currentInput = ref<HTMLInputElement | null>(null)

onMounted(() => currentInput.value?.focus())

const errors = computed(() => ({
  current_password: current.value ? '' : 'Enter the password you just signed in with.',
  new_password:
    next.value.length < PASSWORD_MIN
      ? `At least ${PASSWORD_MIN} characters.`
      : next.value === current.value
        ? 'Choose a password different from the temporary one.'
        : '',
  repeat: repeat.value === next.value ? '' : 'The two new passwords do not match.',
}))

function errorFor(field: 'current_password' | 'new_password' | 'repeat'): string {
  if (serverError.value?.field === field) return serverError.value.message
  return attempted.value ? errors.value[field] : ''
}

async function onSubmit(): Promise<void> {
  attempted.value = true
  serverError.value = null
  if (Object.values(errors.value).some(Boolean)) return
  pending.value = true
  try {
    await authApi.changePassword(current.value, next.value)
    auth.passwordChanged()
    await router.replace(safeNext(route.query.next))
  } catch (error) {
    serverError.value =
      error instanceof FieldError
        ? { field: error.field, message: error.message }
        : { field: null, message: error instanceof Error ? error.message : 'Could not save it.' }
  } finally {
    pending.value = false
  }
}

const FIELD =
  'h-12 w-full rounded-lg border bg-surface px-[14px] text-[15px] text-ink outline-none transition ' +
  'hover:border-primary/60 focus:ring-4 disabled:opacity-50'
const fieldTone = (bad: boolean) =>
  bad
    ? 'border-status-fault/60 focus:border-status-fault focus:ring-status-fault/15'
    : 'border-hairline focus:border-primary focus:ring-primary/20'
</script>

<template>
  <div class="flex min-h-full flex-col bg-canvas px-lg py-lg text-ink sm:px-xl">
    <div class="flex items-center justify-between gap-sm">
      <div class="flex items-center gap-sm">
        <span
          class="flex h-9 w-9 items-center justify-center rounded-lg border border-hairline bg-surface text-[13px] font-semibold tracking-tighter"
        >
          AC
        </span>
        <span class="text-[15px] font-semibold tracking-tight">AMR Control</span>
      </div>
      <button
        type="button"
        class="inline-flex items-center gap-xs rounded-full px-sm py-xs text-[13px] text-body transition hover:bg-surface-strong hover:text-ink"
        @click="auth.signOut()"
      >
        <LogOut :size="14" /> Sign out
      </button>
    </div>

    <main class="mx-auto my-auto w-full max-w-[24rem] py-xl">
      <span
        class="flex h-11 w-11 items-center justify-center rounded-xl border border-hairline bg-surface text-primary"
      >
        <KeyRound :size="20" />
      </span>
      <h1 class="mt-base text-[28px] font-semibold leading-tight tracking-tight">
        Set your own password
      </h1>
      <p class="mt-xs text-[14px] leading-relaxed text-body">
        <template v-if="auth.user">
          {{ displayName(auth.user) }}, you signed in as {{ ROLE_LABEL[auth.user.role] }} with a
          password someone else set.
        </template>
        Choose one only you know before you continue.
      </p>

      <form class="mt-lg space-y-base" novalidate @submit.prevent="onSubmit">
        <div>
          <label for="sp-current" class="text-[13px] font-medium text-ink">
            Temporary password
          </label>
          <input
            id="sp-current"
            ref="currentInput"
            v-model="current"
            :type="show ? 'text' : 'password'"
            autocomplete="current-password"
            :class="cn(FIELD, fieldTone(Boolean(errorFor('current_password'))), 'mt-[6px]')"
            :disabled="pending"
          />
          <p v-if="errorFor('current_password')" class="mt-xs text-[12px] text-status-fault">
            {{ errorFor('current_password') }}
          </p>
        </div>

        <div>
          <div class="flex items-center justify-between">
            <label for="sp-new" class="text-[13px] font-medium text-ink">New password</label>
            <button
              type="button"
              :aria-pressed="show"
              class="rounded-md px-xs py-[2px] text-[12px] font-medium text-primary transition hover:bg-surface-strong"
              @click="show = !show"
            >
              {{ show ? 'Hide' : 'Show' }}
            </button>
          </div>
          <input
            id="sp-new"
            v-model="next"
            :type="show ? 'text' : 'password'"
            autocomplete="new-password"
            :class="cn(FIELD, fieldTone(Boolean(errorFor('new_password'))), 'mt-[6px]')"
            :disabled="pending"
          />
          <p
            :class="
              cn('mt-xs text-[12px]', errorFor('new_password') ? 'text-status-fault' : 'text-muted')
            "
          >
            {{
              errorFor('new_password') ||
              `At least ${PASSWORD_MIN} characters. A short sentence is easy to type and hard to guess.`
            }}
          </p>
        </div>

        <div>
          <label for="sp-repeat" class="text-[13px] font-medium text-ink">
            New password, again
          </label>
          <input
            id="sp-repeat"
            v-model="repeat"
            :type="show ? 'text' : 'password'"
            autocomplete="new-password"
            :class="cn(FIELD, fieldTone(Boolean(errorFor('repeat'))), 'mt-[6px]')"
            :disabled="pending"
          />
          <p v-if="errorFor('repeat')" class="mt-xs text-[12px] text-status-fault">
            {{ errorFor('repeat') }}
          </p>
        </div>

        <p
          v-if="serverError && serverError.field === null"
          class="flex items-center gap-[6px] text-[13px] text-status-fault"
          role="alert"
        >
          <CircleAlert :size="14" />{{ serverError.message }}
        </p>

        <button
          type="submit"
          :disabled="pending"
          class="flex h-12 w-full items-center justify-center gap-xs rounded-full bg-primary text-[15px] font-medium text-on-primary transition hover:bg-primary-active focus:outline-none focus-visible:ring-4 focus-visible:ring-primary/30 disabled:cursor-not-allowed disabled:bg-surface-strong disabled:text-muted-soft"
        >
          <template v-if="pending">
            <LoaderCircle :size="16" class="motion-safe:animate-spin" />Saving…
          </template>
          <template v-else>Save and continue</template>
        </button>
      </form>
    </main>
  </div>
</template>
