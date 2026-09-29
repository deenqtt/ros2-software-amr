<script setup lang="ts">
/**
 * On-screen drive stick.
 *
 * Pointer capture is what makes it safe: without it a drag that leaves the
 * element stops producing events while the browser still considers the button
 * held, and the last command sits there. With capture, the release always
 * arrives — and `pointercancel` covers the cases where it does not.
 *
 * The stick is its own deadman: letting go recentres it and emits a stop.
 */
import { computed, onBeforeUnmount, ref } from 'vue'
import { stickToTwist, type SpeedPreset, type Twist } from '@/domain/teleop'
import { cn } from '@/shared/lib/utils'

const props = withDefaults(
  defineProps<{ preset: SpeedPreset; disabled?: boolean; size?: number }>(),
  { disabled: false, size: 168 },
)

const emit = defineEmits<{ command: [twist: Twist]; release: [] }>()

const THUMB = 44

const pad = ref<HTMLElement | null>(null)
const dragging = ref(false)
const offset = ref({ x: 0, y: 0 })
let pointerId: number | null = null

const radius = computed(() => props.size / 2 - THUMB / 2 - 4)

const thumbStyle = computed(() => ({
  transform: `translate(${offset.value.x}px, ${offset.value.y}px)`,
}))

/** Normalised stick position, in ROS orientation. */
function normalised() {
  const r = radius.value || 1
  return {
    // Screen y grows downward; forward is negative there.
    y: -offset.value.y / r,
    // Screen x grows rightward; ROS angular.z is positive to the left.
    x: -offset.value.x / r,
  }
}

function moveTo(clientX: number, clientY: number) {
  const rect = pad.value?.getBoundingClientRect()
  if (!rect) return
  const dx = clientX - (rect.left + rect.width / 2)
  const dy = clientY - (rect.top + rect.height / 2)
  const distance = Math.hypot(dx, dy)
  const scale = distance > radius.value ? radius.value / distance : 1
  offset.value = { x: dx * scale, y: dy * scale }

  const { x, y } = normalised()
  emit('command', stickToTwist(x, y, props.preset))
}

function recentre() {
  offset.value = { x: 0, y: 0 }
  dragging.value = false
  pointerId = null
  emit('release')
}

function onPointerDown(event: PointerEvent) {
  if (props.disabled) return
  dragging.value = true
  pointerId = event.pointerId
  pad.value?.setPointerCapture(event.pointerId)
  moveTo(event.clientX, event.clientY)
}

function onPointerMove(event: PointerEvent) {
  if (!dragging.value || event.pointerId !== pointerId) return
  moveTo(event.clientX, event.clientY)
}

function onPointerUp(event: PointerEvent) {
  if (event.pointerId !== pointerId) return
  pad.value?.releasePointerCapture?.(event.pointerId)
  recentre()
}

// A component unmounted mid-drag would otherwise leave the robot holding the
// last command until the agent's watchdog fires.
onBeforeUnmount(() => {
  if (dragging.value) recentre()
})
</script>

<template>
  <div
    ref="pad"
    :class="
      cn(
        'relative touch-none select-none rounded-full border-2 transition-colors',
        props.disabled
          ? 'cursor-not-allowed border-hairline bg-surface-soft'
          : 'cursor-grab border-hairline bg-surface-soft active:cursor-grabbing',
        dragging && 'border-primary',
      )
    "
    :style="{ width: `${props.size}px`, height: `${props.size}px` }"
    role="application"
    :aria-label="props.disabled ? 'Drive control, disabled' : 'Drive control'"
    @pointerdown="onPointerDown"
    @pointermove="onPointerMove"
    @pointerup="onPointerUp"
    @pointercancel="onPointerUp"
    @lostpointercapture="recentre"
  >
    <!-- Crosshair, so the centre is findable without dragging to look. -->
    <span class="absolute left-1/2 top-2 h-[calc(100%-1rem)] w-px -translate-x-1/2 bg-hairline" />
    <span class="absolute top-1/2 left-2 h-px w-[calc(100%-1rem)] -translate-y-1/2 bg-hairline" />

    <span
      :class="
        cn(
          'absolute left-1/2 top-1/2 rounded-full border shadow-soft transition-colors',
          props.disabled
            ? 'border-hairline bg-surface-strong'
            : dragging
              ? 'border-primary bg-primary'
              : 'border-hairline bg-surface',
        )
      "
      :style="{
        width: `${THUMB}px`,
        height: `${THUMB}px`,
        marginLeft: `${-THUMB / 2}px`,
        marginTop: `${-THUMB / 2}px`,
        ...thumbStyle,
      }"
    />
  </div>
</template>
