<script setup lang="ts">
/**
 * Label + control + hint/error, as one unit.
 *
 * The error slot replaces the hint rather than stacking below it, so the field
 * never grows and the dialog never reflows while someone is typing in it.
 */
import { useId } from 'vue'
import { cn } from '@/shared/lib/utils'

const props = withDefaults(
  defineProps<{
    label: string
    hint?: string
    error?: string
    required?: boolean
    class?: string
  }>(),
  { required: false },
)

const id = useId()
</script>

<template>
  <div :class="cn('space-y-xxs', props.class)">
    <label :for="id" class="flex items-center gap-xxs text-label uppercase text-muted">
      {{ props.label }}
      <span v-if="!props.required" class="normal-case tracking-normal text-muted-soft">
        (optional)
      </span>
    </label>

    <slot :id="id" :invalid="Boolean(props.error)" />

    <p v-if="props.error" class="text-caption text-status-fault">{{ props.error }}</p>
    <p v-else-if="props.hint" class="text-caption text-muted">{{ props.hint }}</p>
  </div>
</template>
