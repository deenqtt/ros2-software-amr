<script setup lang="ts">
import { cn } from '@/shared/lib/utils'
const props = defineProps<{ class?: string }>()
</script>

<template>
  <tbody :class="cn('divide-y divide-hairline', props.class)"><slot /></tbody>
</template>
