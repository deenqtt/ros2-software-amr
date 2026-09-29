<script setup lang="ts">
/**
 * Text input. `text-input` in DESIGN.md — hairline border, 12px radius,
 * border thickens to the brand blue on focus — at console height rather than
 * the marketing 48px.
 *
 * `invalid` is a real state, not a colour: it drives aria-invalid too, so the
 * error is announced and not only seen.
 */
import { cn } from '@/shared/lib/utils'

const props = withDefaults(
  defineProps<{
    /**
     * Accepts a number so a numeric field can bind its value directly. The
     * event stays a string, because that is what the DOM element actually
     * holds — the caller converts, and does so knowing what it wants.
     */
    modelValue: string | number
    invalid?: boolean
    mono?: boolean
    class?: string
  }>(),
  { invalid: false, mono: false },
)

defineEmits<{ 'update:modelValue': [value: string] }>()
</script>

<template>
  <input
    :value="props.modelValue"
    :aria-invalid="props.invalid || undefined"
    :class="
      cn(
        'h-control w-full rounded-control border bg-canvas px-sm text-body-md text-ink',
        'transition-colors duration-150 ease-out placeholder:text-muted-soft',
        'focus:outline-none focus:ring-0',
        props.mono ? 'font-ident' : 'font-sans',
        props.invalid
          ? 'border-status-fault focus:border-status-fault'
          : 'border-hairline focus:border-primary',
        'disabled:bg-surface-soft disabled:text-muted-soft',
        props.class,
      )
    "
    v-bind="$attrs"
    @input="$emit('update:modelValue', ($event.target as HTMLInputElement).value)"
  />
</template>
