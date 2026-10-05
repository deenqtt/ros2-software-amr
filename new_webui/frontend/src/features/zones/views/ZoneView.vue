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
import { PanelRightClose, PanelRightOpen, Plus, Shapes, X } from 'lucide-vue-next'
import { toast } from 'vue-sonner'
import { useMapStore } from '@/stores/maps'
import { useZoneStore } from '@/stores/zones'
import { useUiStore } from '@/stores/ui'
import { mapsApi } from '@/shared/api/maps'
import { decodePgm, type Grid } from '@/domain/map/pgm'
import {
  SPEED_MAX,
  SPEED_MIN,
  SPEED_STEP,
  ZONE_MIN_POINTS,
  type Zone,
  type ZoneKind,
  type ZonePoint,
} from '@/domain/types'
import { avoidLevel, ZONE_KIND_LIST, ZONE_KIND_STYLE } from '../zoneKind'
import ZoneMapCanvas from '../components/ZoneMapCanvas.vue'
import ZoneListItem from '../components/ZoneListItem.vue'
import { Button } from '@/shared/ui/button'
import { Input } from '@/shared/ui/input'
import { FormField } from '@/shared/ui/label'
import { Select } from '@/shared/ui/select'
import { Dialog } from '@/shared/ui/dialog'
import EmptyState from '@/shared/components/EmptyState.vue'
import ConfirmDialog from '@/shared/components/ConfirmDialog.vue'
import MapListToggle, { type MapListView } from '@/shared/components/MapListToggle.vue'
import { usePermission } from '@/shared/composables/usePermission'
import { useScreenBlocker } from '@/shared/composables/useScreenBlocker'
import { cn } from '@/shared/lib/utils'

const maps = useMapStore()
const zones = useZoneStore()
const { canEdit, editBlocker } = usePermission()
const ui = useUiStore()

/**
 * A phone gets the map full width and the list as the other half of a
 * Map/List switch. Drawing and reshaping stay on bigger screens: a fingertip
 * covers several cells, so corners dropped by thumb land roughly — and a
 * keep-out a few cells off blocks an aisle or misses the hazard.
 */
const phone = computed(() => ui.screen === 'phone')
const view = ref<MapListView>('map')
const { tooSmall: drawTooSmall, reason: drawReason } = useScreenBlocker('Drawing zones')

const selectedMapId = ref<string | null>(null)
const grid = ref<Grid | null>(null)
const mapLoading = ref(false)
const mapError = ref<string | null>(null)

const selectedId = ref<string | null>(null)
function wideScreen(): boolean {
  try {
    return window.matchMedia?.('(min-width: 1024px)')?.matches ?? true
  } catch {
    return true
  }
}
/** Starts collapsed below 1024px, where the open list leaves the map half the screen. */
const panelOpen = ref(wideScreen())

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
  if (!canEdit.value || drawTooSmall.value) return
  drawingKind.value = kind
  drawing.value = []
  selectedId.value = null
}

function cancelDrawing() {
  drawing.value = null
}

/** Guarded here too: the corners come from clicks on the map, not a button. */
function addPoint(point: ZonePoint) {
  if (!canEdit.value) return
  drawing.value = [...(drawing.value ?? []), point]
}

function undoPoint() {
  if (!drawing.value?.length) return
  drawing.value = drawing.value.slice(0, -1)
}

/** The ring is closed; now it needs a name and its settings. */
function closeDrawing() {
  const polygon = drawing.value
  if (!polygon || polygon.length < ZONE_MIN_POINTS || !canEdit.value) return
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
  if (!canEdit.value) return
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
  if (!canEdit.value) return
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

// A zone already of an unavailable kind keeps its kind when edited; it just
// cannot be switched to one.
const kindOptions = computed(() =>
  ZONE_KIND_LIST.map((kind) => ({
    value: kind.value,
    label: kind.label,
    hint: kind.unavailable ?? kind.hint,
    disabled: Boolean(kind.unavailable) && form.value.editing?.kind !== kind.value,
  })),
)

/** Kinds worth a legend entry: the ones that can be drawn, and any on the map. */
const legendKinds = computed(() =>
  ZONE_KIND_LIST.filter(
    (kind) => !kind.unavailable || zones.zones.some((zone) => zone.kind === kind.value),
  ),
)

async function onSubmit() {
  if (nameProblem.value || !selectedMapId.value || !canEdit.value) return
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

/** The zone whose switch is in flight, so a double click is not two requests. */
const togglingId = ref<string | null>(null)

async function toggleEnabled(zone: Zone) {
  if (togglingId.value || !canEdit.value) return
  togglingId.value = zone.id
  try {
    const updated = await zones.update(zone.id, { enabled: !zone.enabled })
    toast.success(updated.enabled ? `${updated.name} is on` : `${updated.name} is off`)
  } catch (error) {
    toast.error('Could not change the zone', { description: zones.describeError(error) })
  } finally {
    togglingId.value = null
  }
}

const pendingRemoval = ref<Zone | null>(null)
const removing = ref(false)

async function confirmRemoval() {
  const zone = pendingRemoval.value
  if (!zone || !canEdit.value) return
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

const selectedZone = computed(
  () => shownZones.value.find((zone) => zone.id === selectedId.value) ?? null,
)

/** From the phone list: show the zone where it is. */
function showOnMap(id: string) {
  selectedId.value = id
  view.value = 'map'
}

watch(phone, (small) => {
  if (small) cancelDrawing()
})
</script>

<template>
  <div class="flex h-full min-h-0 flex-col">
    <div
      class="flex shrink-0 flex-wrap items-center gap-xs border-b border-hairline bg-surface px-base py-xs"
    >
      <Shapes v-if="!phone" :size="14" class="shrink-0 text-muted" />
      <Select
        v-if="mapOptions.length"
        label="Map"
        :model-value="selectedMapId"
        :options="mapOptions"
        :class="phone ? 'min-w-0 flex-1' : 'min-w-[10rem] lg:min-w-[12rem]'"
        @update:model-value="selectMap"
      />

      <MapListToggle v-if="phone" v-model="view" :count="zones.count" class="shrink-0" />

      <template v-else>
        <!--
          One button per kind rather than "Add zone" then a picker: the kind
          decides the colour of the outline being drawn, so it has to be chosen
          before the first corner, not after the last one.
        -->
        <!-- "Draw" makes these read as actions; on their own they looked like the legend. -->
        <div class="flex flex-wrap items-center gap-xxs">
          <span class="mr-xxs text-caption text-muted">Draw</span>
          <!-- A kind that cannot be drawn yet is left to the desktop: on a
               tablet its disabled button costs a toolbar row. -->
          <button
            v-for="kind in ZONE_KIND_LIST"
            :key="kind.value"
            type="button"
            :title="
              kind.unavailable ??
              (editBlocker || `Draw a ${kind.label.toLowerCase()} zone — ${kind.hint} (${kind.filter})`)
            "
            :disabled="!canEdit || !grid || Boolean(kind.unavailable)"
            :class="
              cn(
                'flex h-control-sm items-center gap-xs rounded-control border px-sm text-body-sm transition-colors disabled:cursor-not-allowed disabled:opacity-50',
                drawing !== null && drawingKind === kind.value
                  ? 'border-primary bg-primary/10 text-ink'
                  : 'border-hairline text-body hover:border-primary',
                kind.unavailable && 'hidden lg:flex',
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
          <!-- Touch only: a finger has no Enter key and no dependable double
               tap, while a mouse keeps the toolbar it already had. -->
          <Button
            size="sm"
            variant="outline"
            class="hidden touch:inline-flex"
            :disabled="drawing.length < ZONE_MIN_POINTS"
            @click="closeDrawing"
          >
            Finish
          </Button>
          <Button size="sm" variant="ghost" @click="cancelDrawing">Cancel</Button>
        </template>
      </template>
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
          :editable="canEdit && !phone"
          :hide-legend="phone && selectedZone !== null"
          @select="selectedId = $event"
          @add-point="addPoint"
          @close-drawing="closeDrawing"
          @move-point="movePoint"
        >
          <template #legend>
            <span v-for="kind in legendKinds" :key="kind.value" class="flex items-center gap-xxs">
              <span class="h-2.5 w-2.5 rounded-[2px]" :style="{ backgroundColor: kind.colour }" />
              {{ kind.label }}
            </span>
          </template>
        </ZoneMapCanvas>

        <!--
          Phone, map view: the tapped zone as a card over the bottom of the
          map, with its switch, so turning it off for a shift needs no list.
        -->
        <div
          v-if="phone && view === 'map' && selectedZone"
          class="absolute inset-x-sm bottom-sm z-10 flex items-start gap-xxs rounded-surface border border-hairline bg-surface p-xxs shadow-soft"
        >
          <ZoneListItem
            class="min-w-0 flex-1"
            :zone="selectedZone"
            detail
            :toggling="togglingId === selectedZone.id"
            @toggle="toggleEnabled(selectedZone)"
            @edit="openEdit(selectedZone)"
            @remove="pendingRemoval = selectedZone"
          />
          <Button variant="ghost" size="icon-sm" aria-label="Close" @click="selectedId = null">
            <X :size="15" />
          </Button>
        </div>

        <!--
          Phone, list view: over the map rather than instead of it, so the map
          keeps its zoom and pan for the trip back.
        -->
        <div
          v-if="phone && view === 'list'"
          class="absolute inset-0 z-10 overflow-y-auto bg-surface"
        >
          <div class="flex flex-wrap items-center gap-x-sm gap-y-xxs border-b border-hairline p-sm">
            <Button size="sm" variant="outline" disabled>
              <Plus :size="13" />
              Draw a zone
            </Button>
            <!-- Said in words: a phone has no hover to show a tooltip. -->
            <p class="text-caption text-muted">{{ editBlocker || drawReason }}</p>
          </div>

          <EmptyState
            v-if="!zones.count"
            title="No zones on this map"
            description="Zones are drawn on a tablet or laptop."
          />
          <ul v-else class="space-y-xxs p-xs">
            <li v-for="zone in shownZones" :key="zone.id">
              <ZoneListItem
                :zone="zone"
                :selected="selectedId === zone.id"
                :toggling="togglingId === zone.id"
                @select="showOnMap(zone.id)"
                @toggle="toggleEnabled(zone)"
                @edit="openEdit(zone)"
                @remove="pendingRemoval = zone"
              />
            </li>
          </ul>
        </div>
      </div>

      <aside
        v-if="!phone"
        class="flex shrink-0 flex-col border-l border-hairline bg-surface transition-[width] duration-150"
        :class="panelOpen ? 'w-[18rem]' : 'w-[3rem]'"
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
            <ZoneListItem
              v-for="zone in zones.zones"
              :key="zone.id"
              :zone="zone"
              :selected="selectedId === zone.id"
              :detail="selectedId === zone.id"
              :toggling="togglingId === zone.id"
              @select="selectedId = zone.id"
              @toggle="toggleEnabled(zone)"
              @edit="openEdit(zone)"
              @remove="pendingRemoval = zone"
            />
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
          label="Avoid strength (1–99)"
          required
          :hint="`${avoidLevel(form.avoidCost)}. Higher means the robot tries harder to go around; 100 would be a keep-out.`"
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
          <input v-model="form.enabled" type="checkbox" class="accent-[rgb(var(--primary))]" />
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
