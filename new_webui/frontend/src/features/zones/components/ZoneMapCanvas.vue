<script setup lang="ts">
/**
 * The map with its zones drawn on it.
 *
 * Polygons are held in metres and converted to screen only at the last step.
 * Storing or dragging in pixels would tie a zone to one zoom level and one map
 * resolution, and a re-survey at a finer resolution would move every zone
 * while every number still looked right.
 *
 * Three gestures, and they are kept apart on purpose:
 *   drawing  — click to drop corners, Enter or a click on the first one to close
 *   shaping  — drag a corner of the selected zone
 *   looking  — drag anywhere else to pan
 */
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { Maximize, Minus, Plus } from 'lucide-vue-next'
import { CELL, gridToWorld, worldToGrid, type Grid } from '@/domain/map/pgm'
import { pointInPolygon, type Zone, type ZoneKind, type ZonePoint } from '@/domain/types'
import { ZONE_KIND_STYLE } from '../zoneKind'
import { Button } from '@/shared/ui/button'

const props = defineProps<{
  grid: Grid | null
  placement: { resolution: number; originX: number; originY: number }
  zones: Zone[]
  selectedId: string | null
  /** The polygon being drawn, in metres. Empty when not drawing. */
  drawing: ZonePoint[] | null
  /** Colour for the in-progress outline, so it reads as the kind it will become. */
  drawingKind: ZoneKind
}>()

const emit = defineEmits<{
  select: [id: string | null]
  /** A corner dropped while drawing. */
  addPoint: [point: ZonePoint]
  /** The drawn ring is closed and ready to name. */
  closeDrawing: []
  /** A corner of an existing zone moved. */
  movePoint: [payload: { id: string; index: number; point: ZonePoint }]
}>()

const COLOUR = {
  [CELL.occupied]: [26, 26, 26, 255],
  [CELL.unknown]: [128, 132, 140, 255],
  [CELL.free]: [246, 247, 248, 255],
} as const

const ZOOM_MIN = 0.4
const ZOOM_MAX = 40
const ZOOM_STEP = 1.25
/** Screen radius of a corner handle. Fixed, so it stays grabbable at any zoom. */
const HANDLE_RADIUS = 5
/** How close a click must be to the first corner to close the ring. */
const CLOSE_RADIUS = 10

const wrapper = ref<HTMLDivElement | null>(null)
const canvas = ref<HTMLCanvasElement | null>(null)
const overlay = ref<HTMLCanvasElement | null>(null)
const viewport = ref({ width: 0, height: 0 })

let buffer: HTMLCanvasElement | null = null

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
const isDrawing = computed(() => props.drawing !== null)
const hoverWorld = ref<ZonePoint | null>(null)

// ── Projection ───────────────────────────────────────────────────────────────

function toScreen(point: ZonePoint): { sx: number; sy: number } | null {
  const grid = props.grid
  const t = transform.value
  if (!grid || !t) return null
  const { gx, gy } = worldToGrid(grid, point[0], point[1], props.placement)
  return { sx: t.offsetX + gx * t.scale, sy: t.offsetY + gy * t.scale }
}

function toWorld(sx: number, sy: number): ZonePoint | null {
  const grid = props.grid
  const t = transform.value
  if (!grid || !t || t.scale === 0) return null
  const { x, y } = gridToWorld(
    grid,
    (sx - t.offsetX) / t.scale,
    (sy - t.offsetY) / t.scale,
    props.placement,
  )
  return [x, y]
}

function pointerAt(event: PointerEvent): { sx: number; sy: number } | null {
  const rect = wrapper.value?.getBoundingClientRect()
  if (!rect) return null
  return { sx: event.clientX - rect.left, sy: event.clientY - rect.top }
}

/** A corner handle of the selected zone under the pointer, if any. */
function handleAt(sx: number, sy: number): number | null {
  const selected = props.zones.find((zone) => zone.id === props.selectedId)
  if (!selected) return null
  for (let index = 0; index < selected.polygon.length; index += 1) {
    const screen = toScreen(selected.polygon[index] as ZonePoint)
    if (!screen) continue
    if (Math.hypot(screen.sx - sx, screen.sy - sy) <= HANDLE_RADIUS + 4) return index
  }
  return null
}

function zoneAt(sx: number, sy: number): Zone | null {
  const world = toWorld(sx, sy)
  if (!world) return null
  // Reversed, so the zone drawn last — and therefore on top — is the one hit.
  for (let i = props.zones.length - 1; i >= 0; i -= 1) {
    const zone = props.zones[i] as Zone
    if (pointInPolygon(zone.polygon, world[0], world[1])) return zone
  }
  return null
}

// ── Rendering ────────────────────────────────────────────────────────────────

function paintMap() {
  const grid = props.grid
  if (!grid) return
  if (!buffer || buffer.width !== grid.width || buffer.height !== grid.height) {
    buffer = document.createElement('canvas')
    buffer.width = grid.width
    buffer.height = grid.height
  }
  const context = buffer.getContext('2d')
  if (!context) return
  const image = context.createImageData(grid.width, grid.height)
  for (let i = 0; i < grid.cells.length; i += 1) {
    const colour = COLOUR[grid.cells[i] as keyof typeof COLOUR] ?? COLOUR[CELL.unknown]
    const at = i * 4
    image.data[at] = colour[0]
    image.data[at + 1] = colour[1]
    image.data[at + 2] = colour[2]
    image.data[at + 3] = colour[3]
  }
  context.putImageData(image, 0, 0)
  blit()
}

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
  // Nearest-neighbour: an occupancy grid is data, and smoothing it invents free
  // space between an obstacle and the cell beside it.
  context.imageSmoothingEnabled = false
  context.drawImage(buffer, t.offsetX, t.offsetY, buffer.width * t.scale, buffer.height * t.scale)
  paintZones()
}

function tracePath(context: CanvasRenderingContext2D, polygon: ZonePoint[], close: boolean) {
  context.beginPath()
  polygon.forEach((point, index) => {
    const screen = toScreen(point)
    if (!screen) return
    if (index === 0) context.moveTo(screen.sx, screen.sy)
    else context.lineTo(screen.sx, screen.sy)
  })
  if (close) context.closePath()
}

function drawZone(context: CanvasRenderingContext2D, zone: Zone, selected: boolean) {
  const colour = ZONE_KIND_STYLE[zone.kind].colour
  tracePath(context, zone.polygon, true)

  // A disabled zone still exists and still takes up screen: drawn faint, so
  // "there but doing nothing" reads differently from "not there".
  context.globalAlpha = zone.enabled ? 1 : 0.35
  context.fillStyle = colour
  const previousAlpha = context.globalAlpha
  context.globalAlpha = previousAlpha * (selected ? 0.32 : 0.18)
  context.fill()

  context.globalAlpha = previousAlpha
  context.strokeStyle = colour
  context.lineWidth = selected ? 2.5 : 1.5
  if (!zone.enabled) context.setLineDash([5, 4])
  context.stroke()
  context.setLineDash([])

  if (selected) {
    // Handles only on the selected one. Every zone showing its corners turns a
    // busy map into a field of dots with nothing to grab.
    for (const point of zone.polygon) {
      const screen = toScreen(point)
      if (!screen) continue
      context.beginPath()
      context.arc(screen.sx, screen.sy, HANDLE_RADIUS, 0, Math.PI * 2)
      context.fillStyle = '#ffffff'
      context.fill()
      context.lineWidth = 2
      context.strokeStyle = colour
      context.stroke()
    }
  }

  const label = toScreen(zone.polygon[0] as ZonePoint)
  if (label) {
    context.font = '11px Inter, system-ui, sans-serif'
    context.textAlign = 'left'
    context.textBaseline = 'bottom'
    const width = context.measureText(zone.name).width
    context.fillStyle = 'rgba(255,255,255,0.88)'
    context.fillRect(label.sx + 2, label.sy - 15, width + 6, 14)
    context.fillStyle = '#0a0b0d'
    context.fillText(zone.name, label.sx + 5, label.sy - 3)
  }
  context.globalAlpha = 1
}

function paintZones() {
  const target = overlay.value
  if (!target || !props.grid) return
  const context = resetContext(target)
  if (!context) return

  for (const zone of props.zones) {
    drawZone(context, zone, zone.id === props.selectedId)
  }

  const drawing = props.drawing
  if (!drawing || drawing.length === 0) return

  const colour = ZONE_KIND_STYLE[props.drawingKind].colour
  const preview = hoverWorld.value ? [...drawing, hoverWorld.value] : drawing

  // Open while it is being drawn, closed when there is enough to enclose an
  // area — so the operator can see the shape before committing to it.
  tracePath(context, preview, preview.length >= 3)
  if (preview.length >= 3) {
    context.fillStyle = colour
    context.globalAlpha = 0.16
    context.fill()
    context.globalAlpha = 1
  }
  context.strokeStyle = colour
  context.lineWidth = 2
  context.setLineDash([6, 4])
  context.stroke()
  context.setLineDash([])

  drawing.forEach((point, index) => {
    const screen = toScreen(point)
    if (!screen) return
    context.beginPath()
    context.arc(screen.sx, screen.sy, index === 0 ? HANDLE_RADIUS + 2 : HANDLE_RADIUS, 0, Math.PI * 2)
    // The first corner is drawn larger: it is the one that closes the ring, and
    // nothing else on screen says so.
    context.fillStyle = index === 0 ? colour : '#ffffff'
    context.fill()
    context.lineWidth = 2
    context.strokeStyle = colour
    context.stroke()
  })
}

// ── Pointer ──────────────────────────────────────────────────────────────────

const panning = ref(false)
const draggingHandle = ref<number | null>(null)
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
    scale: base.scale,
  }
  view.value = { ...base }
  wrapper.value?.setPointerCapture(event.pointerId)
}

function onPointerDown(event: PointerEvent) {
  if (event.button !== 0) {
    event.preventDefault()
    startPan(event)
    return
  }
  const at = pointerAt(event)
  if (!at) return

  if (isDrawing.value) {
    const world = toWorld(at.sx, at.sy)
    if (!world) return
    const first = props.drawing?.[0]
    const firstScreen = first ? toScreen(first) : null
    // Clicking the first corner closes the ring, once there is an area to close.
    if (
      firstScreen &&
      (props.drawing?.length ?? 0) >= 3 &&
      Math.hypot(firstScreen.sx - at.sx, firstScreen.sy - at.sy) <= CLOSE_RADIUS
    ) {
      emit('closeDrawing')
      return
    }
    emit('addPoint', world)
    return
  }

  const handle = handleAt(at.sx, at.sy)
  if (handle !== null) {
    draggingHandle.value = handle
    activePointer = event.pointerId
    wrapper.value?.setPointerCapture(event.pointerId)
    return
  }

  const hit = zoneAt(at.sx, at.sy)
  if (hit) {
    emit('select', hit.id)
    return
  }
  // Empty space pans rather than clearing the selection on the way, so a nudge
  // of the view does not lose what was being worked on.
  emit('select', null)
  startPan(event)
}

function onPointerMove(event: PointerEvent) {
  const at = pointerAt(event)
  if (at) hoverWorld.value = toWorld(at.sx, at.sy)

  if (panning.value && event.pointerId === activePointer) {
    view.value = {
      scale: panFrom.scale,
      offsetX: panFrom.offsetX + (event.clientX - panFrom.x),
      offsetY: panFrom.offsetY + (event.clientY - panFrom.y),
    }
    blit()
    return
  }

  if (draggingHandle.value !== null && event.pointerId === activePointer && at) {
    const world = toWorld(at.sx, at.sy)
    if (world && props.selectedId) {
      emit('movePoint', { id: props.selectedId, index: draggingHandle.value, point: world })
    }
    return
  }

  if (isDrawing.value) paintZones()
}

function finishPointer(event: PointerEvent) {
  if (event.pointerId !== activePointer) return
  draggingHandle.value = null
  panning.value = false
  activePointer = null
  wrapper.value?.releasePointerCapture?.(event.pointerId)
}

function onPointerLeave() {
  if (panning.value || draggingHandle.value !== null) return
  hoverWorld.value = null
  paintZones()
}

function onDoubleClick() {
  // A second way to close, because clicking exactly on the first corner is
  // fiddly when the shape is small on screen.
  if (isDrawing.value && (props.drawing?.length ?? 0) >= 3) emit('closeDrawing')
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
  if (!host || !canvas.value || !overlay.value) return
  const ratio = window.devicePixelRatio || 1
  const { width, height } = host.getBoundingClientRect()
  viewport.value = { width, height }
  for (const surface of [canvas.value, overlay.value]) {
    surface.width = Math.max(1, Math.round(width * ratio))
    surface.height = Math.max(1, Math.round(height * ratio))
    surface.style.width = `${width}px`
    surface.style.height = `${height}px`
  }
  paintMap()
}

let observer: ResizeObserver | null = null

onMounted(() => {
  resize()
  observer = new ResizeObserver(resize)
  if (wrapper.value) observer.observe(wrapper.value)
})

onBeforeUnmount(() => {
  observer?.disconnect()
  observer = null
})

watch(
  () => props.grid,
  () => {
    buffer = null
    view.value = null
    paintMap()
  },
)

watch(
  [() => props.zones, () => props.selectedId, () => props.drawing],
  () => paintZones(),
  { deep: true },
)

defineExpose({ resetView })
</script>

<template>
  <div
    ref="wrapper"
    class="relative h-full w-full select-none overflow-hidden bg-[#e9ebee]"
    :class="
      isDrawing
        ? 'cursor-crosshair'
        : draggingHandle !== null
          ? 'cursor-grabbing'
          : 'cursor-grab'
    "
    @pointerdown="onPointerDown"
    @pointermove="onPointerMove"
    @pointerup="finishPointer"
    @pointercancel="finishPointer"
    @pointerleave="onPointerLeave"
    @dblclick="onDoubleClick"
    @wheel="onWheel"
    @contextmenu.prevent
  >
    <canvas ref="canvas" class="absolute inset-0" />
    <canvas ref="overlay" class="pointer-events-none absolute inset-0" />

    <div
      v-if="isDrawing"
      class="pointer-events-none absolute left-1/2 top-sm -translate-x-1/2 rounded-chip bg-primary px-sm py-xxs text-caption text-on-primary shadow-soft"
    >
      {{
        (props.drawing?.length ?? 0) < 3
          ? `Click each corner · ${3 - (props.drawing?.length ?? 0)} more to enclose an area`
          : 'Click the first corner or double-click to finish · Esc to cancel'
      }}
    </div>

    <div class="absolute right-sm top-sm flex flex-col gap-xxs">
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

    <div
      class="pointer-events-none absolute bottom-sm left-sm flex items-center gap-base rounded-control bg-surface/85 px-sm py-xxs text-caption text-muted backdrop-blur-[2px]"
    >
      <slot name="legend" />
      <span v-if="hoverWorld" class="font-data text-ink">
        {{ hoverWorld[0].toFixed(2) }}, {{ hoverWorld[1].toFixed(2) }} m
      </span>
    </div>
  </div>
</template>
