<script setup lang="ts">
/**
 * One station as a row: the docked list, the phone list and the phone's
 * bottom card all use it, so a station reads the same wherever it is tapped.
 */
import { Pencil, Trash2 } from 'lucide-vue-next'
import { radToDeg } from '@/domain/ros/quaternion'
import type { Station } from '@/domain/types'
import { STATION_TYPE_STYLE } from '../stationType'
import { RowActions, RowActionItem, RowActionSeparator } from '@/shared/ui/menu'
import { usePermission } from '@/shared/composables/usePermission'
import { cn } from '@/shared/lib/utils'

const props = defineProps<{
  station: Station
  /** Outlined as the one selected on the map. */
  selected?: boolean
  /** Also shows who taught it and the note. */
  detail?: boolean
  /** Missions that visit it. */
  missions: { id: string; name: string }[]
  /** Name of the robot it was captured from, or null when placed by hand. */
  taughtBy: string | null
}>()

const emit = defineEmits<{ select: []; edit: []; remove: [] }>()

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
        :style="{ backgroundColor: STATION_TYPE_STYLE[props.station.type].colour }"
      >
        <component :is="STATION_TYPE_STYLE[props.station.type].icon" :size="13" />
      </span>
      <span class="min-w-0 flex-1">
        <span class="block truncate text-body-sm text-ink">{{ props.station.name }}</span>
        <!-- The type in words: four colours are not a vocabulary. -->
        <span class="block truncate text-caption text-muted">
          {{ STATION_TYPE_STYLE[props.station.type].label }} ·
          <span class="font-data">
            {{ props.station.x.toFixed(2) }}, {{ props.station.y.toFixed(2) }} m ·
            {{ Math.round(radToDeg(props.station.yaw)) }}°
          </span>
        </span>
        <span
          v-if="props.missions.length"
          class="mt-xxs inline-block rounded-chip bg-surface-strong px-xxs text-caption text-muted"
          :title="props.missions.map((m) => m.name).join(', ')"
        >
          {{ props.missions.length }} mission{{ props.missions.length === 1 ? '' : 's' }}
        </span>
        <!-- Only on the selected one: detail every row carries is not
             detail, it is noise that makes the list twice as long. -->
        <span
          v-if="props.detail && (props.station.taughtByRobotId || props.station.note)"
          class="mt-xxs block text-caption text-muted-soft"
        >
          {{
            [props.taughtBy ? `Taught by ${props.taughtBy}` : null, props.station.note]
              .filter(Boolean)
              .join(' · ')
          }}
        </span>
      </span>
    </button>

    <RowActions :label="`More actions for ${props.station.name}`">
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
