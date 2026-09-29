<script setup lang="ts">
/**
 * Navigation rail.
 *
 * Reads as the quiet side of the page: soft surface, hairline edge, no shadow.
 * The active item is the only blue on the rail — DESIGN.md keeps the brand
 * voltage scarce, so spending it on "where am I" is the highest-value use here.
 *
 * The collapse control sits on the rail's right edge, level with the top of the
 * nav list. That position works identically in both states, which a footer
 * button did not: collapsed, a bottom-anchored toggle is the furthest possible
 * point from where the eye already is.
 *
 * Collapsed, the rail drops to 64px and shows icons only, so every item keeps a
 * title attribute.
 */
import { RouterLink } from 'vue-router'
import { Bot, ChevronLeft, ChevronRight } from 'lucide-vue-next'
import { NAV_GROUPS } from '@/app/navigation'
import { useAlarmStore } from '@/stores/alarms'
import { useUiStore } from '@/stores/ui'
import { cn } from '@/shared/lib/utils'
import ThemeToggle from './ThemeToggle.vue'

const ui = useUiStore()
const alarms = useAlarmStore()

function badgeCount(key?: 'alarms'): number {
  return key === 'alarms' ? alarms.activeCount : 0
}
</script>

<template>
  <aside
    :class="
      cn(
        'relative flex shrink-0 flex-col border-r border-hairline bg-surface-soft transition-[width] duration-200 ease-out',
        ui.navCollapsed ? 'w-sidebar-collapsed' : 'w-sidebar',
      )
    "
  >
    <!-- Brand. The header carries the page title, so identity lives here. -->
    <div
      :class="
        cn(
          'flex h-header shrink-0 items-center border-b border-hairline',
          ui.navCollapsed ? 'justify-center px-0' : 'gap-sm px-base',
        )
      "
    >
      <span
        class="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-primary text-on-primary"
      >
        <Bot :size="16" />
      </span>
      <span v-if="!ui.navCollapsed" class="truncate text-title-sm text-ink">AMR Control</span>
    </div>

    <!-- Collapse control, straddling the rail's edge. Same place in both
         states, so the escape hatch never moves. -->
    <button
      type="button"
      :title="ui.navCollapsed ? 'Expand sidebar' : 'Collapse sidebar'"
      :aria-label="ui.navCollapsed ? 'Expand sidebar' : 'Collapse sidebar'"
      :aria-expanded="!ui.navCollapsed"
      class="absolute -right-[11px] top-[78px] z-10 flex h-[22px] w-[22px] items-center justify-center rounded-full border border-hairline bg-surface text-muted shadow-soft transition-colors duration-150 ease-out hover:border-primary hover:text-primary"
      @click="ui.toggleNav()"
    >
      <ChevronRight v-if="ui.navCollapsed" :size="13" />
      <ChevronLeft v-else :size="13" />
    </button>

    <nav class="flex-1 overflow-y-auto scrollbar-thin px-xs py-sm">
      <template v-for="(group, index) in NAV_GROUPS" :key="group.id">
        <div v-if="index > 0" class="my-sm border-t border-hairline" role="separator" />

        <RouterLink
          v-for="item in group.items"
          :key="item.to"
          :to="item.to"
          :title="item.label"
          :class="
            cn(
              'group relative mb-[2px] flex h-nav items-center rounded-control text-body-md font-medium text-body',
              'transition-colors duration-150 ease-out hover:bg-surface-strong hover:text-ink',
              ui.navCollapsed ? 'justify-center px-0' : 'gap-sm px-sm',
            )
          "
          active-class="!bg-primary/10 !text-primary"
        >
          <component :is="item.icon" :size="17" class="shrink-0" />
          <span v-if="!ui.navCollapsed" class="flex-1 truncate">{{ item.label }}</span>

          <!-- Count reads as a fault, not as decoration. -->
          <span
            v-if="badgeCount(item.badgeKey) > 0"
            :class="
              cn(
                'rounded-chip bg-status-fault px-[6px] py-[1px] text-label text-white',
                ui.navCollapsed && 'absolute right-[8px] top-[5px] px-[4px]',
              )
            "
          >
            {{ badgeCount(item.badgeKey) }}
          </span>
        </RouterLink>
      </template>
    </nav>

    <div class="border-t border-hairline p-xs">
      <ThemeToggle />
    </div>
  </aside>
</template>
