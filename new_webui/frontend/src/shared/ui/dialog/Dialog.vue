<script setup lang="ts">
/**
 * Modal dialog.
 *
 * Distinct from ConfirmDialog, which is an AlertDialog: that one interrupts to
 * ask a yes/no question about something irreversible and traps focus on the
 * two answers. This one hosts a form, so it is dismissible and its content
 * scrolls.
 */
import {
  DialogClose,
  DialogContent,
  DialogDescription,
  DialogOverlay,
  DialogPortal,
  DialogRoot,
  DialogTitle,
} from 'reka-ui'
import { X } from 'lucide-vue-next'
import { cn } from '@/shared/lib/utils'

const props = withDefaults(
  defineProps<{
    open: boolean
    title: string
    description?: string
    /** Blocks dismissal while a submit is in flight. */
    pending?: boolean
    class?: string
  }>(),
  { pending: false },
)

const emit = defineEmits<{ 'update:open': [value: boolean] }>()

function onOpenChange(value: boolean) {
  if (props.pending && !value) return
  emit('update:open', value)
}
</script>

<template>
  <DialogRoot :open="props.open" @update:open="onOpenChange">
    <DialogPortal>
      <!--
        The page behind a modal is blurred, not just dimmed. Dimming alone
        leaves the table legible enough to keep reading, which is the opposite
        of what a modal is for; blur removes it as a place to look while
        keeping enough shape that the operator does not lose their bearings.

        This is the one place backdrop-filter is allowed. As a persistent
        decoration it is a continuous GPU cost on a machine that is also
        running the robot stack — here it exists only while the dialog is open.
      -->
      <DialogOverlay
        class="fixed inset-0 z-50 bg-[#0a0b0d]/45 backdrop-blur-[3px] data-[state=open]:animate-in data-[state=open]:fade-in-0"
      />
      <DialogContent
        :class="
          cn(
            'fixed left-1/2 top-1/2 z-50 flex max-h-[calc(100vh-4rem)] w-[min(30rem,calc(100vw-2rem))] -translate-x-1/2 -translate-y-1/2 flex-col',
            'rounded-surface border border-hairline bg-surface shadow-soft',
            props.class,
          )
        "
      >
        <div class="flex items-start gap-base border-b border-hairline px-lg py-base">
          <div class="min-w-0 flex-1">
            <DialogTitle class="text-title-md text-ink">{{ props.title }}</DialogTitle>
            <DialogDescription v-if="props.description" class="mt-xxs text-body-sm text-muted">
              {{ props.description }}
            </DialogDescription>
          </div>
          <DialogClose
            :disabled="props.pending"
            aria-label="Close"
            class="-mr-xs -mt-xxs flex h-8 w-8 shrink-0 items-center justify-center rounded-control text-muted transition-colors duration-150 ease-out hover:bg-surface-strong hover:text-ink disabled:opacity-40"
          >
            <X :size="16" />
          </DialogClose>
        </div>

        <div class="min-h-0 flex-1 overflow-y-auto scrollbar-thin px-lg py-base">
          <slot />
        </div>

        <div
          v-if="$slots.footer"
          class="flex justify-end gap-xs border-t border-hairline px-lg py-base"
        >
          <slot name="footer" />
        </div>
      </DialogContent>
    </DialogPortal>
  </DialogRoot>
</template>
