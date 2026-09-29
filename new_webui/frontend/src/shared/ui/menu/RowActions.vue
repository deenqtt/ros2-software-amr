<script setup lang="ts">
/**
 * Overflow menu for a table row.
 *
 * Replaces a strip of icon-only buttons. Five bare icons in a cell cost an
 * operator a hover to identify each one, every time, and put a delete a single
 * stray click away from a rename — the previous UI's worst habit, where one
 * unconfirmed click could remove every keepout zone on a map.
 *
 * A menu makes the labels readable, separates the destructive item, and leaves
 * the row's primary action free to stay outside where it can be reached in one
 * click.
 */
import { MoreHorizontal } from 'lucide-vue-next'
import { DropdownMenuContent, DropdownMenuPortal, DropdownMenuRoot, DropdownMenuTrigger } from 'reka-ui'
import { buttonVariants } from '@/shared/ui/button'
import { cn } from '@/shared/lib/utils'

const props = defineProps<{
  /** Names the row for screen readers: "Actions for Warehouse A v2". */
  label: string
  align?: 'start' | 'center' | 'end'
}>()
</script>

<template>
  <DropdownMenuRoot>
    <DropdownMenuTrigger
      :aria-label="props.label"
      :title="props.label"
      :class="cn(buttonVariants({ variant: 'ghost', size: 'icon-sm' }))"
    >
      <MoreHorizontal :size="15" />
    </DropdownMenuTrigger>

    <DropdownMenuPortal>
      <DropdownMenuContent
        :align="props.align ?? 'end'"
        :side-offset="4"
        class="z-50 min-w-[11rem] overflow-hidden rounded-surface border border-hairline bg-surface p-xxs shadow-soft"
      >
        <slot />
      </DropdownMenuContent>
    </DropdownMenuPortal>
  </DropdownMenuRoot>
</template>
