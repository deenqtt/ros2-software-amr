<script setup lang="ts">
import { cn } from '@/shared/lib/utils'
const props = defineProps<{ class?: string }>()
</script>

<template>
  <div class="w-full overflow-x-auto">
    <table :class="cn('w-full caption-bottom border-collapse text-left', props.class)">
      <slot />
    </table>
  </div>
</template>
