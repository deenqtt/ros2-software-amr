<script setup lang="ts">
/**
 * Alarm log.
 *
 * Active first, then acknowledged. Records persist after acknowledgement so
 * "what happened at 14:20" is answerable — the old UI's errors were toasts
 * that vanished in three seconds, and the ones raised by the ROS layer were
 * pushed into an array nothing rendered.
 */
import { computed } from 'vue'
import { BellOff, Check } from 'lucide-vue-next'
import { useAlarmStore, type AlarmSeverity } from '@/stores/alarms'
import { Button } from '@/shared/ui/button'
import { Card, CardContent, CardHeader } from '@/shared/ui/card'
import SectionLabel from '@/shared/components/SectionLabel.vue'
import StatusBadge from '@/shared/components/StatusBadge.vue'
import EmptyState from '@/shared/components/EmptyState.vue'
import type { StatusTone } from '@/domain/types'

const alarms = useAlarmStore()

const acknowledged = computed(() => alarms.ordered.filter((a) => a.acknowledgedAt !== null))
const active = computed(() => alarms.ordered.filter((a) => a.acknowledgedAt === null))

const SEVERITY_TONE: Record<AlarmSeverity, StatusTone> = {
  fault: 'fault',
  warning: 'warning',
  info: 'active',
}

function timestamp(at: number): string {
  return new Date(at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })
}
</script>

<template>
  <div class="space-y-base p-lg">
    <Card>
      <CardHeader>
        <SectionLabel>Active ({{ active.length }})</SectionLabel>
        <div class="flex-1" />
        <Button v-if="active.length" variant="text" size="sm" @click="alarms.acknowledgeAll()">
          <Check :size="13" /> Acknowledge all
        </Button>
      </CardHeader>

      <CardContent class="p-0">
        <EmptyState
          v-if="active.length === 0"
          title="No active alarms"
          description="Faults raised by the robot, the bridge or the backend appear here and stay until acknowledged."
          class="m-base"
        >
          <template #icon><BellOff :size="20" class="text-muted" /></template>
        </EmptyState>

        <ul v-else class="divide-y divide-hairline">
          <li v-for="alarm in active" :key="alarm.id" class="flex items-center gap-sm px-base py-sm">
            <StatusBadge :tone="SEVERITY_TONE[alarm.severity]" :label="alarm.severity" />
            <div class="min-w-0 flex-1">
              <p class="truncate text-body-md text-ink">{{ alarm.message }}</p>
              <p class="text-caption text-muted">{{ alarm.source }}</p>
            </div>
            <span class="font-data text-number-sm text-muted">{{ timestamp(alarm.raisedAt) }}</span>
            <Button variant="ghost" size="sm" @click="alarms.acknowledge(alarm.id)">
              Acknowledge
            </Button>
          </li>
        </ul>
      </CardContent>
    </Card>

    <Card v-if="acknowledged.length">
      <CardHeader>
        <SectionLabel>Acknowledged ({{ acknowledged.length }})</SectionLabel>
      </CardHeader>
      <CardContent class="p-0">
        <ul class="divide-y divide-hairline">
          <li
            v-for="alarm in acknowledged"
            :key="alarm.id"
            class="flex items-center gap-sm px-base py-sm opacity-60"
          >
            <StatusBadge tone="neutral" :label="alarm.severity" />
            <div class="min-w-0 flex-1">
              <p class="truncate text-body-md text-ink">{{ alarm.message }}</p>
              <p class="text-caption text-muted">{{ alarm.source }}</p>
            </div>
            <span class="font-data text-number-sm text-muted">{{ timestamp(alarm.raisedAt) }}</span>
          </li>
        </ul>
      </CardContent>
    </Card>
  </div>
</template>
