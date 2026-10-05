<script setup lang="ts">
/**
 * The map under the brush.
 *
 * Renders the grid into an offscreen canvas one texel per cell, then blits it
 * scaled with smoothing off. Nearest-neighbour is not an aesthetic choice: this
 * is data, and interpolating it would invent free space between an obstacle and
 * the cell beside it — which is exactly the mistake the operator is here to fix.
 *
 * A stroke repaints only the cells it touched. A full putImageData of a
 * warehouse-sized map is a few million pixels, which a freehand drag cannot
 * afford once per sample.
 *
 * Painting is the left button. Panning is the middle or right button, or the Pan
 * tool — keeping them on separate buttons means a drag can never both move the
 * view and lay down paint.
 */
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { Minus, Plus, Maximize } from 'lucide-vue-next'
import { CELL, cellToWorld, type Grid } from '@/domain/map/pgm'
import { Button } from '@/shared/ui/button'
import type { Cell, Tool } from '../composables/useMapEditor'

const props = defineProps<{
  grid: Grid | null
  placement: { resolution: number; originX: number; originY: number }
  tool: Tool
  brushCells: number
  /** Live shape preview while a line or rectangle is being dragged. */
  dragFrom: Cell | null
  dragTo: Cell | null
  /**
   * Draw these cells instead of the grid's own.
   *
   * Used to show the map as it was loaded while a key is held. The grid is not
   * touched, so releasing the key needs only a repaint.
   */
  preview?: Uint8Array | null
}>()

const emit = defineEmits<{
  begin: [cell: Cell]
  extend: [cell: Cell]
  end: []
}>()

/** Same palette as the survey view, so a map looks the same in both places. */
const COLOUR = {
  [CELL.occupied]: [26, 26, 26, 255],
  [CELL.unknown]: [128, 132, 140, 255],
  [CELL.free]: [246, 247, 248, 255],
} as const

/** Below this many screen pixels per cell, grid lines would outweigh the cells. */
const GRID_MIN_SCALE = 8

const ZOOM_MIN = 0.4
const ZOOM_MAX = 40
const ZOOM_STEP = 1.25

const wrapper = ref<HTMLDivElement | null>(null)
const canvas = ref<HTMLCanvasElement | null>(null)
const overlay = ref<HTMLCanvasElement | null>(null)
const viewport = ref({ width: 0, height: 0 })

let buffer: HTMLCanvasElement | null = null
let image: ImageData | null = null

/** Operator pan and zoom, or null while the view auto-fits. */
const view = ref<{ scale: number; offsetX: number; offsetY: number } | null>(null)

const fit = computed(() => {
  const grid = props.grid
  const { width: vw, height: vh } = viewport.value
  if (!grid || vw === 0 || vh === 0) return null
  const scale = Math.min(vw / grid.width, vh / grid.height)
  return {
    scale,
    offsetX: (vw - grid.width * scale) / 2,
    offsetY: (vh - grid.height * scale) / 2,
  }
})

const transform = computed(() => view.value ?? fit.value)

/** Screen pixels per map cell. Everything visual is derived from this. */
const pxPerCell = computed(() => transform.value?.scale ?? 0)

const hover = ref<Cell | null>(null)

/**
 * Space held means pan, whatever tool is selected.
 *
 * Standard in every editor, and better than switching tools: the hand goes back
 * to the brush on release without the operator having to put it there.
 */
const spaceHeld = ref(false)
const activeTool = computed<Tool>(() => (spaceHeld.value ? 'pan' : props.tool))

function onSpaceDown(event: KeyboardEvent) {
  if (event.code !== 'Space' || event.repeat) return
  const target = event.target as HTMLElement | null
  if (target && /^(INPUT|TEXTAREA|SELECT|BUTTON)$/.test(target.tagName)) return
  // Otherwise the page scrolls while the operator is trying to pan.
  event.preventDefault()
  spaceHeld.value = true
}

function onSpaceUp(event: KeyboardEvent) {
  if (event.code !== 'Space') return
  spaceHeld.value = false
}

function releaseSpace() {
  spaceHeld.value = false
}

const hoverWorld = computed(() => {
  const grid = props.grid
  const cell = hover.value
  if (!grid || !cell) return null
  return cellToWorld(grid, cell.column, cell.row, props.placement)
})

// ── Rendering ────────────────────────────────────────────────────────────────

function ensureBuffer(grid: Grid) {
  if (buffer && buffer.width === grid.width && buffer.height === grid.height) return
  buffer = document.createElement('canvas')
  buffer.width = grid.width
  buffer.height = grid.height
  const context = buffer.getContext('2d')
  image = context ? context.createImageData(grid.width, grid.height) : null
}

function writeCell(pixels: Uint8ClampedArray, index: number, value: number) {
  const colour = COLOUR[value as keyof typeof COLOUR] ?? COLOUR[CELL.unknown]
  const at = index * 4
  pixels[at] = colour[0]
  pixels[at + 1] = colour[1]
  pixels[at + 2] = colour[2]
  pixels[at + 3] = colour[3]
}

/**
 * Push cell values into the offscreen buffer.
 *
 * `indices` null means all of them. Otherwise only those cells are rewritten and
 * only their bounding box is uploaded, which is what keeps a drag responsive on
 * a large map.
 */
function refreshCells(indices: Int32Array | null = null) {
  const grid = props.grid
  if (!grid) return
  ensureBuffer(grid)
  const context = buffer?.getContext('2d')
  if (!buffer || !image || !context) return

  const source = props.preview ?? grid.cells

  if (indices === null) {
    for (let i = 0; i < source.length; i += 1) {
      writeCell(image.data, i, source[i] as number)
    }
    context.putImageData(image, 0, 0)
    blit()
    return
  }

  let left = grid.width
  let right = -1
  let top = grid.height
  let bottom = -1
  for (let slot = 0; slot < indices.length; slot += 1) {
    const index = indices[slot] as number
    writeCell(image.data, index, source[index] as number)
    const x = index % grid.width
    const y = (index - x) / grid.width
    if (x < left) left = x
    if (x > right) right = x
    if (y < top) top = y
    if (y > bottom) bottom = y
  }
  if (right < left) return
  context.putImageData(image, 0, 0, left, top, right - left + 1, bottom - top + 1)
  blit()
}

/**
 * Wipe a canvas and hand back a context in CSS pixels.
 *
 * clearRect is interpreted through the current transform, so clearing correctly
 * depends on that transform being what you assumed — and when it is not, the
 * symptom is drawings that accumulate rather than an error.
 */
function resetContext(target: HTMLCanvasElement): CanvasRenderingContext2D | null {
  const context = target.getContext('2d')
  if (!context) return null
  const ratio = window.devicePixelRatio || 1
  context.setTransform(1, 0, 0, 1, 0, 0)
  context.clearRect(0, 0, target.width, target.height)
  context.setTransform(ratio, 0, 0, ratio, 0, 0)
  return context
}

function blit() {
  const target = canvas.value
  const t = transform.value
  if (!target || !buffer || !t) return
  const context = resetContext(target)
  if (!context) return
  context.imageSmoothingEnabled = false
  context.drawImage(buffer, t.offsetX, t.offsetY, buffer.width * t.scale, buffer.height * t.scale)
  paintOverlay()
}

function cellRect(cell: Cell) {
  const t = transform.value
  if (!t) return null
  return {
    x: t.offsetX + cell.column * t.scale,
    y: t.offsetY + cell.row * t.scale,
    size: t.scale,
  }
}

/** Cursor footprint and shape preview. Never touches the map itself. */
function paintOverlay() {
  const target = overlay.value
  const grid = props.grid
  if (!target || !grid) return
  const context = resetContext(target)
  const t = transform.value
  if (!context || !t) return

  // A cell grid, once a cell is big enough for the lines not to become the
  // picture. Below this, per-cell work is guesswork; above it, without lines the
  // operator cannot tell which cell the cursor is actually in.
  if (t.scale >= GRID_MIN_SCALE) {
    const left = Math.max(0, Math.floor(-t.offsetX / t.scale))
    const top = Math.max(0, Math.floor(-t.offsetY / t.scale))
    const right = Math.min(grid.width, Math.ceil((viewport.value.width - t.offsetX) / t.scale))
    const bottom = Math.min(grid.height, Math.ceil((viewport.value.height - t.offsetY) / t.scale))

    context.lineWidth = 1
    context.strokeStyle = 'rgba(10,11,13,0.14)'
    context.beginPath()
    for (let column = left; column <= right; column += 1) {
      const x = Math.round(t.offsetX + column * t.scale) + 0.5
      context.moveTo(x, t.offsetY + top * t.scale)
      context.lineTo(x, t.offsetY + bottom * t.scale)
    }
    for (let row = top; row <= bottom; row += 1) {
      const y = Math.round(t.offsetY + row * t.scale) + 0.5
      context.moveTo(t.offsetX + left * t.scale, y)
      context.lineTo(t.offsetX + right * t.scale, y)
    }
    context.stroke()
  }

  context.lineWidth = 1
  context.strokeStyle = 'rgba(20,110,245,0.95)'

  const from = props.dragFrom
  const to = props.dragTo
  if (from && to) {
    if (activeTool.value === 'rect') {
      const left = Math.min(from.column, to.column)
      const top = Math.min(from.row, to.row)
      const width = Math.abs(to.column - from.column) + 1
      const height = Math.abs(to.row - from.row) + 1
      context.fillStyle = 'rgba(20,110,245,0.18)'
      context.fillRect(
        t.offsetX + left * t.scale,
        t.offsetY + top * t.scale,
        width * t.scale,
        height * t.scale,
      )
      context.strokeRect(
        t.offsetX + left * t.scale,
        t.offsetY + top * t.scale,
        width * t.scale,
        height * t.scale,
      )
    } else if (activeTool.value === 'line') {
      context.beginPath()
      context.moveTo(t.offsetX + (from.column + 0.5) * t.scale, t.offsetY + (from.row + 0.5) * t.scale)
      context.lineTo(t.offsetX + (to.column + 0.5) * t.scale, t.offsetY + (to.row + 0.5) * t.scale)
      context.lineWidth = Math.max(props.brushCells * t.scale, 1)
      context.strokeStyle = 'rgba(20,110,245,0.45)'
      context.stroke()
    }
    return
  }

  const cell = hover.value
  if (!cell || activeTool.value === 'pan') return
  const rect = cellRect(cell)
  if (!rect) return

  if (activeTool.value === 'fill') {
    context.strokeRect(rect.x, rect.y, Math.max(rect.size, 3), Math.max(rect.size, 3))
    return
  }
  // The brush outline is drawn at its true size, so the operator can see whether
  // a stroke will close a gap before making it.
  const diameter = Math.max(props.brushCells * t.scale, 3)
  context.beginPath()
  context.arc(rect.x + rect.size / 2, rect.y + rect.size / 2, diameter / 2, 0, Math.PI * 2)
  context.stroke()
}

// ── Pointer ──────────────────────────────────────────────────────────────────

function cellAt(event: PointerEvent): Cell | null {
  const rect = wrapper.value?.getBoundingClientRect()
  const grid = props.grid
  const t = transform.value
  if (!rect || !grid || !t || t.scale === 0) return null
  const column = Math.floor((event.clientX - rect.left - t.offsetX) / t.scale)
  const row = Math.floor((event.clientY - rect.top - t.offsetY) / t.scale)
  if (column < 0 || row < 0 || column >= grid.width || row >= grid.height) return null
  return { column, row }
}

const painting = ref(false)
const panning = ref(false)
let activePointer: number | null = null
let panFrom = { x: 0, y: 0, offsetX: 0, offsetY: 0, scale: 1 }

function startPan(event: PointerEvent) {
  const base = transform.value
  if (!base) return
  panning.value = true
  activePointer = event.pointerId
  panFrom = {
    x: event.clientX,
    y: event.clientY,
    offsetX: base.offsetX,
    offsetY: base.offsetY,
    // Captured, not read back mid-drag: the scale must not change while panning.
    scale: base.scale,
  }
  // Pin the view: staying in fit mode would re-fit under the operator's hand.
  view.value = { ...base }
  wrapper.value?.setPointerCapture(event.pointerId)
}

function onPointerDown(event: PointerEvent) {
  // Middle and right always pan, whatever tool is selected, so the view can be
  // moved without first putting the brush down.
  if (event.button !== 0 || activeTool.value === 'pan') {
    event.preventDefault()
    startPan(event)
    return
  }
  const cell = cellAt(event)
  if (!cell) return
  painting.value = true
  activePointer = event.pointerId
  wrapper.value?.setPointerCapture(event.pointerId)
  emit('begin', cell)
}

function onPointerMove(event: PointerEvent) {
  if (panning.value && event.pointerId === activePointer) {
    view.value = {
      scale: panFrom.scale,
      offsetX: panFrom.offsetX + (event.clientX - panFrom.x),
      offsetY: panFrom.offsetY + (event.clientY - panFrom.y),
    }
    blit()
    return
  }

  const cell = cellAt(event)
  const previous = hover.value
  if (cell?.column !== previous?.column || cell?.row !== previous?.row) {
    hover.value = cell
    paintOverlay()
  }
  if (painting.value && event.pointerId === activePointer && cell) emit('extend', cell)
}

function finishPointer(event: PointerEvent) {
  if (event.pointerId !== activePointer) return
  if (painting.value) {
    painting.value = false
    emit('end')
  }
  panning.value = false
  activePointer = null
  wrapper.value?.releasePointerCapture?.(event.pointerId)
}

function onPointerLeave() {
  if (painting.value || panning.value) return
  hover.value = null
  paintOverlay()
}

// ── Zoom ─────────────────────────────────────────────────────────────────────

function zoomAt(factor: number, anchorX: number, anchorY: number) {
  const base = transform.value
  if (!base) return
  const next = Math.min(Math.max(base.scale * factor, ZOOM_MIN), ZOOM_MAX)
  const ratio = next / base.scale
  view.value = {
    scale: next,
    offsetX: anchorX - (anchorX - base.offsetX) * ratio,
    offsetY: anchorY - (anchorY - base.offsetY) * ratio,
  }
  blit()
}

function onWheel(event: WheelEvent) {
  event.preventDefault()
  const rect = wrapper.value?.getBoundingClientRect()
  if (!rect) return
  zoomAt(
    event.deltaY < 0 ? ZOOM_STEP : 1 / ZOOM_STEP,
    event.clientX - rect.left,
    event.clientY - rect.top,
  )
}

function zoomCentre(factor: number) {
  zoomAt(factor, viewport.value.width / 2, viewport.value.height / 2)
}

function resetView() {
  view.value = null
  blit()
}

// ── Sizing ───────────────────────────────────────────────────────────────────

function resize() {
  const host = wrapper.value
  const target = canvas.value
  const layer = overlay.value
  if (!host || !target || !layer) return
  const ratio = window.devicePixelRatio || 1
  const { width, height } = host.getBoundingClientRect()
  viewport.value = { width, height }
  for (const surface of [target, layer]) {
    surface.width = Math.max(1, Math.round(width * ratio))
    surface.height = Math.max(1, Math.round(height * ratio))
    surface.style.width = `${width}px`
    surface.style.height = `${height}px`
  }
  refreshCells(null)
}

let observer: ResizeObserver | null = null

onMounted(() => {
  resize()
  observer = new ResizeObserver(resize)
  if (wrapper.value) observer.observe(wrapper.value)
  window.addEventListener('keydown', onSpaceDown)
  window.addEventListener('keyup', onSpaceUp)
  // A tab switch while space is down never delivers the keyup.
  window.addEventListener('blur', releaseSpace)
})

onBeforeUnmount(() => {
  observer?.disconnect()
  observer = null
  window.removeEventListener('keydown', onSpaceDown)
  window.removeEventListener('keyup', onSpaceUp)
  window.removeEventListener('blur', releaseSpace)
})

// A different map replaces the buffer entirely.
watch(
  () => props.grid,
  () => {
    buffer = null
    image = null
    view.value = null
    refreshCells(null)
  },
)

watch(
  [() => props.dragFrom, () => props.dragTo, () => props.brushCells, () => props.tool, spaceHeld],
  () => paintOverlay(),
)

// Swapping the baseline in or out is a full repaint: every cell may differ.
watch(() => props.preview, () => refreshCells(null))

defineExpose({ refreshCells, resetView })
</script>

<template>
  <div class="space-y-xs">
    <!-- touch-none: without it a finger stroke scrolls the page instead of painting. -->
    <div
      ref="wrapper"
      class="relative h-[min(68vh,40rem)] w-full touch-none overflow-hidden rounded-surface border border-hairline bg-[#e9ebee] select-none"
      :class="activeTool === 'pan' || panning ? 'cursor-grab' : 'cursor-crosshair'"
      @pointerdown="onPointerDown"
      @pointermove="onPointerMove"
      @pointerup="finishPointer"
      @pointercancel="finishPointer"
      @pointerleave="onPointerLeave"
      @wheel="onWheel"
      @contextmenu.prevent
    >
      <canvas ref="canvas" class="absolute inset-0" />
      <canvas ref="overlay" class="pointer-events-none absolute inset-0" />

      <div class="absolute right-xs top-xs flex flex-col gap-xxs">
        <Button variant="secondary" size="icon-sm" title="Zoom in" @click="zoomCentre(ZOOM_STEP)">
          <Plus :size="13" />
        </Button>
        <Button variant="secondary" size="icon-sm" title="Zoom out" @click="zoomCentre(1 / ZOOM_STEP)">
          <Minus :size="13" />
        </Button>
        <Button variant="secondary" size="icon-sm" title="Fit map" @click="resetView">
          <Maximize :size="13" />
        </Button>
      </div>
    </div>

    <div class="flex flex-wrap items-center gap-sm text-caption text-muted">
      <span class="font-data">{{ pxPerCell.toFixed(1) }} px/cell</span>
      <span v-if="hover" class="font-data">cell {{ hover.column }}, {{ hover.row }}</span>
      <span v-if="hoverWorld" class="font-data">
        {{ hoverWorld.x.toFixed(2) }}, {{ hoverWorld.y.toFixed(2) }} m
      </span>
      <span v-if="props.preview" class="font-medium text-status-act">Showing original</span>
      <span v-else-if="spaceHeld" class="font-medium text-primary">Pan (space)</span>
      <span class="ml-auto touch:hidden">Hold space or middle-drag to pan · wheel to zoom</span>
    </div>
  </div>
</template>
