<script setup lang="ts">
/** Section heading. One component; the old UI repeated the class string 20 times. */
import { cn } from '@/shared/lib/utils'

const props = defineProps<{ class?: string }>()
</script>

<template>
  <div :class="cn('flex items-center gap-xs text-label uppercase text-muted', props.class)">
    <slot name="icon" />
    <slot />
  </div>
</template>
