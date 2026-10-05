/**
 * Why a precise-pointer map task (drawing zones, placing stations) is off on
 * this screen. On a phone such tasks are disabled with the reason shown next
 * to the control, not in a tooltip: touch has no hover, so a tooltip never
 * appears. Pages combine it with usePermission().editBlocker, role reason
 * first, since a role change is the one a phone user cannot work around.
 *
 *   const { tooSmall, reason } = useScreenBlocker('Drawing zones')
 *   // on a phone: 'Drawing zones needs a tablet or laptop.'
 */
import { computed, type ComputedRef } from 'vue'
import { useUiStore } from '@/stores/ui'

export function useScreenBlocker(task: string): {
  tooSmall: ComputedRef<boolean>
  reason: ComputedRef<string>
} {
  const ui = useUiStore()
  const tooSmall = computed(() => ui.screen === 'phone')
  const reason = computed(() => (tooSmall.value ? `${task} needs a tablet or laptop.` : ''))
  return { tooSmall, reason }
}
