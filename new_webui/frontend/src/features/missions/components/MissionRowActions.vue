<script setup lang="ts">
/**
 * The overflow menu for one mission: open it, remove it.
 *
 * Shared by the table and the phone list so the two cannot drift into
 * offering different things for the same route.
 */
import { Eye, Pencil, Trash2 } from 'lucide-vue-next'
import { RowActions, RowActionItem } from '@/shared/ui/menu'
import { usePermission } from '@/shared/composables/usePermission'
import type { MissionSummary } from '@/domain/types'

const props = defineProps<{
  mission: MissionSummary
  /**
   * Classes for the Edit/View item. The table passes `lg:hidden`: on a
   * desktop the row already has its own Edit button, below that it does not.
   */
  openClass?: string
}>()
const emit = defineEmits<{ remove: [] }>()

const { canEdit, editBlocker } = usePermission()
</script>

<template>
  <RowActions :label="`More actions for ${props.mission.name}`">
    <!-- The editor opens read-only without the admin role, so it is still
         offered, as what it then is. -->
    <RowActionItem
      :icon="canEdit ? Pencil : Eye"
      :to="`/mission/edit/${props.mission.id}`"
      :class="props.openClass"
    >
      {{ canEdit ? 'Edit' : 'View' }}
    </RowActionItem>
    <RowActionItem
      :icon="Trash2"
      destructive
      :disabled="!canEdit"
      :title="editBlocker || undefined"
      @select="emit('remove')"
    >
      Remove
    </RowActionItem>
  </RowActions>
</template>
