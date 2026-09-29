<script setup lang="ts">
/**
 * Theme control.
 *
 * Three states, not two: `system` follows the OS, which matters here because a
 * machine parked next to a robot may be on a scheduled dark/light switch. The
 * resolved theme is shown alongside the choice so `system` is never ambiguous.
 *
 * Expanded, it is a segmented control. Collapsed, there is no room for three
 * options, so it becomes one button that cycles and states the next step in
 * its tooltip.
 */
import { computed } from 'vue'
import { Monitor, Moon, Sun } from 'lucide-vue-next'
import { useUiStore, type Theme } from '@/stores/ui'
import { cn } from '@/shared/lib/utils'

const ui = useUiStore()

const OPTIONS: { value: Theme; label: string; icon: typeof Sun }[] = [
  { value: 'light', label: 'Light', icon: Sun },
  { value: 'dark', label: 'Dark', icon: Moon },
  { value: 'system', label: 'System', icon: Monitor },
]

const current = computed(() => OPTIONS.find((o) => o.value === ui.theme) ?? OPTIONS[0]!)

const collapsedTitle = computed(() => {
  const suffix = ui.theme === 'system' ? ` (following OS: ${ui.resolvedTheme})` : ''
  return `Theme: ${current.value.label}${suffix} — click to change`
})
</script>

<template>
  <!-- Collapsed: one cycling button. -->
  <button
    v-if="ui.navCollapsed"
    type="button"
    :title="collapsedTitle"
    :aria-label="collapsedTitle"
    class="flex h-nav w-full items-center justify-center rounded-control text-muted transition-colors duration-150 ease-out hover:bg-surface-strong hover:text-ink"
    @click="ui.cycleTheme()"
  >
    <component :is="current.icon" :size="16" />
  </button>

  <!-- Expanded: segmented control. The active segment is the only filled
       surface on the rail's footer, so the current choice reads at a glance. -->
  <div
    v-else
    class="flex items-center gap-[2px] rounded-control bg-surface-strong p-[3px]"
    role="radiogroup"
    aria-label="Colour theme"
  >
    <button
      v-for="option in OPTIONS"
      :key="option.value"
      type="button"
      role="radio"
      :aria-checked="ui.theme === option.value"
      :title="
        option.value === 'system'
          ? `Follow the operating system (currently ${ui.resolvedTheme})`
          : option.label
      "
      :class="
        cn(
          'flex h-7 flex-1 items-center justify-center rounded-[6px] transition-colors duration-150 ease-out',
          ui.theme === option.value
            ? 'bg-surface text-ink shadow-soft'
            : 'text-muted hover:text-ink',
        )
      "
      @click="ui.setTheme(option.value)"
    >
      <component :is="option.icon" :size="14" />
      <span class="sr-only">{{ option.label }}</span>
    </button>
  </div>
</template>
