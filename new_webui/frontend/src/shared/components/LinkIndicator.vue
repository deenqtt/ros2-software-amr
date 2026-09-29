<script setup lang="ts">
/**
 * Link state, in five values rather than two.
 *
 * `stale` is the one that earns its place: rosbridge answering while the stack
 * behind it is dead. A boolean calls that "connected", which is how the old UI
 * could show ONLINE / AVAILABLE for a robot whose pose had been frozen for an
 * hour.
 *
 * Colour is never the only channel — each state also has its own mark.
 */
import { computed } from 'vue'
import type { LinkState } from '@/domain/ros/link'
import { cn } from '@/shared/lib/utils'

const props = withDefaults(
  defineProps<{
    state: LinkState
    /** Retry number, shown while reconnecting so a loop is visible. */
    attempt?: number
    showLabel?: boolean
    class?: string
  }>(),
  { attempt: 0, showLabel: true },
)

interface Descriptor {
  label: string
  dot: string
  text: string
  hint: string
}

const DESCRIPTORS: Record<LinkState, Descriptor> = {
  online: {
    label: 'Online',
    dot: 'bg-status-ok',
    text: 'text-status-ok',
    hint: 'Bridge connected and telemetry is arriving.',
  },
  stale: {
    label: 'Stale',
    dot: 'bg-status-warn',
    text: 'text-status-warn',
    hint: 'Bridge is connected but a periodic topic has gone silent — the stack behind it may be down.',
  },
  connecting: {
    label: 'Connecting',
    dot: 'bg-status-warn animate-pulse',
    text: 'text-status-warn',
    hint: 'Opening the connection.',
  },
  offline: {
    label: 'Offline',
    dot: 'bg-status-fault',
    text: 'text-status-fault',
    hint: 'The bridge cannot be reached.',
  },
  muted: {
    label: 'Muted',
    dot: 'bg-muted-soft',
    text: 'text-muted',
    hint: 'Monitoring is switched off for this robot.',
  },
}

const descriptor = computed(() => DESCRIPTORS[props.state])

const label = computed(() =>
  props.state === 'connecting' && props.attempt > 1
    ? `Reconnecting (${props.attempt})`
    : descriptor.value.label,
)

// Shape is the redundant channel beside colour: a diamond for the two states
// that mean "look at me", a square for a hard fault.
const markShape = computed(() => {
  if (props.state === 'stale') return 'rotate-45 rounded-[1px]'
  if (props.state === 'offline') return 'rounded-[1px]'
  return 'rounded-full'
})
</script>

<template>
  <span
    :class="cn('inline-flex items-center gap-xs text-body-sm', descriptor.text, props.class)"
    :title="descriptor.hint"
  >
    <span
      :class="cn('h-[7px] w-[7px] shrink-0', descriptor.dot, markShape)"
      aria-hidden="true"
    />
    <span v-if="props.showLabel" class="font-medium">{{ label }}</span>
  </span>
</template>
