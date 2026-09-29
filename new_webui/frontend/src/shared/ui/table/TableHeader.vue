<script setup lang="ts">
import { cn } from '@/shared/lib/utils'
const props = defineProps<{ class?: string }>()
</script>

<template>
  <thead :class="cn('border-b border-hairline', props.class)"><slot /></thead>
</template>
