<script setup lang="ts">
/**
 * Notification bell.
 *
 * The count dot is the only place a fault colour appears in the header chrome,
 * so it reads immediately against otherwise monochrome type. The popover lists
 * the three most pressing unacknowledged alarms — faults before warnings — and
 * hands off to the Alarm destination rather than trying to be that screen.
 * Routine events never reach the count; it is red only while a fault is open.
 */
import { computed } from 'vue'
import { RouterLink } from 'vue-router'
import { Bell, Check } from 'lucide-vue-next'
import {
  PopoverContent,
  PopoverPortal,
  PopoverRoot,
  PopoverTrigger,
} from 'reka-ui'
import { useAlarmStore } from '@/stores/alarms'
import { Button } from '@/shared/ui/button'
import SectionLabel from '@/shared/components/SectionLabel.vue'
import { cn } from '@/shared/lib/utils'
import type { AlarmSeverity } from '@/stores/alarms'

const alarms = useAlarmStore()

const recent = computed(() => alarms.active.slice(0, 3))

const SEVERITY_CLASS: Record<AlarmSeverity, string> = {
  fault: 'bg-status-fault',
  warning: 'bg-status-warn',
  info: 'bg-status-run',
}

function relativeTime(at: number): string {
  const seconds = Math.round((Date.now() - at) / 1000)
  if (seconds < 60) return `${seconds}s ago`
  const minutes = Math.round(seconds / 60)
  if (minutes < 60) return `${minutes}m ago`
  return `${Math.round(minutes / 60)}h ago`
}
</script>

<template>
  <PopoverRoot>
    <PopoverTrigger
      class="relative flex h-control w-control items-center justify-center rounded-control text-body transition-colors duration-150 ease-out hover:bg-surface-strong hover:text-ink"
      :aria-label="
        alarms.activeCount > 0 ? `${alarms.activeCount} active alarms` : 'No active alarms'
      "
    >
      <Bell :size="17" />
      <span
        v-if="alarms.activeCount > 0"
        :class="
          cn(
            'absolute right-[5px] top-[5px] flex h-[15px] min-w-[15px] items-center justify-center rounded-chip px-[4px] text-[10px] font-semibold leading-none text-white',
            alarms.faultCount > 0 ? 'bg-status-fault' : 'bg-status-warn',
          )
        "
      >
        {{ alarms.activeCount > 99 ? '99+' : alarms.activeCount }}
      </span>
    </PopoverTrigger>

    <PopoverPortal>
      <PopoverContent
        side="bottom"
        align="end"
        :side-offset="8"
        class="z-50 w-[min(22rem,calc(100vw-2rem))] rounded-surface border border-hairline bg-surface shadow-soft"
      >
        <div class="flex items-center justify-between border-b border-hairline px-base py-sm">
          <SectionLabel>Alarms</SectionLabel>
          <Button
            v-if="alarms.activeCount > 0"
            variant="text"
            size="sm"
            @click="alarms.acknowledgeAll()"
          >
            <Check :size="13" /> Acknowledge all
          </Button>
        </div>

        <div v-if="recent.length === 0" class="px-base py-lg text-center">
          <p class="text-body-sm text-muted">No active alarms.</p>
        </div>

        <ul v-else class="divide-y divide-hairline">
          <li v-for="alarm in recent" :key="alarm.id" class="flex gap-sm px-base py-sm">
            <span
              :class="cn('mt-[6px] h-[6px] w-[6px] shrink-0 rounded-full', SEVERITY_CLASS[alarm.severity])"
              aria-hidden="true"
            />
            <div class="min-w-0 flex-1">
              <p class="line-clamp-2 text-body-sm text-ink">{{ alarm.message }}</p>
              <p class="mt-[2px] text-caption text-muted">
                {{ alarm.source }} · {{ relativeTime(alarm.raisedAt) }}
              </p>
            </div>
          </li>
        </ul>

        <div class="border-t border-hairline px-base py-sm">
          <RouterLink to="/alarm" class="text-body-sm font-semibold text-primary hover:text-primary-active">
            View all alarms
          </RouterLink>
        </div>
      </PopoverContent>
    </PopoverPortal>
  </PopoverRoot>
</template>
