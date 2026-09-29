<script setup lang="ts">
import { cn } from '@/shared/lib/utils'

const props = withDefaults(defineProps<{ align?: 'left' | 'right'; class?: string }>(), {
  align: 'left',
})
</script>

<template>
  <td
    :class="cn('h-[52px] px-base align-middle', props.align === 'right' && 'text-right', props.class)"
  >
    <slot />
  </td>
</template>
