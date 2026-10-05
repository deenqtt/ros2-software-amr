<script setup lang="ts">
/**
 * One zone as a row: the docked list, the phone list and the phone's bottom
 * card all use it, so a zone reads the same wherever it is tapped.
 */
import { Pencil, Trash2 } from 'lucide-vue-next'
import { polygonArea, type Zone } from '@/domain/types'
import { ZONE_KIND_STYLE, zoneSetting } from '../zoneKind'
import { RowActions, RowActionItem, RowActionSeparator } from '@/shared/ui/menu'
import { usePermission } from '@/shared/composables/usePermission'
import { cn } from '@/shared/lib/utils'

const props = defineProps<{
  zone: Zone
  /** Outlined as the one selected on the map. */
  selected?: boolean
  /** Also shows the note. */
  detail?: boolean
  /** Its switch is in flight, so a double tap is not two requests. */
  toggling?: boolean
}>()

const emit = defineEmits<{ select: []; toggle: []; edit: []; remove: [] }>()

const { canEdit, editBlocker } = usePermission()
</script>

<template>
  <div
    :class="
      cn(
        'flex items-start gap-xs rounded-control border p-xs transition-colors',
        props.selected
          ? 'border-primary bg-primary/[0.06]'
          : 'border-transparent hover:border-hairline',
        !props.zone.enabled && 'opacity-60',
      )
    "
  >
    <button
      type="button"
      class="flex min-w-0 flex-1 items-start gap-xs text-left"
      @click="emit('select')"
    >
      <span
        class="mt-px flex h-6 w-6 shrink-0 items-center justify-center rounded-control text-white"
        :style="{ backgroundColor: ZONE_KIND_STYLE[props.zone.kind].colour }"
      >
        <component :is="ZONE_KIND_STYLE[props.zone.kind].icon" :size="13" />
      </span>
      <span class="min-w-0 flex-1">
        <span class="block truncate text-body-sm text-ink">{{ props.zone.name }}</span>
        <span class="block font-data text-caption text-muted">
          {{ ZONE_KIND_STYLE[props.zone.kind].label
          }}<template v-if="zoneSetting(props.zone)"> · {{ zoneSetting(props.zone) }}</template> ·
          {{ polygonArea(props.zone.polygon).toFixed(1) }} m²
        </span>
        <!-- A zone that exists but is switched off is not the same as
             one that is not there, and the list has to say which. -->
        <span v-if="!props.zone.enabled" class="block text-caption text-status-warn">
          Switched off — robots ignore it
        </span>
        <span
          v-else-if="props.detail && props.zone.note"
          class="mt-xxs block text-caption text-muted-soft"
        >
          {{ props.zone.note }}
        </span>
      </span>
    </button>

    <!--
      On/off in the row, not the menu: switching a zone off for a shift and
      back on is the most common thing done to one. The track is drawn inside
      so the button can be a finger-sized target on touch without looking
      bigger.
    -->
    <button
      type="button"
      role="switch"
      :aria-checked="props.zone.enabled"
      :aria-label="`${props.zone.name} active`"
      :title="
        editBlocker ||
        (props.zone.enabled ? `Switch ${props.zone.name} off` : `Switch ${props.zone.name} on`)
      "
      :disabled="!canEdit || props.toggling"
      class="mt-[3px] flex h-5 w-9 shrink-0 items-center justify-center transition-opacity disabled:cursor-not-allowed disabled:opacity-50 touch:mt-0 touch:h-11 touch:w-14"
      @click="emit('toggle')"
    >
      <span
        class="flex h-5 w-9 items-center rounded-full p-[2px] transition-colors"
        :class="props.zone.enabled ? 'bg-primary' : 'bg-hairline'"
      >
        <span
          class="h-4 w-4 rounded-full bg-white shadow-soft transition-transform"
          :class="props.zone.enabled ? 'translate-x-4' : 'translate-x-0'"
        />
      </span>
    </button>

    <RowActions :label="`More actions for ${props.zone.name}`">
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
  </div>
</template>
