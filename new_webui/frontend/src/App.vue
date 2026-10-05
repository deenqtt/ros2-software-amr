<script setup lang="ts">
/**
 * Application shell.
 *
 * Deliberately thin. The old App.vue was 1,210 lines holding the header, the
 * Overview page, three dialogs, battery colour logic, mode synchronisation and
 * 77 lines of scoped E-STOP CSS (audit section 2.1). Layout belongs to
 * layouts, screens belong to routes.
 */
import { RouterView } from 'vue-router'
import { Toaster } from 'vue-sonner'
import { useUiStore } from '@/stores/ui'

// Instantiate early so the persisted theme is applied on first paint.
useUiStore()
// Run notifications and link alarms start in AppShell, not here: they read the
// fleet, which needs someone signed in, and the sign-in page has nobody yet.
</script>

<template>
  <RouterView />
  <Toaster position="top-right" rich-colors close-button />
</template>
