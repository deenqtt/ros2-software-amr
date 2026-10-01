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
import { useRunNotifications } from '@/app/runNotifications'

// Instantiate early so the persisted theme is applied on first paint.
useUiStore()
// Here rather than on one page: a robot reaching a stop or failing matters to
// whoever is watching, whichever screen they are on.
useRunNotifications()
</script>

<template>
  <RouterView />
  <Toaster position="top-right" rich-colors close-button />
</template>
