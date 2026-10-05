<script setup lang="ts">
/**
 * Page header: title on the left, notification bell and account on the right.
 *
 * 64px, matching DESIGN.md's top-nav height exactly — that number survives
 * the density reduction because a header is chrome, not content, and cutting
 * it would crowd the title against the hairline.
 *
 * The title is the page's only large type. Everything else in the chrome sits
 * at body or label size, so the eye lands on "where am I" first.
 */
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import { Menu } from 'lucide-vue-next'
import { useUiStore } from '@/stores/ui'
import NotificationBell from './NotificationBell.vue'
import UserMenu from './UserMenu.vue'

const route = useRoute()
const ui = useUiStore()

const title = computed(() => (typeof route.meta.title === 'string' ? route.meta.title : ''))
const subtitle = computed(() =>
  typeof route.meta.subtitle === 'string' ? route.meta.subtitle : '',
)
</script>

<template>
  <header
    class="flex h-header shrink-0 items-center gap-sm border-b border-hairline bg-canvas px-base md:gap-base md:px-lg"
  >
    <!-- Phone only: the rail is gone, so the menu opens from here. -->
    <button
      v-if="ui.screen === 'phone'"
      type="button"
      aria-label="Open menu"
      :aria-expanded="ui.drawerOpen"
      class="-ml-xs flex h-11 w-11 shrink-0 items-center justify-center rounded-control text-body transition-colors hover:bg-surface-strong hover:text-ink"
      @click="ui.toggleNav()"
    >
      <Menu :size="20" />
    </button>
    <div class="min-w-0 flex-1">
      <h1 class="truncate text-title-md text-ink">{{ title }}</h1>
      <p v-if="subtitle" class="hidden truncate text-caption text-muted sm:block">
        {{ subtitle }}
      </p>
    </div>

    <NotificationBell />
    <UserMenu />
  </header>
</template>
