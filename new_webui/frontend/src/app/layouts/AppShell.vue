<script setup lang="ts">
/**
 * Application shell: rail on the left, header above the scrolling content.
 *
 * Grid rather than the old `calc(100vw - 39rem)` arithmetic, which encoded the
 * sidebar and panel widths as a magic constant and broke the moment the
 * sidebar collapsed.
 */
import { watch } from 'vue'
import { RouterView, useRoute } from 'vue-router'
import { onKeyStroke } from '@vueuse/core'
import { useUiStore } from '@/stores/ui'
import { useRunNotifications } from '@/app/runNotifications'
import { useLinkAlarms } from '@/app/linkAlarms'
import AppSidebar from './AppSidebar.vue'
import AppHeader from './AppHeader.vue'

// Here rather than on one page: a robot reaching a stop or failing matters to
// whoever is watching, whichever screen they are on. In the shell rather than
// App.vue because both read the fleet, and only a signed-in person may.
useRunNotifications()
// Also where link monitoring starts, so every page sees real link state.
useLinkAlarms()

const ui = useUiStore()
const route = useRoute()

// Choosing a page is the end of the trip through the menu.
watch(
  () => route.fullPath,
  () => ui.closeNav(),
)
onKeyStroke('Escape', () => ui.closeNav())
</script>

<template>
  <div class="flex h-full bg-canvas">
    <AppSidebar v-if="ui.screen === 'desktop'" />

    <!-- Tablet: the icon rail keeps its place in the layout; opened, it lays
         over the page instead of pushing it, so a map does not shrink. The
         rail itself animates its width; the scrim fades. -->
    <template v-else-if="ui.screen === 'tablet'">
      <div class="w-sidebar-collapsed shrink-0" aria-hidden="true" />
      <Transition
        enter-active-class="transition-opacity duration-200 ease-out motion-reduce:transition-none"
        leave-active-class="transition-opacity duration-200 ease-in motion-reduce:transition-none"
        enter-from-class="opacity-0"
        leave-to-class="opacity-0"
      >
        <div
          v-if="ui.railOpen"
          class="fixed inset-0 z-30 bg-[#0a0b0d]/20"
          aria-hidden="true"
          @click="ui.closeNav()"
        />
      </Transition>
      <AppSidebar mode="overlay" />
    </template>

    <!-- Phone: no rail at all. The menu is a drawer behind the header button:
         the panel slides in from the edge it belongs to, the scrim fades. -->
    <template v-else>
      <Transition
        enter-active-class="transition-opacity duration-[250ms] ease-out motion-reduce:transition-none"
        leave-active-class="transition-opacity duration-200 ease-in motion-reduce:transition-none"
        enter-from-class="opacity-0"
        leave-to-class="opacity-0"
      >
        <div
          v-if="ui.drawerOpen"
          class="fixed inset-0 z-50 bg-[#0a0b0d]/40"
          aria-hidden="true"
          @click="ui.closeNav()"
        />
      </Transition>
      <Transition
        enter-active-class="transition-transform duration-[250ms] ease-out motion-reduce:transition-none"
        leave-active-class="transition-transform duration-200 ease-in motion-reduce:transition-none"
        enter-from-class="-translate-x-full"
        leave-to-class="-translate-x-full"
      >
        <div
          v-if="ui.drawerOpen"
          class="fixed inset-y-0 left-0 z-50 flex shadow-soft"
          role="dialog"
          aria-modal="true"
          aria-label="Menu"
        >
          <AppSidebar mode="drawer" />
        </div>
      </Transition>
    </template>

    <div class="flex min-w-0 flex-1 flex-col">
      <AppHeader />
      <main class="min-h-0 flex-1 overflow-y-auto scrollbar-thin">
        <RouterView />
      </main>
    </div>
  </div>
</template>
