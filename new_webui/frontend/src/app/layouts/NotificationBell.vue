<script setup lang="ts">
/**
 * Notification bell.
 *
 * The count dot is the only place a fault colour appears in the header chrome,
 * so it reads immediately against otherwise monochrome type. The popover lists
 * the three most pressing unacknowledged alarms — faults before warnings — and
 * hands off to the Alarm destination rather than trying to be that screen.
 * Routine events never reach the count; it is red only while a fault is open.
 *
 * On a phone there is no popover: the bell is a link to the Alarm screen. A
 * floating panel that nearly fills a phone's width only covers the page, and
 * the full screen is easier to read and scroll — the usual pattern for a
 * notification icon on mobile. With nothing active, the popover is one line.
 */
import { computed } from 'vue'
import { RouterLink } from 'vue-router'
import { Bell, Check, CheckCircle2 } from 'lucide-vue-next'
import { PopoverContent, PopoverPortal, PopoverRoot, PopoverTrigger } from 'reka-ui'
import { useAlarmStore } from '@/stores/alarms'
import { useUiStore } from '@/stores/ui'
import { Button } from '@/shared/ui/button'
import SectionLabel from '@/shared/components/SectionLabel.vue'
import { cn } from '@/shared/lib/utils'
import type { AlarmSeverity } from '@/stores/alarms'

const alarms = useAlarmStore()
const ui = useUiStore()

const triggerClass =
  'relative flex h-control w-control items-center justify-center rounded-control text-body transition-colors duration-150 ease-out hover:bg-surface-strong hover:text-ink touch:h-[44px] touch:w-[44px]'

const label = computed(() =>
  alarms.activeCount > 0 ? `${alarms.activeCount} active alarms` : 'No active alarms',
)

const badgeClass = computed(() =>
  cn(
    'absolute right-[5px] top-[5px] flex h-[15px] min-w-[15px] items-center justify-center rounded-chip px-[4px] text-[10px] font-semibold leading-none text-white touch:right-[7px] touch:top-[7px]',
    alarms.faultCount > 0 ? 'bg-status-fault' : 'bg-status-warn',
  ),
)

const badgeText = computed(() => (alarms.activeCount > 99 ? '99+' : String(alarms.activeCount)))

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
  <!-- Phone: straight to the Alarm screen. -->
  <RouterLink v-if="ui.screen === 'phone'" to="/alarm" :class="triggerClass" :aria-label="label">
    <Bell :size="18" />
    <span v-if="alarms.activeCount > 0" :class="badgeClass">{{ badgeText }}</span>
  </RouterLink>

  <PopoverRoot v-else>
    <PopoverTrigger :class="triggerClass" :aria-label="label">
      <Bell :size="17" />
      <span v-if="alarms.activeCount > 0" :class="badgeClass">{{ badgeText }}</span>
    </PopoverTrigger>

    <PopoverPortal>
      <PopoverContent
        side="bottom"
        align="end"
        :side-offset="8"
        :class="
          cn(
            'z-50 rounded-surface border border-hairline bg-surface shadow-soft',
            recent.length === 0 ? 'w-auto' : 'w-[min(22rem,calc(100vw-2rem))]',
          )
        "
      >
        <!-- Nothing active: one line, not a panel announcing an empty list. -->
        <div
          v-if="recent.length === 0"
          class="flex items-center gap-sm whitespace-nowrap px-base py-sm"
        >
          <CheckCircle2 :size="15" class="shrink-0 text-status-ok" />
          <span class="flex-1 text-body-sm text-ink">All clear</span>
          <RouterLink
            to="/alarm"
            class="text-body-sm font-semibold text-primary hover:text-primary-active"
          >
            Open alarm log
          </RouterLink>
        </div>

        <template v-else>
          <div class="flex items-center justify-between border-b border-hairline px-base py-sm">
            <SectionLabel>Alarms</SectionLabel>
            <Button variant="text" size="sm" @click="alarms.acknowledgeAll()">
              <Check :size="13" /> Acknowledge all
            </Button>
          </div>

          <ul class="divide-y divide-hairline">
            <li v-for="alarm in recent" :key="alarm.id" class="flex gap-sm px-base py-sm">
              <span
                :class="
                  cn(
                    'mt-[6px] h-[6px] w-[6px] shrink-0 rounded-full',
                    SEVERITY_CLASS[alarm.severity],
                  )
                "
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
            <RouterLink
              to="/alarm"
              class="text-body-sm font-semibold text-primary hover:text-primary-active"
            >
              View all alarms
            </RouterLink>
          </div>
        </template>
      </PopoverContent>
    </PopoverPortal>
  </PopoverRoot>
</template>
