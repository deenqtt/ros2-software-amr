<script setup lang="ts">
/**
 * Rename a map.
 *
 * The name is shared by every version — "Warehouse A" v1, v2, v3 are one map
 * with three surveys — so a rename moves all of them. The dialog says so,
 * because an operator renaming what looks like a single row would otherwise be
 * surprised to find three rows changed.
 *
 * Nothing about the map's contents changes, and robots track a map by id, so
 * this is safe to do while a robot is running the map.
 */
import { computed, ref, watch } from 'vue'
import { Dialog } from '@/shared/ui/dialog'
import { Button } from '@/shared/ui/button'
import { Input } from '@/shared/ui/input'
import { FormField } from '@/shared/ui/label'
import type { MapRecord } from '@/domain/types'

const props = defineProps<{
  /** The map whose lineage is being renamed, or null when closed. */
  map: MapRecord | null
  /** Every map in the registry, to warn about a name that is already taken. */
  maps: MapRecord[]
  busy?: boolean
  error?: string | null
}>()

const emit = defineEmits<{
  'update:open': [value: boolean]
  submit: [name: string]
}>()

const name = ref('')

// Reset on open rather than on close: leaving the old value in place until the
// dialog reopens means a flash of the previous map's name.
watch(
  () => props.map,
  (map) => {
    name.value = map?.name ?? ''
  },
  { immediate: true },
)

const trimmed = computed(() => name.value.trim())
const unchanged = computed(() => trimmed.value === props.map?.name)

/** How many rows this rename will touch, counting the one in front of them. */
const versionCount = computed(() => {
  const current = props.map?.name.toLocaleLowerCase()
  if (!current) return 0
  return props.maps.filter((m) => m.name.toLocaleLowerCase() === current).length
})

const taken = computed(() => {
  const wanted = trimmed.value.toLocaleLowerCase()
  if (!wanted || unchanged.value) return false
  // A case-only change to the same lineage is a rename onto itself, not a clash.
  if (wanted === props.map?.name.toLocaleLowerCase()) return false
  return props.maps.some((m) => m.name.toLocaleLowerCase() === wanted)
})

const problem = computed(() => {
  if (!trimmed.value) return 'A name is required.'
  if (taken.value) return 'Another map already uses this name.'
  return null
})

function submit() {
  if (problem.value || unchanged.value || props.busy) return
  emit('submit', trimmed.value)
}
</script>

<template>
  <Dialog
    :open="props.map !== null"
    title="Rename map"
    description="The name is shared by every version of this map. Its contents and its assignments do not change."
    @update:open="emit('update:open', $event)"
  >
    <form class="space-y-base" @submit.prevent="submit">
      <FormField
        label="Map name"
        required
        :hint="
          versionCount > 1
            ? `This map has ${versionCount} versions. All of them will be renamed.`
            : 'Shown wherever this map appears.'
        "
        :error="props.error ?? problem ?? undefined"
      >
        <template #default="{ id, invalid }">
          <Input
            :id="id"
            v-model="name"
            :invalid="invalid"
            placeholder="Warehouse A"
            autocomplete="off"
          />
        </template>
      </FormField>
    </form>

    <template #footer>
      <Button variant="secondary" size="sm" :disabled="props.busy" @click="emit('update:open', false)">
        Cancel
      </Button>
      <Button size="sm" :disabled="Boolean(problem) || unchanged || props.busy" @click="submit">
        {{ props.busy ? 'Renaming…' : 'Rename' }}
      </Button>
    </template>
  </Dialog>
</template>
