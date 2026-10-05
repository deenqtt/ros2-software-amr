<script setup lang="ts">
/**
 * Says why the control inside is disabled.
 *
 * A disabled Button has `pointer-events: none`, so a `title` on the button
 * itself never shows: the pointer passes straight through. The wrapper takes
 * the hover instead. With no reason it renders nothing extra.
 *
 *   <BlockedTip :reason="editBlocker">
 *     <Button :disabled="!canEdit">Delete</Button>
 *   </BlockedTip>
 */
import { cn } from '@/shared/lib/utils'

/** `class` sizes the wrapper like the control would be sized: w-full, flex-1. */
const props = defineProps<{ reason?: string | null; class?: string }>()
</script>

<template>
  <span
    v-if="props.reason"
    :title="props.reason"
    :class="cn('inline-flex cursor-not-allowed [&>*]:flex-1', props.class)"
  >
    <slot />
  </span>
  <slot v-else />
</template>
