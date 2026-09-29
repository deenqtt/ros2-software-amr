<script setup lang="ts">
import { cn } from '@/shared/lib/utils'
const props = defineProps<{ class?: string }>()
</script>

<template>
  <div :class="cn('flex h-11 items-center gap-xs border-b border-hairline px-base', props.class)">
    <slot />
  </div>
</template>
