<script setup lang="ts">
/**
 * Whether SLAM is actually running on the robot.
 *
 * Reads the agent's own report rather than inferring it from whether map
 * messages are arriving. A grid can keep arriving for a moment after the stack
 * dies, and it never arrives at all in the first seconds after it starts —
 * both would make an inferred indicator lie at exactly the wrong time.
 *
 * `null` is its own state: no agent has spoken, so nothing is known. That is
 * different from an agent reporting idle, and the two must not look alike.
 */
import { computed } from 'vue'
import { Loader2 } from 'lucide-vue-next'
import type { AgentStatus } from '../useRobotTelemetry'
import type { StatusTone } from '@/domain/types'
import StatusBadge from '@/shared/components/StatusBadge.vue'

const props = defineProps<{ agent: AgentStatus | null }>()

interface Descriptor {
  tone: StatusTone
  label: string
  detail: string
  busy: boolean
}

const descriptor = computed<Descriptor>(() => {
  const agent = props.agent
  if (agent === null) {
    return {
      tone: 'neutral',
      label: 'No agent',
      detail: 'Nothing on this robot is reporting its mode.',
      busy: false,
    }
  }

  if (agent.state === 'failed') {
    return {
      tone: 'fault',
      label: 'SLAM failed',
      detail: agent.detail || 'The stack did not come up.',
      busy: false,
    }
  }

  if (agent.mode === 'map') {
    if (agent.state === 'running') {
      return { tone: 'success', label: 'SLAM running', detail: 'Surveying.', busy: false }
    }
    if (agent.state === 'starting') {
      return {
        tone: 'active',
        label: 'SLAM starting',
        detail: 'Waiting for slam_toolbox to appear.',
        busy: true,
      }
    }
    if (agent.state === 'stopping') {
      return { tone: 'active', label: 'SLAM stopping', detail: 'Shutting down.', busy: true }
    }
  }

  if (agent.mode === 'nav' && agent.state === 'running') {
    return {
      tone: 'neutral',
      label: 'Navigating',
      detail: 'Nav2 is running; SLAM is not.',
      busy: false,
    }
  }

  return {
    tone: 'neutral',
    label: 'SLAM stopped',
    detail: agent.detail || 'No stack is running on this robot.',
    busy: false,
  }
})
</script>

<template>
  <span :title="descriptor.detail" class="inline-flex items-center gap-xs">
    <Loader2 v-if="descriptor.busy" :size="13" class="animate-spin text-status-run" />
    <StatusBadge :tone="descriptor.tone" :label="descriptor.label" :pulse="descriptor.busy" />
  </span>
</template>
