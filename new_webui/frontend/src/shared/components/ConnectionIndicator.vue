<script setup lang="ts">
import { computed } from 'vue'
import { connectionStatus } from '@/domain/ros/status'
import type { ConnectionState } from '@/domain/types'
import { cn } from '@/shared/lib/utils'

const props = withDefaults(
  defineProps<{ state: ConnectionState; showLabel?: boolean; class?: string }>(),
  { showLabel: true },
)

const descriptor = computed(() => connectionStatus(props.state))

const dotClass = computed(() => {
  switch (props.state) {
    case 'connected':
      return 'bg-status-ok'
    case 'connecting':
    case 'reconnecting':
      return 'bg-status-warn animate-pulse'
    default:
      return 'bg-status-fault'
  }
})
</script>

<template>
  <div :class="cn('flex items-center gap-xs text-body-sm', props.class)" :title="descriptor.label">
    <span :class="cn('h-[7px] w-[7px] shrink-0 rounded-full', dotClass)" aria-hidden="true" />
    <span v-if="props.showLabel" class="font-medium text-body">{{ descriptor.label }}</span>
  </div>
</template>
