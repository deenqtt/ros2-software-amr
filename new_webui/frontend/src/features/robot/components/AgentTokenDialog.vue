<script setup lang="ts">
/**
 * Shows a freshly generated agent token, once.
 *
 * The server keeps only a hash, so this is the only moment the plaintext
 * exists. It lives in the parent's state while the dialog is open and the
 * parent clears it on close; nothing here persists it anywhere.
 */
import { ref, watch } from 'vue'
import { Check, Copy } from 'lucide-vue-next'
import { Dialog } from '@/shared/ui/dialog'
import { Button } from '@/shared/ui/button'

const props = defineProps<{
  open: boolean
  token: string
  robotName?: string
}>()

const emit = defineEmits<{ 'update:open': [value: boolean] }>()

const copied = ref(false)
const copyFailed = ref(false)
const tokenEl = ref<HTMLElement | null>(null)

watch(
  () => props.open,
  (open) => {
    if (!open) {
      copied.value = false
      copyFailed.value = false
    }
  },
)

function selectToken() {
  const el = tokenEl.value
  const selection = window.getSelection()
  if (!el || !selection) return
  const range = document.createRange()
  range.selectNodeContents(el)
  selection.removeAllRanges()
  selection.addRange(range)
}

async function copy() {
  copyFailed.value = false
  try {
    if (!navigator.clipboard?.writeText) throw new Error('no clipboard')
    await navigator.clipboard.writeText(props.token)
    copied.value = true
  } catch {
    // Clipboard needs a secure context; on plain http the operator copies by hand.
    copied.value = false
    copyFailed.value = true
    selectToken()
  }
}
</script>

<template>
  <Dialog
    :open="props.open"
    title="Agent token"
    :description="props.robotName ? `For ${props.robotName}` : undefined"
    @update:open="(value: boolean) => emit('update:open', value)"
  >
    <p
      ref="tokenEl"
      data-testid="agent-token"
      class="select-all break-all rounded-control border border-hairline bg-surface-strong p-sm font-data text-body-sm text-ink"
      @click="selectToken"
    >
      {{ props.token }}
    </p>
    <p class="mt-sm text-body-sm text-body">
      This token is shown only once. Put it in /etc/amr/robot.env as AMR_AGENT_TOKEN on the robot,
      then restart amr-agent.
    </p>
    <p v-if="copyFailed" role="status" class="mt-xs text-caption text-status-warn">
      Could not copy automatically. The token is selected, so copy it by hand.
    </p>
    <template #footer>
      <Button variant="outline" @click="copy">
        <component :is="copied ? Check : Copy" :size="14" />
        {{ copied ? 'Copied' : 'Copy' }}
      </Button>
      <Button @click="emit('update:open', false)">Done</Button>
    </template>
  </Dialog>
</template>
