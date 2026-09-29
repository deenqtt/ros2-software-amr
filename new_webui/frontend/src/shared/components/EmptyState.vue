<script setup lang="ts">
import { cn } from '@/shared/lib/utils'

const props = defineProps<{ title: string; description?: string; class?: string }>()
</script>

<template>
  <div
    :class="
      cn(
        'flex flex-col items-center justify-center gap-sm rounded-surface border border-dashed border-hairline px-lg py-xxl text-center',
        props.class,
      )
    "
  >
    <slot name="icon" />
    <p class="text-title-sm text-ink">{{ props.title }}</p>
    <p v-if="props.description" class="max-w-md text-body-sm text-muted">
      {{ props.description }}
    </p>
    <slot name="action" />
  </div>
</template>
