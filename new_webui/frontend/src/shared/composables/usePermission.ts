/**
 * What the signed-in role may do, for templates.
 *
 * Two tiers matter to the screens: running the robots (operator) and changing
 * the site (admin). Each comes with the sentence to put on a control that is
 * disabled because of it — "Needs the operator role" — because a greyed-out
 * button with no reason reads as broken.
 *
 *   const { canOperate, operateBlocker, canEdit, editBlocker } = usePermission()
 *   <Button :disabled="!canEdit" :title="editBlocker">Delete</Button>
 */
import { computed } from 'vue'
import { useAuthStore } from '@/stores/auth'

export function usePermission() {
  const auth = useAuthStore()
  return {
    canOperate: computed(() => auth.can('operator')),
    operateBlocker: computed(() => auth.blocker('operator')),
    canEdit: computed(() => auth.can('admin')),
    editBlocker: computed(() => auth.blocker('admin')),
  }
}
