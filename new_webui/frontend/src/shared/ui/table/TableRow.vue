<script setup lang="ts">
/** No zebra striping — hairline rules carry the row separation, per DESIGN.md. */
import { cn } from '@/shared/lib/utils'

const props = withDefaults(defineProps<{ interactive?: boolean; class?: string }>(), {
  interactive: false,
})
</script>

<template>
  <tr
    :class="
      cn(
        'group',
        props.interactive && 'transition-colors duration-150 ease-out hover:bg-surface-soft',
        props.class,
      )
    "
  >
    <slot />
  </tr>
</template>
