<script setup lang="ts">
/**
 * Page header: title on the left, notification bell on the right.
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
import NotificationBell from './NotificationBell.vue'

const route = useRoute()

const title = computed(() => (typeof route.meta.title === 'string' ? route.meta.title : ''))
const subtitle = computed(() =>
  typeof route.meta.subtitle === 'string' ? route.meta.subtitle : '',
)
</script>

<template>
  <header
    class="flex h-header shrink-0 items-center gap-base border-b border-hairline bg-canvas px-lg"
  >
    <div class="min-w-0 flex-1">
      <h1 class="truncate text-title-md text-ink">{{ title }}</h1>
      <p v-if="subtitle" class="truncate text-caption text-muted">{{ subtitle }}</p>
    </div>

    <NotificationBell />
  </header>
</template>
