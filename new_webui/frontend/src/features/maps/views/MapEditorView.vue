<script setup lang="ts">
/**
 * Hand-correct a map.
 *
 * What this exists to fix: glass and mirrors producing phantom walls, doorways
 * smeared shut by a fast pass, pallets and people baked in as permanent
 * obstacles, unknown speckle inside plainly free floor.
 *
 * Three rules shape the whole screen.
 *
 * Nothing is overwritten. Saving publishes a new version under the same name, so
 * the version a robot is running is still there afterwards. Stations store
 * coordinates in a map frame, and replacing a map's contents in place would
 * invalidate every one of them with no record of what changed.
 *
 * Geometry is frozen. Resolution, origin and size are not editable and not even
 * shown as fields: a cell's world position is origin + index x resolution, so
 * cropping or rescaling would silently move every stored coordinate. Painting
 * cells is safe precisely because those four numbers do not move.
 *
 * The result is not deployed. A survey auto-assigns because the robot built the
 * map; a hand edit does not, because a person can paint a real wall away and
 * Nav2 will happily plan straight through it.
 */
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { RouterLink, useRoute, useRouter } from 'vue-router'
import {
  ArrowLeft,
  Brush,
  Droplet,
  Hand,
  Redo2,
  RotateCcw,
  Save,
  Minus,
  Plus,
  Slash,
  Square,
  TriangleAlert,
  Undo2,
} from 'lucide-vue-next'
import { toast } from 'vue-sonner'
import { useMapStore } from '@/stores/maps'
import { useFleetStore } from '@/stores/fleet'
import { mapsApi } from '@/shared/api/maps'
import { decodePgm, encodePgm, nonCanonicalValues, type Material } from '@/domain/map/pgm'
import { BRUSH_METRES, useMapEditor, type Tool } from '../composables/useMapEditor'
import MapEditCanvas from '../components/MapEditCanvas.vue'
import { Button } from '@/shared/ui/button'
import { Card, CardContent } from '@/shared/ui/card'
import { Input } from '@/shared/ui/input'
import { FormField } from '@/shared/ui/label'
import { Dialog } from '@/shared/ui/dialog'
import PanelToolbar from '@/shared/components/PanelToolbar.vue'
import EmptyState from '@/shared/components/EmptyState.vue'
import ConfirmDialog from '@/shared/components/ConfirmDialog.vue'
import BlockedTip from '@/shared/components/BlockedTip.vue'
import LargerScreenNotice from '@/shared/components/LargerScreenNotice.vue'
import { usePermission } from '@/shared/composables/usePermission'
import { useUiStore } from '@/stores/ui'
import { cn, formatNumber } from '@/shared/lib/utils'

const route = useRoute()
const router = useRouter()
const maps = useMapStore()
const fleet = useFleetStore()
const editor = useMapEditor()
const { canEdit, editBlocker } = usePermission()
const ui = useUiStore()

/**
 * Painting cells wants a precise pointer and room to see the walls around
 * them, so a phone gets advice first. Advice, not a block: "Open anyway" is
 * for this visit only, and the gate is computed so turning or widening the
 * screen past a phone lifts it. The map still loads behind it, so opening
 * anyway is instant.
 */
const openAnyway = ref(false)
const phoneNotice = computed(() => ui.screen === 'phone' && !openAnyway.value)

/**
 * Without the admin role the page is a viewer: Pan is the only tool, so the
 * canvas can still be moved around but never painted on.
 */
const activeTool = computed<Tool>(() => (canEdit.value ? editor.tool.value : 'pan'))

const mapId = computed(() => String(route.params.mapId ?? ''))
const record = computed(() => maps.byId(mapId.value))

const loading = ref(true)
const loadError = ref<string | null>(null)
/** The stored yaml, kept byte-for-byte so it can be sent back untouched. */
const yamlBytes = ref<Uint8Array | null>(null)

const canvas = ref<InstanceType<typeof MapEditCanvas> | null>(null)

// Controls that cannot affect the current tool are hidden rather than disabled:
// a greyed-out brush row beside the Pan tool is a question the operator has to
// answer, and the answer is always "not with this tool".
const brushIndex = computed(() =>
  BRUSH_METRES.indexOf(editor.brushMetres.value as (typeof BRUSH_METRES)[number]),
)

/**
 * The physical size. The cell count is shown beside it, because the grid can
 * only express whole cells: asking for 12 cm at 5 cm per cell gives 10, and
 * that rounding has to be visible rather than silent.
 */
const brushLabel = computed(() => {
  const metres = editor.brushActualMetres.value
  return metres < 1 ? `${Math.round(metres * 100)} cm` : `${metres.toFixed(2)} m`
})

function stepBrush(direction: number) {
  const next =
    BRUSH_METRES[Math.min(Math.max(brushIndex.value + direction, 0), BRUSH_METRES.length - 1)]
  if (next !== undefined) editor.brushMetres.value = next
}

/**
 * A standalone ArrayBuffer holding exactly these bytes.
 *
 * A Uint8Array may be a view into a larger buffer, and handing that to File
 * would upload whatever else the buffer holds.
 */
function bufferOf(bytes: Uint8Array): ArrayBuffer {
  return bytes.buffer.slice(bytes.byteOffset, bytes.byteOffset + bytes.byteLength) as ArrayBuffer
}

const saveOpen = ref(false)
const saving = ref(false)
const saveError = ref<string | null>(null)
const note = ref('')

/**
 * New version by default.
 *
 * Overwriting keeps the row count down and is a fair call for an obvious
 * correction, but it destroys what was there — so it is chosen, never assumed.
 */
type SaveMode = 'version' | 'overwrite'
const saveMode = ref<SaveMode>('version')

/** Robots pointing at this exact version, which an overwrite changes underneath. */
const robotsOnThisVersion = computed(() =>
  fleet.robots.filter((robot) => robot.activeMapId === mapId.value).map((robot) => robot.name),
)
const confirmReset = ref(false)
const confirmLeave = ref(false)

const TOOLS: { value: Tool; label: string; icon: typeof Brush; hint: string }[] = [
  { value: 'brush', label: 'Brush', icon: Brush, hint: 'Freehand — B' },
  { value: 'line', label: 'Line', icon: Slash, hint: 'Straight run, closes a doorway — L' },
  { value: 'rect', label: 'Block', icon: Square, hint: 'Fill a rectangle — R' },
  { value: 'fill', label: 'Fill', icon: Droplet, hint: 'Replace a connected region — F' },
  // Reachable by mouse, not only by keyboard. Middle-drag pans from any tool,
  // but that is not discoverable and a trackpad may not have a middle button.
  { value: 'pan', label: 'Pan', icon: Hand, hint: 'Move the view without painting — H' },
]

const SAVE_MODES: { value: SaveMode; label: string; description: string }[] = [
  {
    value: 'version',
    label: 'Publish a new version',
    description:
      'The version you opened stays exactly as it is, and nothing is assigned to the new one. Reversible: put a robot back on the old version and it reloads it.',
  },
  {
    value: 'overwrite',
    label: 'Replace this version',
    description:
      'Keeps one row and the current assignments. The previous contents are gone — there is no version to go back to.',
  },
]

const MATERIALS: { value: Material; label: string; swatch: string; hint: string }[] = [
  { value: 'occupied', label: 'Obstacle', swatch: '#1a1a1a', hint: 'Wall — not drivable' },
  { value: 'free', label: 'Free', swatch: '#f6f7f8', hint: 'Open floor' },
  { value: 'unknown', label: 'Unknown', swatch: 'rgb(128,132,140)', hint: 'Never surveyed' },
]

async function load() {
  loading.value = true
  loadError.value = null
  try {
    if (!maps.loaded) await maps.load()
    // Needed to say which robots an overwrite would change underneath.
    if (fleet.robots.length === 0) await fleet.load()
    const found = maps.byId(mapId.value)
    if (!found) throw new Error('That map is not in the registry.')

    const [image, yaml] = await Promise.all([
      mapsApi.fetchFile(found.id, 'image'),
      mapsApi.fetchFile(found.id, 'yaml'),
    ])
    yamlBytes.value = yaml

    const grid = decodePgm(image)
    // The registry rejects non-canonical values on upload, but a map stored
    // before that check existed could still hold them. Saying so beats letting
    // the operator wonder why some cells look like neither wall nor floor.
    const stray = nonCanonicalValues(grid)
    if (stray.length > 0) {
      toast.warning('This map holds values that are neither wall, floor nor unknown', {
        description: `Found ${stray.slice(0, 6).join(', ')}. Saving will normalise every cell you paint over.`,
      })
    }

    editor.load(grid, {
      resolution: found.resolution ?? 0.05,
      originX: found.originX ?? 0,
      originY: found.originY ?? 0,
    })
  } catch (error) {
    loadError.value = error instanceof Error ? error.message : String(error)
  } finally {
    loading.value = false
  }
}

onMounted(load)

function repaint(indices: Int32Array | null) {
  if (indices) canvas.value?.refreshCells(indices)
}

function onBegin(cell: { column: number; row: number }) {
  if (!canEdit.value) return
  repaint(editor.begin(cell))
}

function onExtend(cell: { column: number; row: number }) {
  if (!canEdit.value) return
  repaint(editor.extend(cell))
}

function onEnd() {
  repaint(editor.end())
}

function undo() {
  // Full repaint: a patch's own indices are what changed, but undo restores
  // earlier values and the cheapest correct thing is to redraw.
  if (editor.undo()) canvas.value?.refreshCells(null)
}

function redo() {
  if (editor.redo()) canvas.value?.refreshCells(null)
}

function reset() {
  editor.reset()
  canvas.value?.refreshCells(null)
  confirmReset.value = false
}

// ── Keyboard ─────────────────────────────────────────────────────────────────

function onKeydown(event: KeyboardEvent) {
  const target = event.target as HTMLElement | null
  if (target && /^(INPUT|TEXTAREA|SELECT)$/.test(target.tagName)) return
  if (!canEdit.value) return

  if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === 'z') {
    event.preventDefault()
    if (event.shiftKey) redo()
    else undo()
    return
  }
  if (event.key === 'Escape') {
    // Abandons a half-dragged shape. Without this the only way out of a
    // rectangle started by accident is to finish it and undo.
    editor.cancelDrag()
    return
  }
  // Bracket keys resize the brush, as every paint tool does.
  if (event.key === '[' || event.key === ']') {
    stepBrush(event.key === '[' ? -1 : 1)
    return
  }
  // Held, not toggled: a comparison you have to switch off is one you forget to.
  if (event.key === '\\' && !event.repeat) {
    editor.previewOriginal.value = true
    return
  }

  const shortcuts: Record<string, Tool> = { b: 'brush', l: 'line', r: 'rect', f: 'fill', h: 'pan' }
  const tool = shortcuts[event.key.toLowerCase()]
  if (tool) editor.tool.value = tool
}

function onKeyup(event: KeyboardEvent) {
  if (event.key === '\\') editor.previewOriginal.value = false
}

/** A tab switch while the key is down never delivers the keyup. */
function dropPreview() {
  editor.previewOriginal.value = false
}

onMounted(() => {
  window.addEventListener('keydown', onKeydown)
  window.addEventListener('keyup', onKeyup)
  window.addEventListener('blur', dropPreview)
})
onBeforeUnmount(() => {
  window.removeEventListener('keydown', onKeydown)
  window.removeEventListener('keyup', onKeyup)
  window.removeEventListener('blur', dropPreview)
})

// ── Save ─────────────────────────────────────────────────────────────────────

/**
 * What the operator has done so far.
 *
 * "0.00 cells changed (0.00% of map)" is a lot of characters for "nothing yet",
 * and it sits in the header where it competes with the buttons that matter.
 */
const changedLabel = computed(() => {
  const count = editor.changedCells.value
  if (count === 0) return 'No changes yet'
  const percent = editor.changedFraction.value * 100
  const shown = percent < 0.01 ? '<0.01' : percent.toFixed(2)
  return `${formatNumber(count)} cells · ${shown}%`
})

/** The same figure spelled out, for the save dialog where there is room. */
const changedDetail = computed(() => {
  const count = editor.changedCells.value
  const percent = editor.changedFraction.value * 100
  const shown = percent > 0 && percent < 0.01 ? '<0.01' : percent.toFixed(2)
  return `${formatNumber(count)} cells changed (${shown}% of map)`
})

async function onSave() {
  const found = record.value
  const grid = editor.grid.value
  const yaml = yamlBytes.value
  if (!found || !grid || !yaml || !canEdit.value) return
  if (!note.value.trim()) {
    saveError.value = 'Say what you changed. This becomes the version history.'
    return
  }

  saving.value = true
  saveError.value = null
  try {
    // The yaml goes back as it arrived. Rebuilding it from MapRecord would drop
    // any key the record does not carry, `mode` among them.
    const files = {
      yamlFile: new File([bufferOf(yaml)], 'map.yaml', { type: 'application/x-yaml' }),
      imageFile: new File([bufferOf(encodePgm(grid))], 'map.pgm', {
        type: 'image/x-portable-graymap',
      }),
      note: note.value.trim(),
    }

    if (saveMode.value === 'overwrite') {
      const updated = await maps.replaceImage(found.id, files)
      const affected = robotsOnThisVersion.value
      toast.success(`Replaced ${updated.name} v${updated.version}`, {
        description: affected.length
          ? `${affected.join(', ')} will pick up the new contents within ten seconds.`
          : 'No robot is assigned to this version.',
      })
    } else {
      // Same name: the registry turns that into the next version rather than a
      // second map, which is exactly what an edit is.
      const created = await maps.upload({ name: found.name, ...files })
      toast.success(`Saved as ${created.name} v${created.version}`, {
        description: 'Not assigned to any robot — assign it when you are ready.',
      })
    }
    saveOpen.value = false
    void router.push('/maps')
  } catch (error) {
    saveError.value = maps.describeError(error)
  } finally {
    saving.value = false
  }
}

function leave() {
  if (!editor.isDirty.value) {
    void router.push('/maps')
    return
  }
  confirmLeave.value = true
}

function onBeforeUnloadGuard(event: BeforeUnloadEvent) {
  if (!editor.isDirty.value) return
  event.preventDefault()
}

onMounted(() => window.addEventListener('beforeunload', onBeforeUnloadGuard))
onBeforeUnmount(() => window.removeEventListener('beforeunload', onBeforeUnloadGuard))

watch(saveOpen, (open) => {
  if (!open) return
  saveError.value = null
  // Reopening after a cancelled overwrite starts from the safe option again.
  saveMode.value = 'version'
})
</script>

<template>
  <div class="p-sm sm:p-base md:p-lg">
    <EmptyState v-if="loadError" title="Cannot edit this map" :description="loadError">
      <template #action>
        <Button size="sm" variant="secondary" as-child>
          <RouterLink to="/maps">Back to maps</RouterLink>
        </Button>
      </template>
    </EmptyState>

    <Card v-else>
      <PanelToolbar
        :title="
          record ? `${canEdit ? 'Edit' : 'View'} ${record.name} v${record.version}` : 'Edit map'
        "
        :subtitle="
          editor.grid.value ? `${editor.placement.value.resolution} m per cell` : 'Loading…'
        "
      >
        <template #icon><Brush :size="14" class="shrink-0 text-muted" /></template>
        <template v-if="!phoneNotice" #actions>
          <!-- The count is in the save dialog as well; a phone needs the room. -->
          <span
            class="hidden font-data text-caption sm:inline"
            :class="editor.isDirty.value ? 'text-status-act' : 'text-muted-soft'"
          >
            {{ changedLabel }}
          </span>

          <!-- History as one group, so it reads as a unit rather than three
               unrelated buttons wedged between the counter and Save. -->
          <div class="flex items-center gap-xxs rounded-control border border-hairline p-xxs">
            <Button
              variant="ghost"
              size="icon-sm"
              title="Undo — Ctrl+Z"
              :disabled="!canEdit || !editor.canUndo.value"
              @click="undo"
            >
              <Undo2 :size="14" />
            </Button>
            <Button
              variant="ghost"
              size="icon-sm"
              title="Redo — Ctrl+Shift+Z"
              :disabled="!canEdit || !editor.canRedo.value"
              @click="redo"
            >
              <Redo2 :size="14" />
            </Button>
            <Button
              variant="ghost"
              size="icon-sm"
              title="Discard every change"
              :disabled="!canEdit || !editor.isDirty.value"
              @click="confirmReset = true"
            >
              <RotateCcw :size="13" />
            </Button>
          </div>
          <BlockedTip :reason="editBlocker">
            <Button
              size="sm"
              :disabled="!canEdit || !editor.isDirty.value"
              @click="saveOpen = true"
            >
              <Save :size="13" /> Save
            </Button>
          </BlockedTip>
          <Button variant="ghost" size="sm" aria-label="Back to maps" @click="leave">
            <ArrowLeft :size="14" /> <span class="hidden sm:inline">Maps</span>
          </Button>
        </template>
      </PanelToolbar>

      <LargerScreenNotice
        v-if="phoneNotice"
        class="py-xl"
        description="Painting cells needs a precise pointer and room to see the walls around them. You can still look at the map here."
        back-to="/maps"
        back-label="Back to maps"
        @continue="openAnyway = true"
      />

      <CardContent v-else class="space-y-base">
        <div
          v-if="loading"
          class="h-[min(68vh,40rem)] animate-pulse rounded-surface bg-hairline-soft"
        />

        <template v-else>
          <p v-if="!canEdit" class="text-caption text-muted">
            View only — editing maps needs the admin role.
          </p>
          <!--
            A tool rail beside the canvas, not a row of controls above it.
            Five icons squeezed into a header read as less important than the
            material buttons next to them, which inverts the hierarchy: the tool
            is the control an operator changes most.
          -->
          <div class="flex items-start gap-sm">
            <div
              class="flex shrink-0 flex-col gap-xxs rounded-surface border border-hairline p-xxs"
            >
              <button
                v-for="item in TOOLS"
                :key="item.value"
                type="button"
                :title="
                  !canEdit && item.value !== 'pan' ? editBlocker : `${item.label} — ${item.hint}`
                "
                :aria-label="item.label"
                :aria-pressed="activeTool === item.value"
                :disabled="!canEdit && item.value !== 'pan'"
                :class="
                  cn(
                    'flex h-9 w-9 items-center justify-center rounded-control transition-colors',
                    'disabled:cursor-not-allowed disabled:opacity-40',
                    activeTool === item.value
                      ? 'bg-primary text-on-primary'
                      : 'text-muted hover:bg-surface-strong hover:text-ink',
                  )
                "
                @click="editor.tool.value = item.value"
              >
                <component :is="item.icon" :size="16" />
              </button>
            </div>

            <div class="min-w-0 flex-1 space-y-xs">
              <!--
                Options for the active tool only. A greyed brush stepper beside
                the Pan tool is a question whose answer is always the same.
              -->
              <div
                class="flex min-h-[2.75rem] flex-wrap items-center gap-sm rounded-surface border border-hairline px-sm py-xxs"
              >
                <template v-if="canEdit && editor.usesMaterial.value">
                  <span class="text-label uppercase text-muted">Paint</span>
                  <div class="flex gap-xxs">
                    <button
                      v-for="item in MATERIALS"
                      :key="item.value"
                      type="button"
                      :title="item.hint"
                      :aria-pressed="editor.material.value === item.value"
                      :class="
                        cn(
                          'flex h-control-sm items-center gap-xs rounded-control border px-sm text-body-sm transition-colors',
                          editor.material.value === item.value
                            ? 'border-primary bg-primary/10 text-ink'
                            : 'border-transparent text-muted hover:bg-surface-strong hover:text-ink',
                        )
                      "
                      @click="editor.material.value = item.value"
                    >
                      <span
                        class="h-3.5 w-3.5 rounded-[3px] border border-hairline"
                        :style="{ backgroundColor: item.swatch }"
                      />
                      {{ item.label }}
                    </button>
                  </div>
                </template>

                <template v-if="canEdit && editor.usesBrushSize.value">
                  <span class="h-5 w-px bg-hairline" />
                  <span class="text-label uppercase text-muted">Brush</span>
                  <!--
                    A stepper, not a set of sizes: they are ordered, and an
                    operator adjusts up or down from where they are.
                  -->
                  <div class="flex items-center gap-xxs">
                    <Button
                      variant="outline"
                      size="icon-sm"
                      title="Smaller brush — ["
                      :disabled="brushIndex === 0"
                      @click="stepBrush(-1)"
                    >
                      <Minus :size="13" />
                    </Button>
                    <span class="min-w-[5.5rem] text-center">
                      <span class="font-data text-body-sm text-ink">{{ brushLabel }}</span>
                      <span class="ml-xxs font-data text-caption text-muted-soft">
                        {{ editor.brushCells.value }}
                        {{ editor.brushCells.value === 1 ? 'cell' : 'cells' }}
                      </span>
                    </span>
                    <Button
                      variant="outline"
                      size="icon-sm"
                      title="Larger brush — ]"
                      :disabled="brushIndex === BRUSH_METRES.length - 1"
                      @click="stepBrush(1)"
                    >
                      <Plus :size="13" />
                    </Button>
                  </div>
                </template>

                <span v-if="activeTool === 'pan'" class="text-body-sm text-muted">
                  Drag to move the view. Nothing is painted with this tool.
                </span>

                <span class="ml-auto font-data text-caption text-muted-soft">
                  {{ editor.grid.value?.width }} × {{ editor.grid.value?.height }} cells
                </span>
              </div>

              <MapEditCanvas
                ref="canvas"
                :grid="editor.grid.value"
                :placement="editor.placement.value"
                :tool="activeTool"
                :brush-cells="editor.brushCells.value"
                :drag-from="editor.dragFrom.value"
                :drag-to="editor.dragTo.value"
                :preview="editor.displayCells.value"
                @begin="onBegin"
                @extend="onExtend"
                @end="onEnd"
              />
            </div>
          </div>

          <p class="text-caption text-muted">
            <!-- Keyboard shortcuts mean nothing to a finger. -->
            <span class="touch:hidden">
              Keys: <span class="font-ident">B</span> brush, <span class="font-ident">L</span> line,
              <span class="font-ident">R</span> block, <span class="font-ident">F</span> fill,
              <span class="font-ident">H</span> pan, <span class="font-ident">[</span>
              <span class="font-ident">]</span> brush size,
              <span class="font-ident">Esc</span> cancel a shape,
              <span class="font-ident">Space</span> pan, <span class="font-ident">\</span> hold to
              see the original, <span class="font-ident">Ctrl+Z</span> undo.
            </span>
            Resolution, origin and size cannot be changed here — every station and keepout
            coordinate is expressed against them.
          </p>
        </template>
      </CardContent>
    </Card>

    <Dialog
      :open="saveOpen"
      title="Save changes"
      description="Publishing a new version keeps a way back. Replacing does not."
      @update:open="(value: boolean) => !saving && (saveOpen = value)"
    >
      <form class="space-y-base" @submit.prevent="onSave">
        <div class="rounded-control border border-hairline bg-canvas p-sm text-body-sm">
          <p class="text-ink">{{ record?.name }}</p>
          <p class="font-data text-caption text-muted">{{ changedDetail }}</p>
        </div>

        <div class="space-y-xxs">
          <p class="text-label uppercase text-muted">How to save</p>
          <label
            v-for="option in SAVE_MODES"
            :key="option.value"
            :class="
              cn(
                'flex cursor-pointer gap-sm rounded-control border p-sm transition-colors',
                saveMode === option.value
                  ? 'border-primary bg-primary/[0.06]'
                  : 'border-hairline hover:border-primary',
              )
            "
          >
            <input
              v-model="saveMode"
              type="radio"
              :value="option.value"
              name="save-mode"
              class="mt-xxs shrink-0 accent-[rgb(var(--color-primary))]"
            />
            <span class="min-w-0">
              <span class="block text-body-sm text-ink">
                {{
                  option.value === 'overwrite' ? `Replace v${record?.version ?? ''}` : option.label
                }}
              </span>
              <span class="block text-caption leading-relaxed text-muted">
                {{ option.description }}
              </span>
            </span>
          </label>

          <!--
            Named, not counted. "2 robots affected" does not tell an operator
            whether the one carrying a tray right now is among them.
          -->
          <p
            v-if="saveMode === 'overwrite' && robotsOnThisVersion.length"
            class="flex items-start gap-xs rounded-control border border-status-warn/40 bg-status-warn/10 p-sm text-caption text-body"
          >
            <TriangleAlert :size="13" class="mt-px shrink-0 text-status-warn" />
            <span>
              <span class="font-medium">{{ robotsOnThisVersion.join(', ') }}</span>
              {{ robotsOnThisVersion.length === 1 ? 'is' : 'are' }} assigned to this version and
              will reload the new contents within ten seconds. There is nothing to put them back on
              if this is wrong.
            </span>
          </p>
        </div>

        <FormField
          label="What changed"
          required
          hint="Read later by whoever asks why a wall moved."
          :error="saveError ?? undefined"
        >
          <template #default="{ id, invalid }">
            <Input
              :id="id"
              v-model="note"
              :invalid="invalid"
              placeholder="Removed phantom wall from the glass near dock 3"
            />
          </template>
        </FormField>
      </form>

      <template #footer>
        <Button variant="secondary" size="sm" :disabled="saving" @click="saveOpen = false">
          Cancel
        </Button>
        <Button
          size="sm"
          :variant="saveMode === 'overwrite' ? 'danger' : 'primary'"
          :disabled="saving"
          @click="onSave"
        >
          {{ saving ? 'Saving…' : saveMode === 'overwrite' ? 'Replace' : 'Save version' }}
        </Button>
      </template>
    </Dialog>

    <ConfirmDialog
      :open="confirmReset"
      destructive
      title="Discard every change?"
      :description="`${changedDetail}. The map returns to what was loaded, and this cannot be undone.`"
      confirm-label="Discard"
      @update:open="(value: boolean) => !value && (confirmReset = false)"
      @cancel="confirmReset = false"
      @confirm="reset"
    />

    <ConfirmDialog
      :open="confirmLeave"
      destructive
      title="Leave without saving?"
      :description="`${changedDetail}. Nothing has been published, so these edits are lost.`"
      confirm-label="Leave"
      @update:open="(value: boolean) => !value && (confirmLeave = false)"
      @cancel="confirmLeave = false"
      @confirm="router.push('/maps')"
    />
  </div>
</template>
