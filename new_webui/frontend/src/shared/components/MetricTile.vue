<script setup lang="ts">
/** A single labelled number, rendered in mono per DESIGN.md's number rule. */
import { cn } from '@/shared/lib/utils'

const props = withDefaults(
  defineProps<{ label: string; value: string; unit?: string; size?: 'md' | 'lg'; class?: string }>(),
  { size: 'md' },
)
</script>

<template>
  <div :class="cn('rounded-control bg-surface-soft px-sm py-xs', props.class)">
    <div class="text-label uppercase text-muted">{{ props.label }}</div>
    <div class="mt-xxs flex items-baseline gap-xxs">
      <span
        :class="
          cn('font-data text-ink', props.size === 'lg' ? 'text-number-lg' : 'text-number-md')
        "
        >{{ props.value }}</span
      >
      <span v-if="props.unit" class="text-caption text-muted">{{ props.unit }}</span>
    </div>
  </div>
</template>
