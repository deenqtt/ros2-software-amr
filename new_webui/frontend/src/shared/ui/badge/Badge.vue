<script setup lang="ts">
/** Pill badge — `badge-pill` in DESIGN.md: surface-strong fill, caption-strong type. */
import { cn } from '@/shared/lib/utils'

const props = defineProps<{ class?: string }>()
</script>

<template>
  <span
    :class="
      cn(
        'inline-flex items-center gap-xxs rounded-chip px-xs py-[3px] text-label uppercase',
        props.class,
      )
    "
  >
    <slot />
  </span>
</template>
