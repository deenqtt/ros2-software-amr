<script setup lang="ts">
/**
 * Change your own password.
 *
 * Asks for the current one, so a terminal left signed in cannot be used to lock
 * its owner out. The server signs out every other browser on success; this one
 * stays in, and the dialog says so.
 */
import { computed, ref, watch } from 'vue'
import { toast } from 'vue-sonner'
import { Dialog } from '@/shared/ui/dialog'
import { Input } from '@/shared/ui/input'
import { FormField } from '@/shared/ui/label'
import { Button } from '@/shared/ui/button'
import { authApi, FieldError } from '@/shared/api/auth'

const PASSWORD_MIN = 10

const props = defineProps<{ open: boolean }>()
const emit = defineEmits<{ 'update:open': [value: boolean] }>()

const current = ref('')
const next = ref('')
const repeat = ref('')
const pending = ref(false)
const attempted = ref(false)
const serverError = ref<{ field: string | null; message: string } | null>(null)

watch(
  () => props.open,
  (open) => {
    if (!open) return
    current.value = ''
    next.value = ''
    repeat.value = ''
    attempted.value = false
    serverError.value = null
  },
)

const errors = computed(() => ({
  current_password: current.value ? '' : 'Enter your current password.',
  new_password:
    next.value.length < PASSWORD_MIN
      ? `At least ${PASSWORD_MIN} characters.`
      : next.value === current.value
        ? 'Choose a password different from the current one.'
        : '',
  repeat: repeat.value === next.value ? '' : 'The two new passwords do not match.',
}))

function errorFor(field: 'current_password' | 'new_password' | 'repeat'): string | undefined {
  if (serverError.value?.field === field) return serverError.value.message
  if (!attempted.value) return undefined
  return errors.value[field] || undefined
}

async function onSubmit(): Promise<void> {
  attempted.value = true
  serverError.value = null
  if (Object.values(errors.value).some(Boolean)) return
  pending.value = true
  try {
    await authApi.changePassword(current.value, next.value)
    toast.success('Password changed. Other browsers signed in as you have been signed out.')
    emit('update:open', false)
  } catch (error) {
    serverError.value =
      error instanceof FieldError
        ? { field: error.field, message: error.message }
        : { field: null, message: error instanceof Error ? error.message : 'Could not change it.' }
  } finally {
    pending.value = false
  }
}
</script>

<template>
  <Dialog
    :open="props.open"
    :pending="pending"
    title="Change password"
    description="Other browsers signed in as you will be signed out. This one stays signed in."
    @update:open="emit('update:open', $event)"
  >
    <form id="password-form" class="space-y-base" novalidate @submit.prevent="onSubmit">
      <FormField label="Current password" required :error="errorFor('current_password')">
        <template #default="{ id, invalid }">
          <Input
            :id="id"
            v-model="current"
            type="password"
            autocomplete="current-password"
            :invalid="invalid"
          />
        </template>
      </FormField>
      <FormField
        label="New password"
        required
        :hint="`At least ${PASSWORD_MIN} characters. A short sentence is easier to type and harder to guess.`"
        :error="errorFor('new_password')"
      >
        <template #default="{ id, invalid }">
          <Input
            :id="id"
            v-model="next"
            type="password"
            autocomplete="new-password"
            :invalid="invalid"
          />
        </template>
      </FormField>
      <FormField label="New password, again" required :error="errorFor('repeat')">
        <template #default="{ id, invalid }">
          <Input
            :id="id"
            v-model="repeat"
            type="password"
            autocomplete="new-password"
            :invalid="invalid"
          />
        </template>
      </FormField>
      <p
        v-if="serverError && serverError.field === null"
        class="text-body-sm text-status-fault"
        role="alert"
      >
        {{ serverError.message }}
      </p>
    </form>

    <template #footer>
      <Button variant="outline" :disabled="pending" @click="emit('update:open', false)">
        Cancel
      </Button>
      <Button type="submit" form="password-form" :disabled="pending">
        {{ pending ? 'Saving…' : 'Change password' }}
      </Button>
    </template>
  </Dialog>
</template>
