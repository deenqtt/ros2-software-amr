<script setup lang="ts">
/**
 * The overflow menu for one account: edit, reset password, disable, delete.
 *
 * Shared by the table (tablet and up) and the list (phone), so the two cannot
 * drift into offering different things for the same person. Your own account
 * cannot be switched off or removed from here: that would lock you out with
 * nobody left to undo it.
 */
import { KeyRound, Pencil, Trash2, UserCheck, UserX } from 'lucide-vue-next'
import { RowActionItem, RowActions, RowActionSeparator } from '@/shared/ui/menu'
import type { UserAccount } from '@/shared/api/auth'

const props = defineProps<{ user: UserAccount; self: boolean }>()
const emit = defineEmits<{ edit: []; password: []; toggle: []; remove: [] }>()
</script>

<template>
  <RowActions :label="`Actions for ${props.user.username}`">
    <RowActionItem :icon="Pencil" @select="emit('edit')">Edit</RowActionItem>
    <RowActionItem :icon="KeyRound" @select="emit('password')">Reset password</RowActionItem>
    <RowActionItem
      :icon="props.user.disabled ? UserCheck : UserX"
      :disabled="props.self"
      :title="props.self ? 'You cannot disable your own account' : undefined"
      @select="emit('toggle')"
    >
      {{ props.user.disabled ? 'Enable' : 'Disable' }}
    </RowActionItem>
    <RowActionSeparator class="my-xxs h-px bg-hairline" />
    <RowActionItem
      :icon="Trash2"
      destructive
      :disabled="props.self"
      :title="props.self ? 'You cannot delete your own account' : undefined"
      @select="emit('remove')"
    >
      Delete
    </RowActionItem>
  </RowActions>
</template>
