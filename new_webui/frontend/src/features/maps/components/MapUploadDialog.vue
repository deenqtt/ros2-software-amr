<script setup lang="ts">
/**
 * Upload a map pair.
 *
 * A ROS map is two files that refer to each other, so the form insists on
 * both. Accepting a yaml alone would produce a registry entry that no robot
 * can load, and the failure would surface later, on a robot, as what looks
 * like a robot fault.
 */
import { computed, ref, watch } from 'vue'
import { FileText, Image as ImageIcon, X } from 'lucide-vue-next'
import { Dialog } from '@/shared/ui/dialog'
import { Input } from '@/shared/ui/input'
import { FormField } from '@/shared/ui/label'
import { Button } from '@/shared/ui/button'
import { cn } from '@/shared/lib/utils'

const props = withDefaults(
  defineProps<{
    open: boolean
    pending?: boolean
    serverError?: string | null
    /** Names already in the registry, to warn about creating a new version. */
    existingNames?: string[]
  }>(),
  { pending: false, serverError: null, existingNames: () => [] },
)

const emit = defineEmits<{
  'update:open': [value: boolean]
  submit: [payload: { name: string; yamlFile: File; imageFile: File; note: string | null }]
}>()

const name = ref('')
const note = ref('')
const yamlFile = ref<File | null>(null)
const imageFile = ref<File | null>(null)
const submitAttempted = ref(false)

watch(
  () => props.open,
  (open) => {
    if (!open) return
    name.value = ''
    note.value = ''
    yamlFile.value = null
    imageFile.value = null
    submitAttempted.value = false
  },
  { immediate: true },
)

/**
 * Files are sorted by extension rather than by which input they came from, so
 * dropping the pair in either order works.
 */
function classify(files: FileList | null) {
  for (const file of Array.from(files ?? [])) {
    const lower = file.name.toLowerCase()
    if (lower.endsWith('.yaml') || lower.endsWith('.yml')) yamlFile.value = file
    else if (lower.endsWith('.pgm') || lower.endsWith('.png')) imageFile.value = file
  }
}

const nameError = computed(() => {
  if (!submitAttempted.value) return undefined
  return name.value.trim() ? undefined : 'A map name is required.'
})

const filesError = computed(() => {
  if (!submitAttempted.value) return undefined
  if (!yamlFile.value && !imageFile.value) return 'Both the .yaml and the image are required.'
  if (!yamlFile.value) return 'The .yaml is missing.'
  if (!imageFile.value) return 'The image (.pgm or .png) is missing.'
  return undefined
})

/**
 * Saving under an existing name is legal and common — it is how a re-survey is
 * recorded — but it must not look like an edit.
 */
const willCreateVersion = computed(() =>
  props.existingNames.some(
    (existing) => existing.toLocaleLowerCase() === name.value.trim().toLocaleLowerCase(),
  ),
)

function onSubmit() {
  submitAttempted.value = true
  if (nameError.value || filesError.value || !yamlFile.value || !imageFile.value) return
  emit('submit', {
    name: name.value.trim(),
    yamlFile: yamlFile.value,
    imageFile: imageFile.value,
    note: note.value.trim() || null,
  })
}
</script>

<template>
  <Dialog
    :open="props.open"
    :pending="props.pending"
    title="Upload map"
    description="A map is a .yaml and its image. Both are required — one without the other cannot be loaded."
    @update:open="emit('update:open', $event)"
  >
    <form id="map-upload" class="space-y-base" novalidate @submit.prevent="onSubmit">
      <FormField
        label="Map name"
        required
        :hint="
          willCreateVersion
            ? 'This name already exists — uploading creates the next version. Existing versions are never overwritten.'
            : 'Shown wherever this map appears. Re-surveying later adds a version under the same name.'
        "
        :error="nameError"
      >
        <template #default="{ id, invalid }">
          <Input :id="id" v-model="name" :invalid="invalid" placeholder="Warehouse A" />
        </template>
      </FormField>

      <div class="space-y-xxs">
        <p class="text-label uppercase text-muted">Files</p>

        <label
          :class="
            cn(
              'flex cursor-pointer flex-col items-center gap-xs rounded-control border border-dashed px-base py-lg text-center transition-colors',
              filesError ? 'border-status-fault' : 'border-hairline hover:border-primary',
            )
          "
        >
          <input
            type="file"
            class="sr-only"
            multiple
            accept=".yaml,.yml,.pgm,.png"
            @change="classify(($event.target as HTMLInputElement).files)"
          />
          <p class="text-body-sm text-body">Choose the .yaml and the image</p>
          <p class="text-caption text-muted">Both at once, or one at a time</p>
        </label>

        <div class="grid gap-xs sm:grid-cols-2">
          <div
            v-for="slot in [
              { file: yamlFile, label: 'Map .yaml', icon: FileText },
              { file: imageFile, label: 'Image .pgm / .png', icon: ImageIcon },
            ]"
            :key="slot.label"
            :class="
              cn(
                'flex items-center gap-xs rounded-control px-sm py-xs text-body-sm',
                slot.file ? 'bg-status-ok/10 text-status-ok' : 'bg-surface-soft text-muted',
              )
            "
          >
            <component :is="slot.icon" :size="14" class="shrink-0" />
            <span class="min-w-0 flex-1 truncate">{{ slot.file?.name ?? slot.label }}</span>
            <button
              v-if="slot.file"
              type="button"
              class="shrink-0 text-muted hover:text-ink"
              :aria-label="`Remove ${slot.file.name}`"
              @click="slot.label.startsWith('Map') ? (yamlFile = null) : (imageFile = null)"
            >
              <X :size="13" />
            </button>
          </div>
        </div>

        <p v-if="filesError" class="text-caption text-status-fault">{{ filesError }}</p>
      </div>

      <FormField label="Note" hint="Optional. What changed in this survey.">
        <template #default="{ id }">
          <Input :id="id" v-model="note" placeholder="Re-surveyed after racking moved" />
        </template>
      </FormField>

      <p
        v-if="props.serverError"
        class="rounded-control border border-status-fault/40 bg-status-fault/10 px-sm py-xs text-body-sm text-status-fault"
        role="alert"
      >
        {{ props.serverError }}
      </p>
    </form>

    <template #footer>
      <Button variant="secondary" size="sm" :disabled="props.pending" @click="emit('update:open', false)">
        Cancel
      </Button>
      <Button type="submit" form="map-upload" size="sm" :disabled="props.pending">
        {{ props.pending ? 'Uploading…' : 'Upload' }}
      </Button>
    </template>
  </Dialog>
</template>
