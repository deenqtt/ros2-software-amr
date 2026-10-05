<script setup lang="ts">
/**
 * Add / edit a robot.
 *
 * One dialog for both, because the fields and the rules are identical and two
 * copies drift. The mode only changes the title and the submit label.
 *
 * Errors appear on blur and on submit, never on every keystroke — validating
 * while someone is still typing a URL flags it as broken before they have
 * finished writing it.
 */
import { computed, ref, watch } from 'vue'
import { Bot, ChevronRight } from 'lucide-vue-next'
import { Dialog } from '@/shared/ui/dialog'
import { Input } from '@/shared/ui/input'
import { FormField } from '@/shared/ui/label'
import { Button } from '@/shared/ui/button'
import { cn } from '@/shared/lib/utils'
import {
  fromRobot,
  hasErrors,
  toRobotPatch,
  validateRobotForm,
  warnRobotForm,
  type RobotFormErrors,
  type RobotFormValues,
} from '@/domain/robot-form'
import { config } from '@/app/config'
import type { RobotConfig } from '@/domain/types'

const props = withDefaults(
  defineProps<{
    open: boolean
    /** null = add, a robot = edit. */
    robot?: RobotConfig | null
    existing: RobotConfig[]
    pending?: boolean
    /**
     * A rejection from the server. The client checks uniqueness against the
     * rows it can see, but it only sees this page and this browser — the
     * database is the authority, and its answer belongs on the field that
     * caused it, not in a toast.
     */
    serverError?: { field: 'name' | 'bridgeUrl' | null; message: string } | null
  }>(),
  { robot: null, pending: false, serverError: null },
)

const emit = defineEmits<{
  'update:open': [value: boolean]
  submit: [values: ReturnType<typeof toRobotPatch>]
}>()

const isEdit = computed(() => props.robot !== null)

function blank(): RobotFormValues {
  return { name: '', bridgeUrl: config.defaultRosUrl, rosDomainId: '' }
}

const values = ref<RobotFormValues>(blank())
const touched = ref<Record<keyof RobotFormValues, boolean>>({
  name: false,
  bridgeUrl: false,
  rosDomainId: false,
})
const submitAttempted = ref(false)
/**
 * The ROS domain sits behind "Advanced": the browser reaches a robot through
 * rosbridge, which ignores it, so most robots never need one. Open by itself
 * when there is a value to see or an error to fix.
 */
const advancedOpen = ref(false)

// Reset whenever the dialog opens, so a cancelled edit never leaks into the
// next one.
watch(
  () => [props.open, props.robot] as const,
  ([open, robot]) => {
    if (!open) return
    values.value = robot ? fromRobot(robot) : blank()
    touched.value = { name: false, bridgeUrl: false, rosDomainId: false }
    submitAttempted.value = false
    advancedOpen.value = values.value.rosDomainId !== ''
  },
  { immediate: true },
)

const errors = computed(() =>
  validateRobotForm(values.value, props.existing, props.robot?.id ?? null),
)
const warnings = computed(() => warnRobotForm(values.value))

/** Only surface an error once the field has been visited or submit was tried. */
function errorFor(field: keyof RobotFormValues): string | undefined {
  // A server rejection outranks local validation: the local rules passed, and
  // the server disagreed on evidence the browser does not have.
  if (props.serverError?.field === field) return props.serverError.message
  if (!submitAttempted.value && !touched.value[field]) return undefined
  return (errors.value as RobotFormErrors)[field]
}

/** A failure that belongs to no single field — the backend being down, say. */
const generalError = computed(() =>
  props.serverError && props.serverError.field === null ? props.serverError.message : null,
)

function markTouched(field: keyof RobotFormValues) {
  touched.value[field] = true
}

function onSubmit() {
  submitAttempted.value = true
  if ((errors.value as RobotFormErrors).rosDomainId) advancedOpen.value = true
  if (hasErrors(errors.value)) return
  emit('submit', toRobotPatch(values.value))
}
</script>

<template>
  <Dialog
    :open="props.open"
    :pending="props.pending"
    :title="isEdit ? `Edit ${props.robot?.name}` : 'Add robot'"
    :description="
      isEdit
        ? 'Changes apply immediately. A live connection to this robot will be re-established.'
        : 'A robot needs a name and a rosbridge WebSocket address.'
    "
    @update:open="emit('update:open', $event)"
  >
    <form id="robot-form" class="space-y-base" novalidate @submit.prevent="onSubmit">
      <FormField
        label="Robot name"
        required
        hint="Shown everywhere this robot appears. Make it match what is painted on the machine."
        :error="errorFor('name')"
      >
        <template #default="{ id, invalid }">
          <Input
            :id="id"
            v-model="values.name"
            :invalid="invalid"
            placeholder="AMR-02"
            autocomplete="off"
            @blur="markTouched('name')"
          />
        </template>
      </FormField>

      <FormField
        label="Bridge WebSocket"
        required
        hint="rosbridge address, including the port."
        :error="errorFor('bridgeUrl')"
      >
        <template #default="{ id, invalid }">
          <Input
            :id="id"
            v-model="values.bridgeUrl"
            mono
            :invalid="invalid"
            placeholder="ws://192.168.1.50:8765"
            autocomplete="off"
            spellcheck="false"
            @blur="markTouched('bridgeUrl')"
          />
        </template>
      </FormField>

      <div class="rounded-control border border-hairline">
        <button
          type="button"
          :aria-expanded="advancedOpen"
          aria-controls="robot-advanced"
          class="flex w-full items-center gap-xs px-sm py-xs text-left text-body-sm text-body transition-colors hover:text-ink touch:min-h-[44px]"
          @click="advancedOpen = !advancedOpen"
        >
          <ChevronRight
            :size="14"
            :class="cn('shrink-0 text-muted transition-transform', advancedOpen && 'rotate-90')"
          />
          Advanced
          <span
            v-if="!advancedOpen && values.rosDomainId"
            class="ml-auto font-data text-caption text-muted"
          >
            domain {{ values.rosDomainId }}
          </span>
        </button>
        <div v-show="advancedOpen" id="robot-advanced" class="border-t border-hairline p-sm">
          <FormField
            label="ROS domain ID"
            :hint="
              warnings.rosDomainId ??
              'Only needed if something on this machine speaks DDS directly. The browser reaches the robot through rosbridge, which ignores the domain.'
            "
            :error="errorFor('rosDomainId')"
          >
            <template #default="{ id, invalid }">
              <Input
                :id="id"
                v-model="values.rosDomainId"
                mono
                :invalid="invalid"
                inputmode="numeric"
                placeholder="42"
                autocomplete="off"
                class="w-32"
                @blur="markTouched('rosDomainId')"
              />
            </template>
          </FormField>
        </div>
      </div>

      <!-- Identity preview. The accent colour is assigned on save, so the add
           form shows the generic mark rather than promising a colour. -->
      <div
        v-if="values.name.trim()"
        class="flex items-center gap-sm rounded-control bg-surface-soft px-sm py-xs"
      >
        <span
          class="flex h-8 w-8 shrink-0 items-center justify-center rounded-full text-white"
          :style="{
            backgroundColor: props.robot
              ? `rgb(var(--robot-accent-${props.robot.accent}))`
              : 'rgb(var(--muted))',
          }"
        >
          <Bot :size="15" />
        </span>
        <div class="min-w-0">
          <p class="truncate text-title-sm text-ink">{{ values.name.trim() }}</p>
          <p class="truncate font-ident text-caption text-muted">
            {{ values.bridgeUrl.trim() || 'no bridge set' }}
          </p>
        </div>
      </div>
      <p
        v-if="generalError"
        class="rounded-control border border-status-fault/40 bg-status-fault/10 px-sm py-xs text-body-sm text-status-fault"
        role="alert"
      >
        {{ generalError }}
      </p>
    </form>

    <template #footer>
      <Button
        variant="secondary"
        size="sm"
        :disabled="props.pending"
        @click="emit('update:open', false)"
      >
        Cancel
      </Button>
      <Button type="submit" form="robot-form" size="sm" :disabled="props.pending">
        {{ props.pending ? 'Saving…' : isEdit ? 'Save changes' : 'Add robot' }}
      </Button>
    </template>
  </Dialog>
</template>
