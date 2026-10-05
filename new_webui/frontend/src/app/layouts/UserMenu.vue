<script setup lang="ts">
/**
 * Who is signed in, and the way out.
 *
 * The role is always on show, not tucked inside the menu: on a shared terminal
 * "why is Run greyed out?" is answered by glancing at the header, and a
 * supervisor can see at a distance whose session is open.
 */
import { ref } from 'vue'
import {
  DropdownMenuContent,
  DropdownMenuLabel,
  DropdownMenuPortal,
  DropdownMenuRoot,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from 'reka-ui'
import { ChevronDown, KeyRound, LogOut } from 'lucide-vue-next'
import { RowActionItem } from '@/shared/ui/menu'
import { useAuthStore } from '@/stores/auth'
import { displayName, initials, ROLE_LABEL } from '@/domain/auth'
import ChangePasswordDialog from './ChangePasswordDialog.vue'

const auth = useAuthStore()
const changingPassword = ref(false)
const signingOut = ref(false)

async function signOut(): Promise<void> {
  signingOut.value = true
  await auth.signOut()
}
</script>

<template>
  <template v-if="auth.user">
    <DropdownMenuRoot>
      <DropdownMenuTrigger
        :aria-label="`Account: ${displayName(auth.user)}, ${ROLE_LABEL[auth.user.role]}`"
        class="flex items-center gap-xs rounded-control px-xs py-xxs text-left transition-colors hover:bg-surface-strong focus:outline-none focus-visible:ring-2 focus-visible:ring-primary/40"
      >
        <span
          class="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-primary/10 text-label text-primary"
          aria-hidden="true"
        >
          {{ initials(auth.user) }}
        </span>
        <span class="hidden min-w-0 flex-col sm:flex">
          <span class="max-w-[10rem] truncate text-body-sm font-medium text-ink">
            {{ displayName(auth.user) }}
          </span>
          <span class="text-caption text-muted">{{ ROLE_LABEL[auth.user.role] }}</span>
        </span>
        <ChevronDown :size="14" class="text-muted" />
      </DropdownMenuTrigger>

      <DropdownMenuPortal>
        <DropdownMenuContent
          align="end"
          :side-offset="6"
          class="z-50 min-w-[14rem] overflow-hidden rounded-surface border border-hairline bg-surface p-xxs shadow-soft"
        >
          <DropdownMenuLabel class="px-sm py-xs">
            <p class="truncate text-body-sm font-medium text-ink">{{ displayName(auth.user) }}</p>
            <p class="truncate text-caption text-muted">
              {{ auth.user.username }} · {{ ROLE_LABEL[auth.user.role] }}
            </p>
          </DropdownMenuLabel>
          <DropdownMenuSeparator class="my-xxs h-px bg-hairline" />
          <RowActionItem :icon="KeyRound" @select="changingPassword = true">
            Change password
          </RowActionItem>
          <RowActionItem :icon="LogOut" :disabled="signingOut" @select="signOut">
            Sign out
          </RowActionItem>
        </DropdownMenuContent>
      </DropdownMenuPortal>
    </DropdownMenuRoot>

    <ChangePasswordDialog v-model:open="changingPassword" />
  </template>
</template>
