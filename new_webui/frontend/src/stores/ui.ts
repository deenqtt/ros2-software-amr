/** Operator preferences. Persisted, because the old UI lost everything on refresh. */
import { defineStore } from 'pinia'
import { useLocalStorage, usePreferredDark } from '@vueuse/core'
import { computed, watchEffect } from 'vue'

export type Theme = 'light' | 'dark' | 'system'
export type Density = 'compact' | 'default' | 'comfortable'

export const useUiStore = defineStore('ui', () => {
  // DESIGN.md's default canvas is white; dark is its editorial mode and
  // stays available for night or low-light operation.
  const theme = useLocalStorage<Theme>('amr.ui.theme', 'light')
  const density = useLocalStorage<Density>('amr.ui.density', 'default')
  const navCollapsed = useLocalStorage('amr.ui.navCollapsed', false)
  const inspectorOpen = useLocalStorage('amr.ui.inspectorOpen', true)

  const prefersDark = usePreferredDark()
  const resolvedTheme = computed<'light' | 'dark'>(() =>
    theme.value === 'system' ? (prefersDark.value ? 'dark' : 'light') : theme.value,
  )

  watchEffect(() => {
    document.documentElement.classList.toggle('dark', resolvedTheme.value === 'dark')
  })

  function toggleNav() {
    navCollapsed.value = !navCollapsed.value
  }

  const THEME_ORDER: Theme[] = ['light', 'dark', 'system']

  function setTheme(next: Theme) {
    theme.value = next
  }

  /** Used by the collapsed rail, where there is no room for three options. */
  function cycleTheme() {
    const index = THEME_ORDER.indexOf(theme.value)
    theme.value = THEME_ORDER[(index + 1) % THEME_ORDER.length] ?? 'light'
  }

  function toggleInspector() {
    inspectorOpen.value = !inspectorOpen.value
  }

  return {
    theme,
    density,
    navCollapsed,
    inspectorOpen,
    resolvedTheme,
    toggleNav,
    toggleInspector,
    setTheme,
    cycleTheme,
  }
})
