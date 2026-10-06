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
import { computed } from 'vue'
import { RouterLink } from 'vue-router'
import { ChevronLeft, ChevronRight, X } from 'lucide-vue-next'
import BrandMark from '@/shared/components/BrandMark.vue'
import { navGroupsFor } from '@/app/navigation'
import { useAlarmStore } from '@/stores/alarms'
import { useAuthStore } from '@/stores/auth'
import { useUiStore } from '@/stores/ui'
import { cn } from '@/shared/lib/utils'
import ThemeToggle from './ThemeToggle.vue'

/**
 * inline   desktop: part of the layout, pushes the page
 * overlay  tablet: fixed over the page, so opening it does not squeeze the map
 * drawer   phone: inside the menu drawer, always with labels
 */
const props = withDefaults(defineProps<{ mode?: 'inline' | 'overlay' | 'drawer' }>(), {
  mode: 'inline',
})

const ui = useUiStore()
const alarms = useAlarmStore()
const auth = useAuthStore()

const groups = computed(() => navGroupsFor((role) => auth.can(role)))

function badgeCount(key?: 'alarms'): number {
  return key === 'alarms' ? alarms.activeCount : 0
}
</script>

<template>
  <aside
    :class="
      cn(
        'flex shrink-0 flex-col border-r border-hairline bg-surface-soft transition-[width] duration-200 ease-out',
        props.mode === 'inline' && 'relative',
        props.mode === 'overlay' && 'fixed inset-y-0 left-0 z-40',
        props.mode === 'overlay' && !ui.navCollapsed && 'shadow-soft',
        props.mode === 'drawer' && 'relative h-full w-[min(18rem,85vw)]',
        props.mode !== 'drawer' && (ui.navCollapsed ? 'w-sidebar-collapsed' : 'w-sidebar'),
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
      <BrandMark :size="32" />
      <span v-if="!ui.navCollapsed" class="flex-1 truncate text-title-sm text-ink">
        AMR Control
      </span>
      <button
        v-if="props.mode === 'drawer'"
        type="button"
        aria-label="Close menu"
        class="flex h-10 w-10 items-center justify-center rounded-control text-muted transition-colors hover:bg-surface-strong hover:text-ink"
        @click="ui.closeNav()"
      >
        <X :size="18" />
      </button>
    </div>

    <!-- Collapse control, straddling the rail's edge. Same place in both
         states, so the escape hatch never moves. -->
    <button
      v-if="props.mode !== 'drawer'"
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
      <template v-for="(group, index) in groups" :key="group.id">
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
