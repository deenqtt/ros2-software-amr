<script setup lang="ts">
/**
 * Zones for one map.
 *
 * Map first, because a zone is a shape on a floor. The panel beside it is
 * reference: what each one is called, and what it does.
 *
 * Four kinds, three Nav2 filters — `keep out` and `avoid` are the same filter
 * with a different value in its mask. The kind picker says what each one does
 * rather than naming the filter, because "KeepoutFilter with cost 60" is not
 * what an operator is deciding.
 *
 * Nothing here changes what a robot is doing. A saved zone reaches a robot when
 * its agent next syncs, and the panel says so.
 */
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { PanelRightClose, PanelRightOpen, Pencil, Shapes, Trash2 } from 'lucide-vue-next'
import { toast } from 'vue-sonner'
import { useMapStore } from '@/stores/maps'
import { useZoneStore } from '@/stores/zones'
import { mapsApi } from '@/shared/api/maps'
import { decodePgm, type Grid } from '@/domain/map/pgm'
import {
  polygonArea,
  SPEED_MAX,
  SPEED_MIN,
  SPEED_STEP,
  ZONE_MIN_POINTS,
  type Zone,
  type ZoneKind,
  type ZonePoint,
} from '@/domain/types'
import { ZONE_KIND_LIST, ZONE_KIND_STYLE, zoneSetting } from '../zoneKind'
import ZoneMapCanvas from '../components/ZoneMapCanvas.vue'
import { Button } from '@/shared/ui/button'
import { Input } from '@/shared/ui/input'
import { FormField } from '@/shared/ui/label'
import { Select } from '@/shared/ui/select'
import { Dialog } from '@/shared/ui/dialog'
import { RowActions, RowActionItem, RowActionSeparator } from '@/shared/ui/menu'
import EmptyState from '@/shared/components/EmptyState.vue'
import ConfirmDialog from '@/shared/components/ConfirmDialog.vue'
import { cn } from '@/shared/lib/utils'

const maps = useMapStore()
const zones = useZoneStore()

const selectedMapId = ref<string | null>(null)
const grid = ref<Grid | null>(null)
const mapLoading = ref(false)
const mapError = ref<string | null>(null)

const selectedId = ref<string | null>(null)
const panelOpen = ref(true)

/** Corners dropped so far, in metres. Null when not drawing. */
const drawing = ref<ZonePoint[] | null>(null)
const drawingKind = ref<ZoneKind>('keepout')

const mapOptions = computed(() =>
  maps.maps.map((map) => ({ value: map.id, label: `${map.name} v${map.version}` })),
)

const selectedMap = computed(() => (selectedMapId.value ? maps.byId(selectedMapId.value) : null))

const placement = computed(() => ({
  resolution: selectedMap.value?.resolution ?? 0.05,
  originX: selectedMap.value?.originX ?? 0,
  originY: selectedMap.value?.originY ?? 0,
}))

async function loadMapImage(mapId: string) {
  mapLoading.value = true
  mapError.value = null
  grid.value = null
  try {
    grid.value = decodePgm(await mapsApi.fetchFile(mapId, 'image'))
  } catch (error) {
    mapError.value = error instanceof Error ? error.message : String(error)
  } finally {
    mapLoading.value = false
  }
}

async function selectMap(mapId: string) {
  selectedMapId.value = mapId
  selectedId.value = null
  drawing.value = null
  await Promise.all([loadMapImage(mapId), zones.load(mapId)])
}

onMounted(async () => {
  await maps.load()
  const first = maps.maps[0]
  if (first) await selectMap(first.id)
})

// ── Drawing ──────────────────────────────────────────────────────────────────

function startDrawing(kind: ZoneKind) {
  drawingKind.value = kind
  drawing.value = []
  selectedId.value = null
}

function cancelDrawing() {
  drawing.value = null
}

function addPoint(point: ZonePoint) {
  drawing.value = [...(drawing.value ?? []), point]
}

function undoPoint() {
  if (!drawing.value?.length) return
  drawing.value = drawing.value.slice(0, -1)
}

/** The ring is closed; now it needs a name and its settings. */
function closeDrawing() {
  const polygon = drawing.value
  if (!polygon || polygon.length < ZONE_MIN_POINTS) return
  form.value = {
    open: true,
    editing: null,
    polygon,
    name: '',
    kind: drawingKind.value,
    speedLimit: 0.3,
    avoidCost: 50,
    enabled: true,
    note: '',
  }
  formError.value = null
  drawing.value = null
}

// ── Reshaping ────────────────────────────────────────────────────────────────

/**
 * A dragged corner writes after the drag settles.
 *
 * Shown at once, saved once: a pointer at 60 Hz would otherwise issue sixty
 * PATCHes per second, and each one rebuilds a mask on the robot.
 */
let reshapeWrite: ReturnType<typeof setTimeout> | null = null
const reshaped = ref<Map<string, ZonePoint[]>>(new Map())

function movePoint(payload: { id: string; index: number; point: ZonePoint }) {
  const current = reshaped.value.get(payload.id) ?? zones.byId(payload.id)?.polygon
  if (!current) return
  const next = [...current]
  next[payload.index] = payload.point
  reshaped.value = new Map(reshaped.value).set(payload.id, next)

  if (reshapeWrite) clearTimeout(reshapeWrite)
  reshapeWrite = setTimeout(async () => {
    try {
      await zones.update(payload.id, { polygon: next })
    } catch (error) {
      toast.error('Could not reshape the zone', { description: zones.describeError(error) })
      if (selectedMapId.value) await zones.load(selectedMapId.value)
    } finally {
      const pending = new Map(reshaped.value)
      pending.delete(payload.id)
      reshaped.value = pending
    }
  }, 300)
}

/** Stored zones with any in-flight reshape applied on top. */
const shownZones = computed(() =>
  zones.zones.map((zone) => {
    const pending = reshaped.value.get(zone.id)
    return pending ? { ...zone, polygon: pending } : zone
  }),
)

// ── The form ─────────────────────────────────────────────────────────────────

const form = ref<{
  open: boolean
  editing: Zone | null
  polygon: ZonePoint[]
  name: string
  kind: ZoneKind
  speedLimit: number
  avoidCost: number
  enabled: boolean
  note: string
}>({
  open: false,
  editing: null,
  polygon: [],
  name: '',
  kind: 'keepout',
  speedLimit: 0.3,
  avoidCost: 50,
  enabled: true,
  note: '',
})
const saving = ref(false)
const formError = ref<string | null>(null)

function openEdit(zone: Zone) {
  form.value = {
    open: true,
    editing: zone,
    polygon: zone.polygon,
    name: zone.name,
    kind: zone.kind,
    speedLimit: zone.speedLimit ?? 0.3,
    avoidCost: zone.avoidCost ?? 50,
    enabled: zone.enabled,
    note: zone.note ?? '',
  }
  formError.value = null
}

const nameProblem = computed(() => {
  const name = form.value.name.trim()
  if (!name) return 'A name is required.'
  if (zones.nameTaken(name, form.value.editing?.id)) {
    return 'Another zone on this map already uses this name.'
  }
  return null
})

const kindOptions = ZONE_KIND_LIST.map((kind) => ({
  value: kind.value,
  label: kind.label,
  hint: kind.hint,
}))

async function onSubmit() {
  if (nameProblem.value || !selectedMapId.value) return
  saving.value = true
  formError.value = null
  try {
    const kind = form.value.kind
    const payload = {
      name: form.value.name.trim(),
      kind,
      polygon: form.value.polygon,
      enabled: form.value.enabled,
      note: form.value.note.trim() || null,
      // Sent only for the kind that uses it. The server refuses a setting a
      // kind has no use for, because a speed limit on a keepout is a number
      // nobody reads.
      speedLimit: kind === 'speed' ? form.value.speedLimit : null,
      avoidCost: kind === 'avoid' ? form.value.avoidCost : null,
    }
    if (form.value.editing) {
      const updated = await zones.update(form.value.editing.id, payload)
      toast.success(`Updated ${updated.name}`)
    } else {
      const created = await zones.create({ mapId: selectedMapId.value, ...payload })
      selectedId.value = created.id
      toast.success(`Added ${created.name}`, {
        description: 'Robots on this map pick it up within ten seconds.',
      })
    }
    form.value.open = false
  } catch (error) {
    formError.value = zones.describeError(error)
  } finally {
    saving.value = false
  }
}

async function toggleEnabled(zone: Zone) {
  try {
    const updated = await zones.update(zone.id, { enabled: !zone.enabled })
    toast.success(updated.enabled ? `${updated.name} is on` : `${updated.name} is off`)
  } catch (error) {
    toast.error('Could not change the zone', { description: zones.describeError(error) })
  }
}

const pendingRemoval = ref<Zone | null>(null)
const removing = ref(false)

async function confirmRemoval() {
  const zone = pendingRemoval.value
  if (!zone) return
  removing.value = true
  try {
    await zones.remove(zone.id)
    if (selectedId.value === zone.id) selectedId.value = null
    toast.success(`Removed ${zone.name}`)
    pendingRemoval.value = null
  } catch (error) {
    toast.error(`Could not remove ${zone.name}`, { description: zones.describeError(error) })
  } finally {
    removing.value = false
  }
}

// ── Keyboard ─────────────────────────────────────────────────────────────────

function onKeydown(event: KeyboardEvent) {
  const target = event.target as HTMLElement | null
  if (target && /^(INPUT|TEXTAREA|SELECT)$/.test(target.tagName)) return
  if (form.value.open) return

  if (event.key === 'Escape') {
    if (drawing.value) cancelDrawing()
    else selectedId.value = null
    return
  }
  if (drawing.value && event.key === 'Enter') {
    closeDrawing()
    return
  }
  // Backspace takes back the last corner rather than the whole shape: a
  // misplaced click should not cost the other eleven.
  if (drawing.value && (event.key === 'Backspace' || (event.ctrlKey && event.key === 'z'))) {
    event.preventDefault()
    undoPoint()
  }
}

onMounted(() => window.addEventListener('keydown', onKeydown))
onBeforeUnmount(() => {
  window.removeEventListener('keydown', onKeydown)
  if (reshapeWrite) clearTimeout(reshapeWrite)
})

watch(
  () => form.value.open,
  (open) => {
    if (!open) formError.value = null
  },
)

function areaLabel(zone: Zone): string {
  return `${polygonArea(zone.polygon).toFixed(1)} m²`
}
</script>

<template>
  <div class="flex h-full min-h-0 flex-col">
    <div
      class="flex shrink-0 flex-wrap items-center gap-xs border-b border-hairline bg-surface px-base py-xs"
    >
      <Shapes :size="14" class="shrink-0 text-muted" />
      <Select
        v-if="mapOptions.length"
        label="Map"
        :model-value="selectedMapId"
        :options="mapOptions"
        class="min-w-[12rem]"
        @update:model-value="selectMap"
      />

      <!--
        One button per kind rather than "Add zone" then a picker: the kind
        decides the colour of the outline being drawn, so it has to be chosen
        before the first corner, not after the last one.
      -->
      <div class="flex flex-wrap gap-xxs">
        <button
          v-for="kind in ZONE_KIND_LIST"
          :key="kind.value"
          type="button"
          :title="`${kind.hint} (${kind.filter})`"
          :disabled="!grid"
          :class="
            cn(
              'flex h-control-sm items-center gap-xs rounded-control border px-sm text-body-sm transition-colors disabled:cursor-not-allowed disabled:opacity-50',
              drawing !== null && drawingKind === kind.value
                ? 'border-primary bg-primary/10 text-ink'
                : 'border-hairline text-body hover:border-primary',
            )
          "
          @click="startDrawing(kind.value)"
        >
          <span class="h-3 w-3 rounded-[3px]" :style="{ backgroundColor: kind.colour }" />
          {{ kind.label }}
        </button>
      </div>

      <template v-if="drawing !== null">
        <Button size="sm" variant="ghost" :disabled="!drawing.length" @click="undoPoint">
          Undo corner
        </Button>
        <Button size="sm" variant="ghost" @click="cancelDrawing">Cancel</Button>
      </template>

      <span class="ml-auto font-data text-caption text-muted-soft">
        {{ selectedMap ? `${selectedMap.name} v${selectedMap.version}` : '' }}
      </span>
    </div>

    <div class="flex min-h-0 flex-1">
      <div class="relative min-w-0 flex-1">
        <EmptyState
          v-if="!mapOptions.length && !maps.loading"
          class="p-lg"
          title="No maps yet"
          description="A zone is a shape on a map, so there has to be a map first."
        />
        <EmptyState
          v-else-if="mapError"
          class="p-lg"
          title="Cannot show this map"
          :description="mapError"
        />
        <div v-else-if="mapLoading" class="h-full w-full animate-pulse bg-hairline-soft" />

        <ZoneMapCanvas
          v-else
          :grid="grid"
          :placement="placement"
          :zones="shownZones"
          :selected-id="selectedId"
          :drawing="drawing"
          :drawing-kind="drawingKind"
          @select="selectedId = $event"
          @add-point="addPoint"
          @close-drawing="closeDrawing"
          @move-point="movePoint"
        >
          <template #legend>
            <span v-for="kind in ZONE_KIND_LIST" :key="kind.value" class="flex items-center gap-xxs">
              <span class="h-2.5 w-2.5 rounded-[2px]" :style="{ backgroundColor: kind.colour }" />
              {{ kind.label }}
            </span>
          </template>
        </ZoneMapCanvas>
      </div>

      <aside
        class="flex shrink-0 flex-col border-l border-hairline bg-surface transition-[width] duration-150"
        :class="panelOpen ? 'w-[21rem]' : 'w-[3rem]'"
      >
        <button
          type="button"
          class="flex h-11 shrink-0 items-center gap-xs border-b border-hairline px-sm text-body-sm text-body transition-colors hover:text-ink"
          :aria-expanded="panelOpen"
          :title="panelOpen ? 'Hide the zone list' : 'Show the zone list'"
          @click="panelOpen = !panelOpen"
        >
          <component :is="panelOpen ? PanelRightClose : PanelRightOpen" :size="15" class="shrink-0" />
          <template v-if="panelOpen">
            <span>Zones</span>
            <span class="ml-auto font-data text-caption text-muted">{{ zones.count }}</span>
          </template>
        </button>

        <div v-if="panelOpen" class="min-h-0 flex-1 overflow-y-auto scrollbar-thin p-xs">
          <EmptyState
            v-if="!zones.count"
            title="No zones on this map"
            description="Pick a kind above, then click each corner on the map."
          />

          <div v-else class="space-y-xxs">
            <div
              v-for="zone in zones.zones"
              :key="zone.id"
              :class="
                cn(
                  'flex items-start gap-xs rounded-control border p-xs transition-colors',
                  selectedId === zone.id
                    ? 'border-primary bg-primary/[0.06]'
                    : 'border-transparent hover:border-hairline',
                  !zone.enabled && 'opacity-60',
                )
              "
            >
              <button
                type="button"
                class="flex min-w-0 flex-1 items-start gap-xs text-left"
                @click="selectedId = zone.id"
              >
                <span
                  class="mt-px flex h-6 w-6 shrink-0 items-center justify-center rounded-control text-white"
                  :style="{ backgroundColor: ZONE_KIND_STYLE[zone.kind].colour }"
                >
                  <component :is="ZONE_KIND_STYLE[zone.kind].icon" :size="13" />
                </span>
                <span class="min-w-0 flex-1">
                  <span class="block truncate text-body-sm text-ink">{{ zone.name }}</span>
                  <span class="block font-data text-caption text-muted">
                    {{ ZONE_KIND_STYLE[zone.kind].label
                    }}<template v-if="zoneSetting(zone)"> · {{ zoneSetting(zone) }}</template>
                    · {{ areaLabel(zone) }}
                  </span>
                  <!-- A zone that exists but is switched off is not the same as
                       one that is not there, and the list has to say which. -->
                  <span v-if="!zone.enabled" class="block text-caption text-status-warn">
                    Switched off — robots ignore it
                  </span>
                  <span
                    v-else-if="selectedId === zone.id && zone.note"
                    class="mt-xxs block text-caption text-muted-soft"
                  >
                    {{ zone.note }}
                  </span>
                </span>
              </button>

              <RowActions :label="`More actions for ${zone.name}`">
                <RowActionItem :icon="Pencil" @select="openEdit(zone)">Edit</RowActionItem>
                <RowActionItem
                  :icon="ZONE_KIND_STYLE[zone.kind].icon"
                  @select="toggleEnabled(zone)"
                >
                  {{ zone.enabled ? 'Switch off' : 'Switch on' }}
                </RowActionItem>
                <RowActionSeparator class="my-xxs h-px bg-hairline" />
                <RowActionItem :icon="Trash2" destructive @select="pendingRemoval = zone">
                  Remove
                </RowActionItem>
              </RowActions>
            </div>
          </div>
        </div>
      </aside>
    </div>

    <Dialog
      :open="form.open"
      :title="form.editing ? `Edit ${form.editing.name}` : 'New zone'"
      :description="`${form.polygon.length} corners. Robots on this map pick the change up within ten seconds.`"
      @update:open="(value: boolean) => !saving && (form.open = value)"
    >
      <form class="space-y-base" @submit.prevent="onSubmit">
        <FormField label="Name" required :error="formError ?? nameProblem ?? undefined">
          <template #default="{ id, invalid }">
            <Input :id="id" v-model="form.name" :invalid="invalid" placeholder="Panel listrik" />
          </template>
        </FormField>

        <FormField label="Kind" required :hint="ZONE_KIND_STYLE[form.kind].hint">
          <template #default>
            <Select
              label="Kind"
              :model-value="form.kind"
              :options="kindOptions"
              class="w-full"
              @update:model-value="form.kind = $event"
            />
          </template>
        </FormField>

        <!--
          Steps of 0.1 because that is what the mask can express: Nav2 reads a
          mask value of 0 as "no limit", so the encoding starts at 0.1 m/s.
        -->
        <FormField
          v-if="form.kind === 'speed'"
          label="Speed limit (m/s)"
          required
          hint="How fast a robot may go while inside."
        >
          <template #default="{ id }">
            <Input
              :id="id"
              :model-value="form.speedLimit"
              type="number"
              :min="SPEED_MIN"
              :max="SPEED_MAX"
              :step="SPEED_STEP"
              @update:model-value="form.speedLimit = Number($event)"
            />
          </template>
        </FormField>

        <FormField
          v-if="form.kind === 'avoid'"
          label="Reluctance"
          required
          hint="Higher means the robot tries harder to go around. 100 would be a keep-out."
        >
          <template #default="{ id }">
            <Input
              :id="id"
              :model-value="form.avoidCost"
              type="number"
              min="1"
              max="99"
              @update:model-value="form.avoidCost = Number($event)"
            />
          </template>
        </FormField>

        <FormField label="Note" hint="Why this zone is here, for whoever inherits the site.">
          <template #default="{ id }">
            <Input :id="id" v-model="form.note" placeholder="Panel listrik, jangan ketabrak" />
          </template>
        </FormField>

        <label class="flex items-center gap-xs text-body-sm text-body">
          <input v-model="form.enabled" type="checkbox" class="accent-[rgb(var(--color-primary))]" />
          Active — robots obey it
        </label>
      </form>

      <template #footer>
        <Button variant="secondary" size="sm" :disabled="saving" @click="form.open = false">
          Cancel
        </Button>
        <Button size="sm" :disabled="Boolean(nameProblem) || saving" @click="onSubmit">
          {{ saving ? 'Saving…' : form.editing ? 'Save' : 'Add zone' }}
        </Button>
      </template>
    </Dialog>

    <ConfirmDialog
      :open="pendingRemoval !== null"
      destructive
      :pending="removing"
      :title="`Remove ${pendingRemoval?.name ?? ''}?`"
      description="Robots stop obeying it at their next sync. If it is only temporary, switch it off instead — it comes back the same shape."
      confirm-label="Remove"
      @update:open="(value: boolean) => !value && !removing && (pendingRemoval = null)"
      @cancel="pendingRemoval = null"
      @confirm="confirmRemoval"
    />
  </div>
</template>
