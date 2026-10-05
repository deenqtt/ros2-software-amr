<script setup lang="ts">
/**
 * Map or list, for a phone: the map keeps the full width and the side panel
 * becomes the other half of this switch instead of squeezing it. The page
 * decides when to render it.
 */
import { List, Map as MapIcon } from 'lucide-vue-next'
import { cn } from '@/shared/lib/utils'

export type MapListView = 'map' | 'list'

const props = withDefaults(
  defineProps<{ modelValue: MapListView; count?: number; listLabel?: string; class?: string }>(),
  { count: undefined, listLabel: 'List', class: undefined },
)
const emit = defineEmits<{ 'update:modelValue': [value: MapListView] }>()

const options = [
  { value: 'map', icon: MapIcon },
  { value: 'list', icon: List },
] as const

function label(value: MapListView) {
  if (value === 'map') return 'Map'
  return props.count === undefined ? props.listLabel : `${props.listLabel} (${props.count})`
}
</script>

<template>
  <div
    role="radiogroup"
    aria-label="View"
    :class="cn('flex items-center gap-[2px] rounded-control bg-surface-strong p-[3px]', props.class)"
  >
    <button
      v-for="option in options"
      :key="option.value"
      type="button"
      role="radio"
      :aria-checked="props.modelValue === option.value ? 'true' : 'false'"
      :class="
        cn(
          'inline-flex h-8 flex-1 items-center justify-center gap-xs whitespace-nowrap rounded-[6px] px-sm text-body-sm transition-colors touch:min-h-[44px]',
          props.modelValue === option.value
            ? 'bg-surface text-ink shadow-sm'
            : 'text-muted hover:text-ink',
        )
      "
      @click="emit('update:modelValue', option.value)"
    >
      <component :is="option.icon" :size="14" aria-hidden="true" />
      {{ label(option.value) }}
    </button>
  </div>
</template>
