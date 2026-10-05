<script setup lang="ts">
/**
 * Shown in place of a task that needs a precise pointer and room, such as
 * painting map cells, when the screen is a phone.
 */
import { Laptop } from 'lucide-vue-next'
import { RouterLink, type RouteLocationRaw } from 'vue-router'
import { Button } from '@/shared/ui/button'
import EmptyState from './EmptyState.vue'

const props = withDefaults(
  defineProps<{
    title?: string
    description: string
    backTo: RouteLocationRaw
    backLabel: string
    class?: string
  }>(),
  { title: 'Best on a tablet or laptop', class: undefined },
)
const emit = defineEmits<{ continue: [] }>()
</script>

<template>
  <EmptyState :title="props.title" :description="props.description" :class="props.class">
    <template #icon>
      <Laptop :size="32" class="text-muted" aria-hidden="true" />
    </template>
    <template #action>
      <div class="mt-xs flex flex-wrap items-center justify-center gap-sm">
        <Button size="sm" as-child>
          <RouterLink :to="props.backTo">{{ props.backLabel }}</RouterLink>
        </Button>
        <!-- Advice, not a rule: phones vary, and a large one may manage. -->
        <Button size="sm" variant="outline" @click="emit('continue')">Open anyway</Button>
      </div>
    </template>
  </EmptyState>
</template>
