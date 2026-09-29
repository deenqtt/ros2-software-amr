<script setup lang="ts">
import { cn } from '@/shared/lib/utils'
const props = defineProps<{ class?: string }>()
</script>

<template>
  <div :class="cn('p-base', props.class)"><slot /></div>
</template>
