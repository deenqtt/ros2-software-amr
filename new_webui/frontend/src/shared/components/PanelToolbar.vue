<script setup lang="ts">
/**
 * Toolbar above a table.
 *
 * Replaces the fixed 44px card header that the action buttons were being
 * jammed into: a row with a hard height and three competing children has
 * nowhere to give, so the primary button ended up crushed against the card's
 * corner with its label clipped.
 *
 * This grows with its contents, wraps at narrow widths instead of overflowing,
 * and gives the title and the actions their own blocks.
 */
import { cn } from '@/shared/lib/utils'

const props = defineProps<{ title: string; subtitle?: string; class?: string }>()
</script>

<template>
  <div
    :class="
      cn(
        'flex flex-wrap items-center justify-between gap-sm border-b border-hairline px-base py-sm',
        props.class,
      )
    "
  >
    <div class="min-w-0">
      <div class="flex items-center gap-xs">
        <slot name="icon" />
        <h2 class="truncate text-title-sm text-ink">{{ props.title }}</h2>
      </div>
      <p v-if="props.subtitle" class="mt-[1px] font-data text-caption text-muted">
        {{ props.subtitle }}
      </p>
    </div>

    <!-- shrink-0 so the actions never compress; the title truncates instead. -->
    <div class="flex shrink-0 items-center gap-xs">
      <slot name="actions" />
    </div>
  </div>
</template>
