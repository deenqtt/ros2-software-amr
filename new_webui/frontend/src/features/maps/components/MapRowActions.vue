<script setup lang="ts">
/**
 * The overflow menu for one map version: rename, edit cells, download, remove.
 *
 * Shared by the table (tablet and up) and the list (phone), so the two cannot
 * drift into offering different things for the same map. The table keeps
 * Assign as its own button beside the robots column; the phone row has no room
 * for it, so there it leads the menu instead.
 */
import { Brush, Download, Pencil, Trash2, Users } from 'lucide-vue-next'
import { RowActions, RowActionItem, RowActionSeparator } from '@/shared/ui/menu'
import { mapsApi } from '@/shared/api/maps'
import { usePermission } from '@/shared/composables/usePermission'
import type { MapRecord } from '@/domain/types'

const props = withDefaults(
  defineProps<{ map: MapRecord; withAssign?: boolean; label?: string }>(),
  { withAssign: false, label: undefined },
)
const emit = defineEmits<{ assign: []; rename: []; remove: [] }>()

const { canEdit, editBlocker } = usePermission()
</script>

<template>
  <RowActions :label="props.label ?? `More actions for ${props.map.name} v${props.map.version}`">
    <RowActionItem
      v-if="props.withAssign"
      :icon="Users"
      :disabled="!canEdit"
      :title="editBlocker || undefined"
      @select="emit('assign')"
    >
      Assign to robots
    </RowActionItem>
    <RowActionItem
      :icon="Pencil"
      :disabled="!canEdit"
      :title="editBlocker || undefined"
      @select="emit('rename')"
    >
      Rename
    </RowActionItem>
    <!-- No link at all when disabled: a disabled menu item still
         lets a click through to the anchor inside it. -->
    <RowActionItem
      :icon="Brush"
      :to="canEdit ? `/maps/edit/${props.map.id}` : undefined"
      :disabled="!canEdit"
      :title="editBlocker || undefined"
    >
      Edit cells
    </RowActionItem>
    <RowActionItem :icon="Download" :href="mapsApi.archiveUrl(props.map.id)" download>
      Download
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
