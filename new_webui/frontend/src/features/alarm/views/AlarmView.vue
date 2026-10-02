<script setup lang="ts">
/**
 * Alarm log.
 *
 * Two lists with different jobs. "Active" is what needs a person: faults, then
 * warnings, each waiting to be acknowledged. "Log" is what happened: routine
 * events and alarms already handled, newest first. Records persist after
 * acknowledgement so "what happened at 14:20" is answerable — the old UI's
 * errors were toasts that vanished in three seconds.
 */
import { computed, onBeforeUnmount, ref } from 'vue'
import { RouterLink } from 'vue-router'
import { BellOff, Check, Trash2 } from 'lucide-vue-next'
import { useAlarmStore, type Alarm, type AlarmSeverity } from '@/stores/alarms'
import { Button } from '@/shared/ui/button'
import { Card, CardContent, CardHeader } from '@/shared/ui/card'
import SectionLabel from '@/shared/components/SectionLabel.vue'
import StatusBadge from '@/shared/components/StatusBadge.vue'
import EmptyState from '@/shared/components/EmptyState.vue'
import ConfirmDialog from '@/shared/components/ConfirmDialog.vue'
import type { StatusTone } from '@/domain/types'
import { alarmAge, alarmTime } from '../alarmTime'

const alarms = useAlarmStore()

const SEVERITY_TONE: Record<AlarmSeverity, StatusTone> = {
  fault: 'fault',
  warning: 'warning',
  info: 'active',
}

const SEVERITY_LABEL: Record<AlarmSeverity, string> = {
  fault: 'Fault',
  warning: 'Warning',
  info: 'Event',
}

/** Ticks so "Yesterday" and the hover age stay right on a screen left open. */
const now = ref(Date.now())
const clock = setInterval(() => (now.value = Date.now()), 30_000)
onBeforeUnmount(() => clearInterval(clock))

function when(alarm: Alarm): string {
  return alarmTime(alarm.raisedAt, now.value)
}

function whenTitle(alarm: Alarm): string {
  const raised = `${new Date(alarm.raisedAt).toLocaleString()} · ${alarmAge(alarm.raisedAt, now.value)}`
  return alarm.acknowledgedAt
    ? `${raised} · acknowledged ${alarmTime(alarm.acknowledgedAt, now.value)}`
    : raised
}

const confirmClear = ref(false)
const historyCount = computed(() => alarms.history.length)

function clearHistory() {
  alarms.clearHistory()
  confirmClear.value = false
}
</script>

<template>
  <div class="space-y-base p-lg">
    <Card>
      <CardHeader>
        <SectionLabel>Active ({{ alarms.activeCount }})</SectionLabel>
        <div class="flex-1" />
        <Button
          v-if="alarms.activeCount > 1"
          variant="text"
          size="sm"
          @click="alarms.acknowledgeAll()"
        >
          <Check :size="13" /> Acknowledge all
        </Button>
      </CardHeader>

      <CardContent class="p-0">
        <EmptyState
          v-if="alarms.activeCount === 0"
          title="No active alarms"
          description="Faults and warnings from the robots and their missions appear here and stay until acknowledged. Routine events go to the log below."
          class="m-base"
        >
          <template #icon><BellOff :size="20" class="text-muted" /></template>
        </EmptyState>

        <ul v-else class="divide-y divide-hairline">
          <li
            v-for="alarm in alarms.active"
            :key="alarm.id"
            class="flex flex-wrap items-start gap-x-sm gap-y-xs px-base py-sm sm:flex-nowrap"
          >
            <!-- Fixed width, so every message starts at the same edge. -->
            <span class="w-[5.5rem] shrink-0 pt-[2px]">
              <StatusBadge :tone="SEVERITY_TONE[alarm.severity]" :label="SEVERITY_LABEL[alarm.severity]" />
            </span>
            <!-- Wraps rather than truncates: on a fault the end of the sentence
                 is usually the reason. -->
            <div class="min-w-0 flex-1 basis-[12rem]">
              <p class="break-words text-body-md text-ink">{{ alarm.message }}</p>
              <p class="mt-[2px] flex flex-wrap gap-x-xs text-caption text-muted">
                <RouterLink
                  v-if="alarm.robotId"
                  :to="`/robot/${alarm.robotId}/nav`"
                  class="hover:text-primary hover:underline"
                >
                  {{ alarm.source }}
                </RouterLink>
                <span v-else>{{ alarm.source }}</span>
                <RouterLink
                  v-if="alarm.missionId"
                  :to="`/mission/edit/${alarm.missionId}`"
                  class="hover:text-primary hover:underline"
                >
                  Open mission
                </RouterLink>
              </p>
            </div>
            <span
              class="shrink-0 pt-[3px] font-data text-number-sm text-muted"
              :title="whenTitle(alarm)"
            >
              {{ when(alarm) }}
            </span>
            <Button variant="ghost" size="sm" class="shrink-0" @click="alarms.acknowledge(alarm.id)">
              Acknowledge
            </Button>
          </li>
        </ul>
      </CardContent>
    </Card>

    <Card v-if="historyCount">
      <CardHeader>
        <SectionLabel>Log ({{ historyCount }})</SectionLabel>
        <div class="flex-1" />
        <Button variant="text" size="sm" @click="confirmClear = true">
          <Trash2 :size="13" /> Clear log
        </Button>
      </CardHeader>
      <CardContent class="p-0">
        <ul class="divide-y divide-hairline">
          <li
            v-for="alarm in alarms.history"
            :key="alarm.id"
            class="flex items-start gap-sm px-base py-xs"
          >
            <span class="w-[5.5rem] shrink-0 pt-[2px]">
              <StatusBadge
                :tone="alarm.severity === 'info' ? 'neutral' : SEVERITY_TONE[alarm.severity]"
                :label="SEVERITY_LABEL[alarm.severity]"
              />
            </span>
            <div class="min-w-0 flex-1">
              <p class="break-words text-body-sm text-body">{{ alarm.message }}</p>
              <p class="text-caption text-muted">
                <RouterLink
                  v-if="alarm.robotId"
                  :to="`/robot/${alarm.robotId}/nav`"
                  class="hover:text-primary hover:underline"
                >
                  {{ alarm.source }}
                </RouterLink>
                <span v-else>{{ alarm.source }}</span>
                <template v-if="alarm.acknowledgedAt && alarm.severity !== 'info'">
                  · acknowledged {{ alarmTime(alarm.acknowledgedAt, now) }}
                </template>
              </p>
            </div>
            <span
              class="shrink-0 pt-[2px] font-data text-number-sm text-muted"
              :title="whenTitle(alarm)"
            >
              {{ when(alarm) }}
            </span>
          </li>
        </ul>
      </CardContent>
    </Card>

    <ConfirmDialog
      :open="confirmClear"
      destructive
      title="Clear the log?"
      :description="`Removes ${historyCount} logged event${historyCount === 1 ? '' : 's'} from this browser. Active alarms stay. Mission history on the server is not affected.`"
      confirm-label="Clear log"
      @update:open="(value: boolean) => (confirmClear = value)"
      @cancel="confirmClear = false"
      @confirm="clearHistory"
    />
  </div>
</template>
