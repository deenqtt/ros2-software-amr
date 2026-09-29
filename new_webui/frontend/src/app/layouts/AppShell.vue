<script setup lang="ts">
/**
 * Application shell: rail on the left, header above the scrolling content.
 *
 * Grid rather than the old `calc(100vw - 39rem)` arithmetic, which encoded the
 * sidebar and panel widths as a magic constant and broke the moment the
 * sidebar collapsed.
 */
import { RouterView } from 'vue-router'
import AppSidebar from './AppSidebar.vue'
import AppHeader from './AppHeader.vue'
</script>

<template>
  <div class="flex h-full bg-canvas">
    <AppSidebar />
    <div class="flex min-w-0 flex-1 flex-col">
      <AppHeader />
      <main class="min-h-0 flex-1 overflow-y-auto scrollbar-thin">
        <RouterView />
      </main>
    </div>
  </div>
</template>
