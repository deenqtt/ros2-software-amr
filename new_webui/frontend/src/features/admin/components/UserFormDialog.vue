<script setup lang="ts">
/**
 * Add an account, edit one, or reset its password.
 *
 * One dialog for the three, because they share fields and rules. Editing does
 * not show the password: an admin changes who someone is and what they may do,
 * and resetting a password is a separate, deliberate act that signs the person
 * out everywhere.
 */
import { computed, ref, watch } from 'vue'
import { Dialog } from '@/shared/ui/dialog'
import { Input } from '@/shared/ui/input'
import { FormField } from '@/shared/ui/label'
import { Button } from '@/shared/ui/button'
import { ROLE_LABEL, ROLE_SUMMARY, ROLES, type Role } from '@/domain/auth'
import type { UserAccount } from '@/shared/api/auth'
import { cn } from '@/shared/lib/utils'

export type UserFormMode = 'add' | 'edit' | 'password'

export interface UserFormValues {
  username: string
  displayName: string
  role: Role
  password: string
}

const PASSWORD_MIN = 10
const USERNAME = /^[A-Za-z0-9._-]{3,32}$/

const props = withDefaults(
  defineProps<{
    open: boolean
    mode: UserFormMode
    user?: UserAccount | null
    /** True when editing yourself: your own role is not yours to change. */
    self?: boolean
    pending?: boolean
    serverError?: { field: string | null; message: string } | null
    /** Already formatted. The phone list has no column for it, so it lives here. */
    lastSignIn?: string
  }>(),
  { user: null, self: false, pending: false, serverError: null },
)

const emit = defineEmits<{
  'update:open': [value: boolean]
  submit: [values: UserFormValues]
}>()

const values = ref<UserFormValues>({ username: '', displayName: '', role: 'operator', password: '' })
const attempted = ref(false)

watch(
  () => [props.open, props.user, props.mode] as const,
  ([open, user]) => {
    if (!open) return
    values.value = {
      username: user?.username ?? '',
      displayName: user?.displayName ?? '',
      // Operator by default: most new accounts are for people running the floor.
      role: user?.role ?? 'operator',
      password: '',
    }
    attempted.value = false
  },
  { immediate: true },
)

const title = computed(() => {
  if (props.mode === 'add') return 'Add user'
  const name = props.user?.displayName || props.user?.username
  return props.mode === 'password' ? `Reset password for ${name}` : `Edit ${name}`
})

const description = computed(() => {
  if (props.mode === 'add') {
    return 'Give them this username and a temporary password. They choose their own the first time they sign in.'
  }
  if (props.mode === 'password') {
    return props.self
      ? 'Your other browsers will be signed out.'
      : 'They are signed out everywhere, sign in with this temporary password, and then choose their own. Tell it to them in person.'
  }
  return 'Changes apply the next time they load a page.'
})

const errors = computed(() => ({
  username:
    props.mode === 'add' && !USERNAME.test(values.value.username.trim())
      ? 'Use 3 to 32 letters, digits, dots, dashes or underscores, with no spaces.'
      : '',
  displayName: values.value.displayName.length > 64 ? 'At most 64 characters.' : '',
  password:
    props.mode !== 'edit' && values.value.password.length < PASSWORD_MIN
      ? `At least ${PASSWORD_MIN} characters.`
      : '',
}))

function errorFor(field: 'username' | 'displayName' | 'password'): string | undefined {
  const serverField = field === 'displayName' ? 'display_name' : field
  if (props.serverError?.field === serverField) return props.serverError.message
  if (!attempted.value) return undefined
  return errors.value[field] || undefined
}

const generalError = computed(() => {
  const error = props.serverError
  if (!error) return null
  return error.field && ['username', 'display_name', 'password'].includes(error.field)
    ? null
    : error.message
})

function onSubmit(): void {
  attempted.value = true
  if (Object.values(errors.value).some(Boolean)) return
  emit('submit', { ...values.value, username: values.value.username.trim() })
}
</script>

<template>
  <Dialog
    :open="props.open"
    :pending="props.pending"
    :title="title"
    :description="description"
    @update:open="emit('update:open', $event)"
  >
    <form id="user-form" class="space-y-base" novalidate @submit.prevent="onSubmit">
      <p v-if="props.mode === 'edit' && props.lastSignIn" class="text-caption text-muted">
        Last sign-in: <span class="font-data">{{ props.lastSignIn }}</span>
      </p>
      <template v-if="props.mode !== 'password'">
        <FormField
          v-if="props.mode === 'add'"
          label="Username"
          required
          hint="What they type to sign in. It cannot be changed later."
          :error="errorFor('username')"
        >
          <template #default="{ id, invalid }">
            <Input
              :id="id"
              v-model="values.username"
              mono
              :invalid="invalid"
              placeholder="budi.s"
              autocomplete="off"
              autocapitalize="none"
              spellcheck="false"
            />
          </template>
        </FormField>

        <FormField
          label="Full name"
          hint="Shown in the header and the activity log."
          :error="errorFor('displayName')"
        >
          <template #default="{ id, invalid }">
            <Input
              :id="id"
              v-model="values.displayName"
              :invalid="invalid"
              placeholder="Budi Santoso"
              autocomplete="off"
            />
          </template>
        </FormField>

        <fieldset class="space-y-xxs">
          <legend class="text-label uppercase text-muted">Role</legend>
          <p v-if="props.self" class="text-caption text-muted">
            You cannot change your own role. Ask another admin.
          </p>
          <div class="space-y-xxs" role="radiogroup" aria-label="Role">
            <label
              v-for="role in ROLES"
              :key="role"
              :class="
                cn(
                  'flex cursor-pointer items-start gap-sm rounded-control border px-sm py-xs transition-colors',
                  values.role === role
                    ? 'border-primary bg-primary/5'
                    : 'border-hairline hover:border-primary/50',
                  props.self && 'cursor-not-allowed opacity-60',
                )
              "
            >
              <input
                v-model="values.role"
                type="radio"
                name="role"
                :value="role"
                :disabled="props.self"
                class="mt-[3px] accent-[rgb(var(--primary))]"
              />
              <span class="min-w-0">
                <span class="block text-body-sm font-medium text-ink">{{ ROLE_LABEL[role] }}</span>
                <span class="block text-caption text-muted">{{ ROLE_SUMMARY[role] }}</span>
              </span>
            </label>
          </div>
        </fieldset>
      </template>

      <FormField
        v-if="props.mode !== 'edit'"
        :label="props.self ? 'New password' : 'Temporary password'"
        required
        :hint="
          props.self
            ? `At least ${PASSWORD_MIN} characters.`
            : `At least ${PASSWORD_MIN} characters. It only works until they set their own.`
        "
        :error="errorFor('password')"
      >
        <template #default="{ id, invalid }">
          <Input
            :id="id"
            v-model="values.password"
            type="password"
            autocomplete="new-password"
            :invalid="invalid"
          />
        </template>
      </FormField>

      <p v-if="generalError" class="text-body-sm text-status-fault" role="alert">
        {{ generalError }}
      </p>
    </form>

    <template #footer>
      <Button variant="outline" :disabled="props.pending" @click="emit('update:open', false)">
        Cancel
      </Button>
      <Button type="submit" form="user-form" :disabled="props.pending">
        {{
          props.pending
            ? 'Saving…'
            : props.mode === 'add'
              ? 'Add user'
              : props.mode === 'password'
                ? 'Reset password'
                : 'Save'
        }}
      </Button>
    </template>
  </Dialog>
</template>
