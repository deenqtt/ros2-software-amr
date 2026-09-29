<script setup lang="ts">
/**
 * Confirmation for a destructive or safety-relevant action.
 *
 * The old UI confirmed exactly one action out of twelve; a single unconfirmed
 * click could delete every keepout zone on a map. Anything irreversible routes
 * through this, and the message names the robot or object rather than saying
 * "this item".
 */
import {
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogOverlay,
  AlertDialogPortal,
  AlertDialogRoot,
  AlertDialogTitle,
} from 'reka-ui'
import { buttonVariants } from '@/shared/ui/button'
import { cn } from '@/shared/lib/utils'

const props = withDefaults(
  defineProps<{
    open: boolean
    title: string
    description: string
    confirmLabel?: string
    cancelLabel?: string
    destructive?: boolean
    pending?: boolean
    /**
     * The action cannot succeed, and the caller already knows it.
     *
     * Offering a live button that the server will refuse turns a clear
     * precondition into a failed request and a toast. When this is set the
     * confirm is disabled and the caller is expected to put the way forward in
     * the #actions slot.
     */
    blocked?: boolean
  }>(),
  {
    confirmLabel: 'Confirm',
    cancelLabel: 'Cancel',
    destructive: false,
    pending: false,
    blocked: false,
  },
)

const emit = defineEmits<{
  'update:open': [value: boolean]
  confirm: []
  cancel: []
}>()

/**
 * Hand the confirmation to the caller before reka-ui closes the dialog.
 *
 * Bound on the capture phase, and that is the whole point. reka-ui closes on
 * action through its own click handler, and it ran first: every caller here
 * reads what to act on out of the same ref the close handler clears, so the
 * work was handed an empty box and returned in silence. The dialog shut,
 * nothing was deleted, and no error was ever shown. It cost two bug reports —
 * maps and stations — because both go through this one dialog.
 *
 * Capture runs before the bubble-phase handler on the same element, so the
 * caller now sees `confirm` first and can mark itself busy. Its own `pending`
 * then keeps the dialog up while the work runs: the button reads "Working…"
 * and whoever owns the action closes the dialog when it is actually done.
 *
 * preventDefault does not work here — reka-ui does not close through the
 * default action — which is why the order is fixed instead of the close being
 * suppressed. The emit order is asserted in this component's test.
 */
function onConfirm() {
  emit('confirm')
}

</script>

<template>
  <AlertDialogRoot :open="props.open" @update:open="emit('update:open', $event)">
    <AlertDialogPortal>
      <!-- Blurred, not merely dimmed — see Dialog.vue for why. -->
      <AlertDialogOverlay class="fixed inset-0 z-50 bg-[#0a0b0d]/45 backdrop-blur-[3px]" />
      <AlertDialogContent
        class="fixed left-1/2 top-1/2 z-50 w-[min(26rem,calc(100vw-2rem))] -translate-x-1/2 -translate-y-1/2 rounded-surface border border-hairline bg-surface p-lg shadow-soft"
      >
        <AlertDialogTitle class="text-title-sm text-ink">{{ props.title }}</AlertDialogTitle>
        <AlertDialogDescription class="mt-xs text-body-sm leading-relaxed text-body">
          {{ props.description }}
        </AlertDialogDescription>

        <slot />

        <div class="mt-base flex justify-end gap-xs">
          <!-- Where a blocked action puts its unblocking step. -->
          <slot name="actions" />
          <AlertDialogCancel
            :class="cn(buttonVariants({ variant: 'secondary', size: 'sm' }))"
            :disabled="props.pending"
            @click="emit('cancel')"
          >
            {{ props.cancelLabel }}
          </AlertDialogCancel>
          <AlertDialogAction
            :class="
              cn(buttonVariants({ variant: props.destructive ? 'danger' : 'primary', size: 'sm' }))
            "
            :disabled="props.pending || props.blocked"
            @click.capture="onConfirm"
          >
            {{ props.pending ? 'Working…' : props.confirmLabel }}
          </AlertDialogAction>
        </div>
      </AlertDialogContent>
    </AlertDialogPortal>
  </AlertDialogRoot>
</template>
