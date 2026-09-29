<script setup lang="ts">
/**
 * The only component that renders operational status.
 *
 * Five hues, all drawn from the DESIGN.md palette — no new colour is
 * introduced. `attention` and `warning` share the amber, because they are the
 * same signal to the eye ("look here") and differ in what they ask of you.
 * They are told apart by weight, not hue:
 *
 *   attention -> SOLID amber. The robot is waiting on a person. Act now.
 *   warning   -> SOFT amber.  Degraded but still running. Be aware.
 *
 * That solid/soft split is learnable in one shift and survives a sunlit
 * factory floor, where two similar ambers would not.
 *
 * Colour is never the only channel: each tone also carries a shape.
 */
import { computed } from 'vue'
import { Badge } from '@/shared/ui/badge'
import { cn } from '@/shared/lib/utils'
import type { StatusTone } from '@/domain/types'

const props = withDefaults(
  defineProps<{ tone: StatusTone; label: string; pulse?: boolean; class?: string }>(),
  { pulse: false },
)

const TONE_CLASS: Record<StatusTone, string> = {
  neutral: 'bg-surface-strong text-body',
  active: 'bg-status-run/10 text-status-run',
  attention: 'bg-status-act text-[#0a0b0d]',
  warning: 'bg-status-warn/12 text-status-warn',
  fault: 'bg-status-fault/12 text-status-fault',
  success: 'bg-status-ok/12 text-status-ok',
}

/** Redundant channel alongside colour. */
const TONE_MARK: Record<StatusTone, string> = {
  neutral: 'rounded-full',
  active: 'rounded-full',
  attention: 'rounded-[1px] rotate-45',
  warning: 'rounded-[1px] rotate-45',
  fault: 'rounded-[1px]',
  success: 'rounded-full',
}

const toneClass = computed(() => TONE_CLASS[props.tone])
const markClass = computed(() => TONE_MARK[props.tone])
</script>

<template>
  <Badge :class="cn(toneClass, props.class)">
    <span
      :class="cn('h-[5px] w-[5px] bg-current', markClass, props.pulse && 'animate-pulse')"
      aria-hidden="true"
    />
    {{ props.label }}
  </Badge>
</template>
