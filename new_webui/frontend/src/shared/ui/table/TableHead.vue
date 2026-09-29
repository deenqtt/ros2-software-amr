<script setup lang="ts">
import { cn } from '@/shared/lib/utils'

const props = withDefaults(defineProps<{ align?: 'left' | 'right'; class?: string }>(), {
  align: 'left',
})
</script>

<template>
  <th
    scope="col"
    :class="
      cn(
        'h-9 whitespace-nowrap px-base text-label uppercase text-muted',
        props.align === 'right' && 'text-right',
        props.class,
      )
    "
  >
    <slot />
  </th>
</template>
