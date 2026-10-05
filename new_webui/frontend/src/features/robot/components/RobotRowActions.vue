<script setup lang="ts">
/**
 * The overflow menu for one robot: monitoring, edit, remove.
 *
 * Shared by the table (tablet and up) and the list (phone), so the two cannot
 * drift into offering different things for the same robot.
 */
import { Bell, BellOff, Pencil, Trash2 } from 'lucide-vue-next'
import { RowActions, RowActionItem, RowActionSeparator } from '@/shared/ui/menu'
import { useLinkStore } from '@/stores/links'
import { usePermission } from '@/shared/composables/usePermission'
import type { RobotConfig } from '@/domain/types'

const props = defineProps<{ robot: RobotConfig }>()
const emit = defineEmits<{ edit: []; remove: [] }>()

const links = useLinkStore()
const { canEdit, editBlocker } = usePermission()
</script>

<template>
  <RowActions :label="`More actions for ${props.robot.name}`">
    <!--
      Labelled by what it will do, not by what is true now. The current state
      is already on the row: the link reads "Muted", so this menu does not
      have to carry it as well.
    -->
    <RowActionItem
      :icon="links.isMuted(props.robot.id) ? Bell : BellOff"
      @select="links.setMuted(props.robot.id, !links.isMuted(props.robot.id))"
    >
      {{ links.isMuted(props.robot.id) ? 'Resume monitoring' : 'Stop monitoring' }}
    </RowActionItem>
    <RowActionItem
      :icon="Pencil"
      :disabled="!canEdit"
      :title="editBlocker || undefined"
      @select="emit('edit')"
    >
      Edit
    </RowActionItem>
    <RowActionSeparator class="my-xxs h-px bg-hairline" />
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
