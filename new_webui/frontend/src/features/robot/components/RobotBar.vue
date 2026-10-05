<script setup lang="ts">
/**
 * The bar across the top of every robot page.
 *
 * Navigation and Details are two views of one machine, so they share one bar:
 * which robot, whether it is reachable, a tab to the other view, and Stop &
 * park — on every robot page, not only the one with the map.
 */
import { RouterLink, useRoute } from 'vue-router'
import { Bot, LayoutDashboard, OctagonX } from 'lucide-vue-next'
import type { RobotConfig } from '@/domain/types'
import type { LinkState } from '@/domain/ros/link'
import { Button } from '@/shared/ui/button'
import LinkIndicator from '@/shared/components/LinkIndicator.vue'
import BlockedTip from '@/shared/components/BlockedTip.vue'
import { usePermission } from '@/shared/composables/usePermission'
import { cn } from '@/shared/lib/utils'

defineProps<{
  robot: RobotConfig
  linkState: LinkState
  attempt: number
  stopPending: boolean
}>()

const emit = defineEmits<{ stop: [] }>()

const route = useRoute()
const { canOperate, operateBlocker } = usePermission()

const TABS = [
  { name: 'robot-nav', label: 'Navigation' },
  { name: 'robot-detail', label: 'Details' },
] as const
</script>

<template>
  <header
    class="flex shrink-0 flex-wrap items-center gap-x-sm gap-y-xs border-b border-hairline bg-surface px-base py-xs"
  >
    <span
      class="flex h-7 w-7 shrink-0 items-center justify-center rounded-full text-white"
      :style="{ backgroundColor: `rgb(var(--robot-accent-${robot.accent}))` }"
    >
      <Bot :size="14" />
    </span>
    <div class="min-w-0">
      <p class="truncate text-title-sm text-ink">{{ robot.name }}</p>
      <!-- Configuration, on the details page; the phone needs the room. -->
      <p class="hidden truncate font-data text-caption text-muted md:block">
        {{ robot.bridgeUrl }}
      </p>
    </div>
    <LinkIndicator :state="linkState" :attempt="attempt" />

    <!-- On a phone the tabs take their own full-width row, last; from md they
         sit inline after the name as before. -->
    <nav
      aria-label="Robot views"
      class="order-last flex w-full rounded-control border border-hairline p-[2px] md:order-none md:inline-flex md:w-auto"
    >
      <RouterLink
        v-for="tab in TABS"
        :key="tab.name"
        :to="{ name: tab.name, params: { robotId: robot.id } }"
        :aria-current="route.name === tab.name ? 'page' : undefined"
        :class="
          cn(
            'flex h-[26px] flex-1 items-center justify-center rounded-[6px] px-sm text-body-sm transition-colors touch:h-[40px] md:flex-none',
            route.name === tab.name ? 'bg-surface-strong text-ink' : 'text-body hover:text-ink',
          )
        "
      >
        {{ tab.label }}
      </RouterLink>
    </nav>

    <div class="ml-auto flex flex-wrap items-center gap-xxs">
      <!-- Says where it goes: robot pages are opened from the dashboard. -->
      <!-- Not on a phone: the menu and the back button already go there. -->
      <Button variant="ghost" size="sm" class="hidden md:inline-flex" as-child>
        <RouterLink to="/dashboard"><LayoutDashboard :size="14" /> Dashboard</RouterLink>
      </Button>
      <!-- Named for what it does. A red octagon labelled "Stop" reads as the
           E-STOP, and this is not that. -->
      <BlockedTip :reason="operateBlocker">
        <Button
          variant="danger"
          size="sm"
          :disabled="stopPending || !canOperate"
          title="Cancel the goal, cancel the mission, and park the robot. Not the physical E-STOP."
          aria-label="Stop and park"
          @click="emit('stop')"
        >
          <OctagonX :size="13" />
          <span class="sm:hidden">Stop</span>
          <span class="hidden sm:inline">Stop &amp; park</span>
        </Button>
      </BlockedTip>
    </div>
  </header>
</template>
