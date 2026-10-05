<script setup lang="ts">
/**
 * Who can sign in, and what they may do. Super admins only.
 *
 * Disable is offered before delete. When someone leaves, their account is
 * switched off rather than removed: nobody can sign in as them, and their name
 * stays readable on everything the activity log says they did.
 */
import { computed, onMounted, ref } from 'vue'
import { toast } from 'vue-sonner'
import { Plus, RefreshCw, Users } from 'lucide-vue-next'
import { usersApi, FieldError, type UserAccount } from '@/shared/api/auth'
import { useAuthStore } from '@/stores/auth'
import { ROLE_LABEL, initials } from '@/domain/auth'
import { Button } from '@/shared/ui/button'
import { Card } from '@/shared/ui/card'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/shared/ui/table'
import PanelToolbar from '@/shared/components/PanelToolbar.vue'
import StatusBadge from '@/shared/components/StatusBadge.vue'
import EmptyState from '@/shared/components/EmptyState.vue'
import ConfirmDialog from '@/shared/components/ConfirmDialog.vue'
import type { StatusTone } from '@/domain/types'
import UserRowActions from '../components/UserRowActions.vue'
import UserFormDialog, { type UserFormMode, type UserFormValues } from '../components/UserFormDialog.vue'
import { auditDate } from '../auditLabel'

const auth = useAuthStore()

const users = ref<UserAccount[]>([])
const loading = ref(false)
const error = ref<string | null>(null)

// A role is not a status, so no warning or fault hues: blue for the two that
// change things beyond the robots, green for running them, grey for watching.
const ROLE_TONE: Record<UserAccount['role'], StatusTone> = {
  super_admin: 'active',
  admin: 'active',
  operator: 'success',
  viewer: 'neutral',
}

async function load(): Promise<void> {
  loading.value = true
  error.value = null
  try {
    users.value = await usersApi.list()
  } catch (cause) {
    error.value = cause instanceof Error ? cause.message : 'Could not load accounts.'
  } finally {
    loading.value = false
  }
}

onMounted(load)

const subtitle = computed(() => {
  const active = users.value.filter((user) => !user.disabled).length
  const off = users.value.length - active
  return off ? `${active} active · ${off} disabled` : `${active} active`
})

function isSelf(user: UserAccount): boolean {
  return user.id === auth.user?.id
}

function lastSignIn(user: UserAccount): string {
  if (!user.lastLoginAt) return 'Never'
  return auditDate(user.lastLoginAt).toLocaleString([], {
    dateStyle: 'medium',
    timeStyle: 'short',
  })
}

// ── Add / edit / reset ────────────────────────────────────────────────────────

const formOpen = ref(false)
const formMode = ref<UserFormMode>('add')
const formUser = ref<UserAccount | null>(null)
const formPending = ref(false)
const formError = ref<{ field: string | null; message: string } | null>(null)

function openForm(mode: UserFormMode, user: UserAccount | null = null): void {
  formMode.value = mode
  formUser.value = user
  formError.value = null
  formOpen.value = true
}

function replace(updated: UserAccount): void {
  users.value = users.value.map((user) => (user.id === updated.id ? updated : user))
}

async function onSubmit(values: UserFormValues): Promise<void> {
  formPending.value = true
  formError.value = null
  try {
    if (formMode.value === 'add') {
      const created = await usersApi.create({
        username: values.username,
        displayName: values.displayName.trim() || null,
        role: values.role,
        password: values.password,
      })
      users.value = [...users.value, created].sort((a, b) =>
        a.username.localeCompare(b.username, undefined, { sensitivity: 'base' }),
      )
      toast.success(`${created.username} can sign in, and will choose their own password first`)
    } else if (formMode.value === 'password' && formUser.value) {
      replace(await usersApi.update(formUser.value.id, { password: values.password }))
      toast.success(
        isSelf(formUser.value)
          ? 'Password changed'
          : `Password reset. ${formUser.value.username} is signed out and will choose a new one at next sign-in.`,
      )
    } else if (formUser.value) {
      const patch: Parameters<typeof usersApi.update>[1] = {
        displayName: values.displayName.trim() || null,
      }
      if (!isSelf(formUser.value)) patch.role = values.role
      replace(await usersApi.update(formUser.value.id, patch))
      toast.success('Saved')
    }
    formOpen.value = false
  } catch (cause) {
    formError.value =
      cause instanceof FieldError
        ? { field: cause.field, message: cause.message }
        : { field: null, message: cause instanceof Error ? cause.message : 'Could not save.' }
  } finally {
    formPending.value = false
  }
}

// ── Disable / enable / delete ─────────────────────────────────────────────────

const pendingToggle = ref<UserAccount | null>(null)
const pendingRemoval = ref<UserAccount | null>(null)
const confirmPending = ref(false)

async function setDisabled(user: UserAccount, disabled: boolean): Promise<void> {
  confirmPending.value = true
  try {
    replace(await usersApi.update(user.id, { disabled }))
    toast.success(disabled ? `${user.username} can no longer sign in` : `${user.username} can sign in again`)
    pendingToggle.value = null
  } catch (cause) {
    toast.error(cause instanceof Error ? cause.message : 'Could not change it.')
  } finally {
    confirmPending.value = false
  }
}

async function remove(user: UserAccount): Promise<void> {
  confirmPending.value = true
  try {
    await usersApi.remove(user.id)
    users.value = users.value.filter((other) => other.id !== user.id)
    toast.success(`${user.username} deleted`)
    pendingRemoval.value = null
  } catch (cause) {
    toast.error(cause instanceof Error ? cause.message : 'Could not delete it.')
  } finally {
    confirmPending.value = false
  }
}

function onToggle(user: UserAccount): void {
  // Enabling needs no confirmation; switching someone off mid-shift does.
  if (user.disabled) void setDisabled(user, false)
  else pendingToggle.value = user
}
</script>

<template>
  <div class="p-sm sm:p-base md:p-lg">
    <Card>
      <PanelToolbar title="Users" :subtitle="users.length ? subtitle : undefined">
        <template #icon><Users :size="14" class="shrink-0 text-muted" /></template>
        <template #actions>
          <Button variant="outline" size="icon" title="Reload" :disabled="loading" @click="load">
            <RefreshCw :size="15" :class="loading && 'animate-spin'" />
          </Button>
          <Button @click="openForm('add')">
            <Plus :size="15" />
            <span>Add user</span>
          </Button>
        </template>
      </PanelToolbar>

      <div v-if="error" class="p-base">
        <EmptyState title="Could not load accounts" :description="error">
          <template #action>
            <Button size="sm" variant="secondary" @click="load">Try again</Button>
          </template>
        </EmptyState>
      </div>

      <template v-else>
        <!--
          Phone: who, and their role. Status only when something is off —
          a green "Active" on every row is noise that hides the one that is not.
          The row opens the account; the menu holds the rest.
        -->
        <ul class="divide-y divide-hairline md:hidden">
          <li
            v-for="user in users"
            :key="user.id"
            class="flex items-center pr-xs"
            :class="user.disabled ? 'opacity-60' : undefined"
          >
            <button
              type="button"
              class="flex min-h-[56px] min-w-0 flex-1 items-center gap-sm py-xs pl-base pr-xs text-left transition-colors active:bg-surface-strong"
              @click="openForm('edit', user)"
            >
              <span
                class="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-primary/10 text-label text-primary"
                aria-hidden="true"
              >
                {{ initials(user) }}
              </span>
              <span class="min-w-0 flex-1">
                <span class="block truncate text-title-sm text-ink">
                  {{ user.displayName || user.username }}
                  <span v-if="isSelf(user)" class="text-caption font-normal text-muted">(you)</span>
                </span>
                <span class="block truncate text-caption text-muted">
                  <span class="font-ident">{{ user.username }}</span> · {{ ROLE_LABEL[user.role] }}
                </span>
              </span>
              <StatusBadge v-if="user.disabled" tone="neutral" label="Disabled" class="shrink-0" />
              <StatusBadge
                v-else-if="user.mustChangePassword"
                tone="warning"
                label="Temporary password"
                title="Has not yet replaced the password set for them"
                class="shrink-0"
              />
            </button>
            <UserRowActions
              :user="user"
              :self="isSelf(user)"
              @edit="openForm('edit', user)"
              @password="openForm('password', user)"
              @toggle="onToggle(user)"
              @remove="pendingRemoval = user"
            />
          </li>
        </ul>

        <div class="hidden md:block">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead class="w-full">Person</TableHead>
                <TableHead class="whitespace-nowrap">Role</TableHead>
                <TableHead class="whitespace-nowrap">Status</TableHead>
                <TableHead class="hidden whitespace-nowrap lg:table-cell">Last sign-in</TableHead>
                <TableHead align="right">Actions</TableHead>
              </TableRow>
            </TableHeader>

            <TableBody>
              <TableRow
                v-for="user in users"
                :key="user.id"
                :class="user.disabled ? 'opacity-60' : undefined"
              >
                <TableCell class="w-full">
                  <div class="flex items-center gap-sm">
                    <span
                      class="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-primary/10 text-label text-primary"
                      aria-hidden="true"
                    >
                      {{ initials(user) }}
                    </span>
                    <div class="min-w-0">
                      <p class="truncate text-title-sm text-ink">
                        {{ user.displayName || user.username }}
                        <span v-if="isSelf(user)" class="text-caption font-normal text-muted">(you)</span>
                      </p>
                      <p class="truncate font-ident text-caption text-muted">{{ user.username }}</p>
                    </div>
                  </div>
                </TableCell>
                <TableCell class="whitespace-nowrap">
                  <StatusBadge :tone="ROLE_TONE[user.role]" :label="ROLE_LABEL[user.role]" />
                </TableCell>
                <TableCell class="whitespace-nowrap">
                  <StatusBadge
                    :tone="user.disabled ? 'neutral' : user.mustChangePassword ? 'warning' : 'success'"
                    :label="
                      user.disabled ? 'Disabled' : user.mustChangePassword ? 'Temporary password' : 'Active'
                    "
                    :title="
                      !user.disabled && user.mustChangePassword
                        ? 'Has not yet replaced the password set for them'
                        : undefined
                    "
                  />
                </TableCell>
                <TableCell class="hidden whitespace-nowrap lg:table-cell">
                  <span class="font-data text-body-sm text-body">{{ lastSignIn(user) }}</span>
                </TableCell>
                <TableCell align="right">
                  <UserRowActions
                    :user="user"
                    :self="isSelf(user)"
                    @edit="openForm('edit', user)"
                    @password="openForm('password', user)"
                    @toggle="onToggle(user)"
                    @remove="pendingRemoval = user"
                  />
                </TableCell>
              </TableRow>
            </TableBody>
          </Table>
        </div>
      </template>
    </Card>

    <UserFormDialog
      v-model:open="formOpen"
      :mode="formMode"
      :user="formUser"
      :self="formUser ? isSelf(formUser) : false"
      :last-sign-in="formUser ? lastSignIn(formUser) : undefined"
      :pending="formPending"
      :server-error="formError"
      @submit="onSubmit"
    />

    <ConfirmDialog
      :open="pendingToggle !== null"
      destructive
      :pending="confirmPending"
      :title="`Disable ${pendingToggle?.username}?`"
      description="They are signed out everywhere and cannot sign in until enabled again. Their name stays on everything in the activity log."
      confirm-label="Disable"
      @update:open="(open: boolean) => !open && (pendingToggle = null)"
      @cancel="pendingToggle = null"
      @confirm="pendingToggle && setDisabled(pendingToggle, true)"
    />

    <ConfirmDialog
      :open="pendingRemoval !== null"
      destructive
      :pending="confirmPending"
      :title="`Delete ${pendingRemoval?.username}?`"
      description="The account is removed for good. Their past activity stays in the log under this name. To stop someone signing in but keep the account, disable it instead."
      confirm-label="Delete"
      @update:open="(open: boolean) => !open && (pendingRemoval = null)"
      @cancel="pendingRemoval = null"
      @confirm="pendingRemoval && remove(pendingRemoval)"
    />
  </div>
</template>
