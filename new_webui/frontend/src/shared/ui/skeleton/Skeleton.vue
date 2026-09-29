<script setup lang="ts">
/**
 * Loading placeholder.
 *
 * Shaped like the content it replaces so the layout does not jump when data
 * lands. Uses a pulse rather than a sweeping shimmer: a shimmer reads as
 * motion, and in this product motion is reserved for things that are actually
 * moving.
 */
import { cn } from '@/shared/lib/utils'

const props = defineProps<{ class?: string }>()
</script>

<template>
  <div
    :class="cn('animate-pulse rounded-chip bg-surface-strong', props.class)"
    aria-hidden="true"
  />
</template>
