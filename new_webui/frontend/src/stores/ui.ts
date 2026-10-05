/** Operator preferences. Persisted, because the old UI lost everything on refresh. */
import { defineStore } from 'pinia'
import { useLocalStorage, useMediaQuery, usePreferredDark } from '@vueuse/core'
import { computed, ref, watchEffect } from 'vue'

export type Theme = 'light' | 'dark' | 'system'
export type Density = 'compact' | 'default' | 'comfortable'

/**
 * Which layout the screen gets. The same breakpoints as the Tailwind config
 * (md 768, lg 1024), so a template's `md:` and the store agree.
 *
 *   phone    < 768   rail hidden; the menu is a drawer behind the header button
 *   tablet   < 1024  rail shows icons; opening it lays it over the page
 *   desktop          the rail as the operator left it, labels and all
 */
export type Screen = 'phone' | 'tablet' | 'desktop'

export const useUiStore = defineStore('ui', () => {
  // DESIGN.md's default canvas is white; dark is its editorial mode and
  // stays available for night or low-light operation.
  const theme = useLocalStorage<Theme>('amr.ui.theme', 'light')
  const density = useLocalStorage<Density>('amr.ui.density', 'default')
  const navCollapsedSaved = useLocalStorage('amr.ui.navCollapsed', false)
  /**
   * Folded by a page that needs the room — the robot's live map — for as long
   * as it is open. Not saved: leaving the page puts the rail back as the
   * operator had it, and expanding it by hand wins while on the page.
   */
  const navFolded = ref(false)

  const isPhone = useMediaQuery('(max-width: 767px)')
  const isNarrow = useMediaQuery('(max-width: 1023px)')
  const screen = computed<Screen>(() =>
    isPhone.value ? 'phone' : isNarrow.value ? 'tablet' : 'desktop',
  )

  /** Phone: the menu drawer. Never saved; it opens on demand. */
  const drawerOpen = ref(false)
  /**
   * Tablet: the rail opened over the page. Not saved either: on a tablet the
   * page needs the width, so the rail starts as icons every time.
   */
  const railOpen = ref(false)

  const navCollapsed = computed({
    get: () => {
      if (screen.value === 'phone') return false // the drawer always shows labels
      if (screen.value === 'tablet') return !railOpen.value
      return navCollapsedSaved.value || navFolded.value
    },
    set: (value: boolean) => {
      if (screen.value === 'tablet') {
        railOpen.value = !value
        return
      }
      navFolded.value = false
      navCollapsedSaved.value = value
    },
  })

  /** Put away whatever is covering the page: the drawer or the opened rail. */
  function closeNav() {
    drawerOpen.value = false
    railOpen.value = false
  }

  function foldNav(fold: boolean) {
    navFolded.value = fold
  }
  const inspectorOpen = useLocalStorage('amr.ui.inspectorOpen', true)

  const prefersDark = usePreferredDark()
  const resolvedTheme = computed<'light' | 'dark'>(() =>
    theme.value === 'system' ? (prefersDark.value ? 'dark' : 'light') : theme.value,
  )

  watchEffect(() => {
    document.documentElement.classList.toggle('dark', resolvedTheme.value === 'dark')
  })

  function toggleNav() {
    if (screen.value === 'phone') {
      drawerOpen.value = !drawerOpen.value
      return
    }
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
    screen,
    drawerOpen,
    railOpen,
    closeNav,
    inspectorOpen,
    resolvedTheme,
    toggleNav,
    foldNav,
    toggleInspector,
    setTheme,
    cycleTheme,
  }
})
