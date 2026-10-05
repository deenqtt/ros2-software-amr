<script setup lang="ts">
/**
 * The route drawn on its map, for the mission editor.
 *
 * One component for the two places the editor shows it — folded under the
 * steps on a phone, sticky beside them on wider screens — so the two cannot
 * drift apart. The caller owns the frame (height, border, stickiness).
 */
import { MousePointerClick } from 'lucide-vue-next'
import type { Grid } from '@/domain/map/pgm'
import type { Station } from '@/domain/types'
import StationMapCanvas from '@/features/stations/components/StationMapCanvas.vue'
import { STATION_TYPE_LIST } from '@/features/stations/stationType'
import { Skeleton } from '@/shared/ui/skeleton'
import EmptyState from '@/shared/components/EmptyState.vue'

const props = defineProps<{
  grid: Grid | null
  placement: { resolution: number; originX: number; originY: number }
  stations: Station[]
  selectedId: string | null
  route: string[]
  loading: boolean
  error: string | null
  /** Shows the "click/tap a station to add it" hint. */
  canEdit: boolean
}>()

const emit = defineEmits<{ select: [stationId: string | null] }>()
</script>

<template>
  <Skeleton v-if="props.loading" class="h-full w-full rounded-none" />
  <EmptyState
    v-else-if="props.error"
    class="p-lg"
    title="Cannot show this map"
    :description="props.error"
  />
  <StationMapCanvas
    v-else
    :grid="props.grid"
    :placement="props.placement"
    :stations="props.stations"
    :selected-id="props.selectedId"
    :placing="false"
    :movable="false"
    :route="props.route"
    @select="emit('select', $event)"
  >
    <template #legend>
      <template v-if="props.canEdit">
        <span class="flex items-center gap-xxs whitespace-nowrap text-ink touch:hidden">
          <MousePointerClick :size="12" /> Click a station to add it
        </span>
        <span class="hidden items-center gap-xxs whitespace-nowrap text-ink touch:flex">
          <MousePointerClick :size="12" /> Tap a station to add it
        </span>
      </template>
      <span
        v-for="kind in STATION_TYPE_LIST"
        :key="kind.value"
        class="hidden items-center gap-xxs whitespace-nowrap 2xl:flex"
      >
        <span class="h-2.5 w-2.5 rounded-full" :style="{ backgroundColor: kind.colour }" />
        {{ kind.label }}
      </span>
    </template>
  </StationMapCanvas>
</template>
