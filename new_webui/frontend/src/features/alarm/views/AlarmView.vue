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
import { useUiStore } from '@/stores/ui'
import { Button } from '@/shared/ui/button'
import { Card, CardContent, CardHeader } from '@/shared/ui/card'
import SectionLabel from '@/shared/components/SectionLabel.vue'
import StatusBadge from '@/shared/components/StatusBadge.vue'
import EmptyState from '@/shared/components/EmptyState.vue'
import ConfirmDialog from '@/shared/components/ConfirmDialog.vue'
import type { StatusTone } from '@/domain/types'
import { alarmAge, alarmTime } from '../alarmTime'

const alarms = useAlarmStore()
const ui = useUiStore()

const SEVERITY_TONE: Record<AlarmSeverity, StatusTone> = {
  fault: 'fault',
  warning: 'warning',
  info: 'active',
}

/** The log on a phone has no badge column; the severity word carries the hue. */
const SEVERITY_TEXT: Record<AlarmSeverity, string> = {
  fault: 'text-status-fault',
  warning: 'text-status-warn',
  info: 'text-muted',
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

/**
 * A phone gets the latest few; the log keeps up to 200 and scrolling past all
 * of them to reach anything below is not what someone checking in wants.
 */
const PHONE_LOG = 20
const showAll = ref(false)
const isPhone = computed(() => ui.screen === 'phone')
const visibleHistory = computed(() =>
  isPhone.value && !showAll.value ? alarms.history.slice(0, PHONE_LOG) : alarms.history,
)

function clearHistory() {
  alarms.clearHistory()
  confirmClear.value = false
}
</script>

<template>
  <div class="space-y-base p-sm sm:p-base md:p-lg">
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
          <!--
            A grid so one DOM serves both layouts. On a phone: badge and time,
            then the message at full width, then links and Acknowledge on the
            row's own last line. From sm up: the single line it always was.
          -->
          <li
            v-for="alarm in alarms.active"
            :key="alarm.id"
            class="grid grid-cols-[minmax(0,1fr)_auto] items-center gap-x-sm gap-y-xs px-base py-sm md:grid-cols-[5.5rem_minmax(0,1fr)_auto_auto] md:grid-rows-[auto_1fr] md:items-start md:gap-y-0"
          >
            <!-- Fixed width from sm, so every message starts at the same edge. -->
            <span class="col-start-1 row-start-1 justify-self-start md:row-span-2 md:pt-[2px]">
              <StatusBadge :tone="SEVERITY_TONE[alarm.severity]" :label="SEVERITY_LABEL[alarm.severity]" />
            </span>
            <!-- Wraps rather than truncates: on a fault the end of the sentence
                 is usually the reason. -->
            <p
              class="col-span-2 col-start-1 row-start-2 break-words text-body-md text-ink md:col-span-1 md:col-start-2 md:row-start-1"
            >
              {{ alarm.message }}
            </p>
            <p
              class="col-start-1 row-start-3 flex flex-wrap gap-x-xs text-caption text-muted md:col-start-2 md:row-start-2 md:mt-[2px]"
            >
              <RouterLink
                v-if="alarm.robotId"
                :to="`/robot/${alarm.robotId}/nav`"
                class="inline-flex items-center hover:text-primary hover:underline touch:min-h-[44px]"
              >
                {{ alarm.source }}
              </RouterLink>
              <span v-else>{{ alarm.source }}</span>
              <RouterLink
                v-if="alarm.missionId"
                :to="`/mission/edit/${alarm.missionId}`"
                class="inline-flex items-center hover:text-primary hover:underline touch:min-h-[44px]"
              >
                Open mission
              </RouterLink>
            </p>
            <span
              class="col-start-2 row-start-1 justify-self-end font-data text-number-sm text-muted md:col-start-3 md:row-span-2 md:pt-[3px]"
              :title="whenTitle(alarm)"
            >
              {{ when(alarm) }}
            </span>
            <Button
              variant="ghost"
              size="sm"
              class="col-start-2 row-start-3 justify-self-end md:col-start-4 md:row-span-2 md:row-start-1"
              @click="alarms.acknowledge(alarm.id)"
            >
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
        <!-- Phone: no badge column, which would take a fifth of the width;
             the severity word in its colour leads the caption instead. -->
        <ul v-if="isPhone" class="divide-y divide-hairline">
          <li v-for="alarm in visibleHistory" :key="alarm.id" class="px-base py-xs">
            <p class="break-words text-body-sm text-body">{{ alarm.message }}</p>
            <p class="text-caption text-muted">
              <span :class="SEVERITY_TEXT[alarm.severity]">{{ SEVERITY_LABEL[alarm.severity] }}</span>
              ·
              <RouterLink
                v-if="alarm.robotId"
                :to="`/robot/${alarm.robotId}/nav`"
                class="hover:text-primary hover:underline"
              >
                {{ alarm.source }}
              </RouterLink>
              <span v-else>{{ alarm.source }}</span>
              ·
              <span class="font-data" :title="whenTitle(alarm)">{{ when(alarm) }}</span>
              <template v-if="alarm.acknowledgedAt && alarm.severity !== 'info'">
                · acknowledged {{ alarmTime(alarm.acknowledgedAt, now) }}
              </template>
            </p>
          </li>
        </ul>
        <ul v-else class="divide-y divide-hairline">
          <li
            v-for="alarm in visibleHistory"
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
        <div v-if="visibleHistory.length < historyCount" class="border-t border-hairline px-base py-xs">
          <Button variant="text" size="sm" @click="showAll = true">Show all {{ historyCount }}</Button>
        </div>
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
