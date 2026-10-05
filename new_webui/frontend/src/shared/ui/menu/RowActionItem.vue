<script setup lang="ts">
/**
 * One entry in a row's overflow menu.
 *
 * Renders a router link, an anchor, or a button depending on what it is given,
 * because a download has to be a real <a download> and a navigation has to be a
 * real link — a button that calls router.push cannot be middle-clicked or
 * opened in a new tab.
 */
import { DropdownMenuItem } from 'reka-ui'
import { RouterLink } from 'vue-router'
import type { Component } from 'vue'
import { cn } from '@/shared/lib/utils'

const props = defineProps<{
  icon?: Component
  /** Navigate: rendered as a RouterLink. */
  to?: string
  /** Download or external: rendered as an anchor. */
  href?: string
  download?: boolean
  disabled?: boolean
  /** Styles the item as destructive and keeps it visually apart. */
  destructive?: boolean
}>()

const emit = defineEmits<{ select: [] }>()

const itemClass = cn(
  'flex w-full cursor-pointer items-center gap-xs rounded-control px-sm py-xs text-left text-body-sm outline-none transition-colors touch:min-h-[44px]',
  'data-[highlighted]:bg-surface-strong data-[disabled]:cursor-not-allowed data-[disabled]:opacity-40',
)
</script>

<template>
  <DropdownMenuItem
    :disabled="props.disabled"
    :class="cn(itemClass, props.destructive ? 'text-status-fault' : 'text-body')"
    @select="emit('select')"
  >
    <template v-if="props.to">
      <RouterLink :to="props.to" class="flex flex-1 items-center gap-xs">
        <component :is="props.icon" v-if="props.icon" :size="14" class="shrink-0" />
        <slot />
      </RouterLink>
    </template>
    <template v-else-if="props.href">
      <a :href="props.href" :download="props.download" class="flex flex-1 items-center gap-xs">
        <component :is="props.icon" v-if="props.icon" :size="14" class="shrink-0" />
        <slot />
      </a>
    </template>
    <template v-else>
      <component :is="props.icon" v-if="props.icon" :size="14" class="shrink-0" />
      <slot />
    </template>
  </DropdownMenuItem>
</template>
