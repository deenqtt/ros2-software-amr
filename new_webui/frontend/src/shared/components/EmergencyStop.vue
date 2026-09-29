<script setup lang="ts">
/**
 * Emergency stop.
 *
 * Deliberately the one place the reference's "never fill with semantic red"
 * rule is set aside. There, red means "price down" and filling it would shout
 * for no reason. Here it means "stop a moving machine", and the control has
 * to be the loudest thing on screen.
 *
 * Two rules the old implementation broke:
 *
 *  1. It must actually stop the robot. Cancelling a Nav2 goal is not enough —
 *     the docking manager and the joystick publish to /cmd_vel outside Nav2,
 *     so the handler must also hold a zero Twist. That is the caller's job.
 *  2. When it cannot act, it must say so. The old button was styled as
 *     disabled while disconnected but still fired its handler and still
 *     reported "Emergency stop activated!" — positive confirmation of nothing,
 *     in exactly the situation where the truth matters most. Here `disabled`
 *     is a real attribute and the label changes to NO LINK.
 */
import { computed } from 'vue'
import { OctagonX } from 'lucide-vue-next'
import { cn } from '@/shared/lib/utils'

const props = withDefaults(
  defineProps<{
    connected: boolean
    moving?: boolean
    variant?: 'bar' | 'floating'
    class?: string
  }>(),
  { moving: false, variant: 'bar' },
)

const emit = defineEmits<{ stop: [] }>()

const label = computed(() => (props.connected ? 'E-STOP' : 'NO LINK'))
const title = computed(() =>
  props.connected
    ? 'Emergency stop — halts the robot immediately'
    : 'Cannot stop: no connection to this robot',
)

function onPress() {
  if (!props.connected) return
  emit('stop')
}
</script>

<template>
  <button
    type="button"
    :disabled="!props.connected"
    :title="title"
    :aria-label="title"
    :class="
      cn(
        'relative inline-flex items-center justify-center font-semibold uppercase tracking-wide transition-transform duration-150 ease-out active:scale-95',
        'disabled:cursor-not-allowed disabled:bg-surface-strong disabled:text-muted-soft disabled:active:scale-100',
        props.variant === 'bar'
          ? 'h-control gap-xs rounded-control px-base text-body-sm'
          : 'h-14 w-14 flex-col gap-0 rounded-full text-label',
        props.connected && 'bg-status-fault text-white hover:brightness-110',
        props.class,
      )
    "
    @click="onPress"
  >
    <span
      v-if="props.connected && props.moving"
      class="absolute inset-0 animate-ping rounded-[inherit] bg-status-fault opacity-25"
      aria-hidden="true"
    />
    <OctagonX :size="props.variant === 'bar' ? 15 : 20" />
    <span>{{ label }}</span>
  </button>
</template>
