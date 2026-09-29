<script setup lang="ts">
/**
 * Flat by default. DESIGN.md puts roughly 80% of surfaces at no shadow and no
 * border, with a 1px hairline as the next tier and exactly one soft shadow
 * above that. Depth comes from card-on-card layering, never from stacked
 * shadow tiers.
 */
import { cn } from '@/shared/lib/utils'

const props = withDefaults(
  defineProps<{ elevation?: 'flat' | 'hairline' | 'soft'; class?: string }>(),
  { elevation: 'hairline' },
)

const ELEVATION = {
  flat: 'bg-surface',
  hairline: 'bg-surface border border-hairline',
  soft: 'bg-surface border border-hairline shadow-soft',
} as const
</script>

<template>
  <div :class="cn('rounded-surface', ELEVATION[props.elevation], props.class)">
    <slot />
  </div>
</template>
