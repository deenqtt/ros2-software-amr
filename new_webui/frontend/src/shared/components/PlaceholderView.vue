<script setup lang="ts">
/**
 * Stand-in for a destination that has not been built yet.
 *
 * States which roadmap phase covers the screen and what blocks it, so an
 * unbuilt route documents itself instead of rendering a blank page.
 */
import { Construction } from 'lucide-vue-next'
import EmptyState from './EmptyState.vue'

defineProps<{ title: string; description: string; phase?: string }>()
</script>

<template>
  <div class="p-lg">
    <EmptyState :title="title" :description="description">
      <template #icon>
        <Construction :size="20" class="text-muted" />
      </template>
      <template #action>
        <span
          v-if="phase"
          class="rounded-chip bg-surface-strong px-xs py-[3px] text-label uppercase text-muted"
        >
          {{ phase }}
        </span>
      </template>
    </EmptyState>
  </div>
</template>
