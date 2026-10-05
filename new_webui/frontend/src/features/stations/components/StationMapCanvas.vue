<script setup lang="ts">
/**
 * The map with its stations on it.
 *
 * Placement is done here rather than by typing coordinates because a station is
 * a physical place: an operator knows "the bench by the shutter", not
 * "(-1.10, 3.05)". The numbers stay visible so a pose captured from a robot can
 * still be checked against one placed by hand.
 *
 * Markers are drawn in world units and only converted to screen at the last
 * step. Storing or dragging in pixels would tie a station to one zoom level and
 * one image resolution, and a re-survey at a finer resolution would move every
 * station without anything reporting it.
 */
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { Maximize, Minus, Plus } from 'lucide-vue-next'
import { CELL, gridToWorld, worldToGrid, type Grid } from '@/domain/map/pgm'
import { Button } from '@/shared/ui/button'
import type { Station } from '@/domain/types'
import { STATION_TYPE_STYLE } from '../stationType'

const props = defineProps<{
  grid: Grid | null
  placement: { resolution: number; originX: number; originY: number }
  stations: Station[]
  selectedId: string | null
  /** While true, a drag on empty space proposes a new station and its heading. */
  placing: boolean
  /** Live robot pose in the map frame, for the teach-from-robot flow. */
  robotPose?: { x: number; y: number; yaw: number } | null
  /**
   * Station ids in visiting order, drawn as a numbered path. For the mission
   * editor: a route read as a list of names says nothing about whether it
   * zig-zags across the floor.
   */
  route?: string[]
  /** False where stations are picked rather than placed: a click must not nudge one. */
  movable?: boolean
  /** Hides the legend and readout, for while a card covers the bottom of the map. */
  hideLegend?: boolean
}>()

const emit = defineEmits<{
  place: [pose: { x: number; y: number; yaw: number }]
  select: [id: string | null]
  move: [payload: { id: string; x: number; y: number }]
}>()

/** Same palette as every other map view, so a map looks the same everywhere. */
const COLOUR = {
  [CELL.occupied]: [26, 26, 26, 255],
  [CELL.unknown]: [128, 132, 140, 255],
  [CELL.free]: [246, 247, 248, 255],
} as const

/** Ink, so the robot does not compete with the station hues. */
const ROBOT_COLOUR = '#0a0b0d'

/** Ink as well: the route connects stations of every type, so it takes none of their hues. */
const ROUTE_COLOUR = '#0a0b0d'

const ZOOM_MIN = 0.4
const ZOOM_MAX = 40
const ZOOM_STEP = 1.25
/** Screen radius of a marker. Fixed, so a station stays hittable at any zoom. */
const MARKER_RADIUS = 9

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

const hoverWorld = ref<{ x: number; y: number } | null>(null)
/** Over a marker, so the cursor can say "this is clickable" before the click. */
const hoverStation = ref(false)

/**
 * Below this drag distance the gesture is a plain click, and the station is
 * placed facing east.
 *
 * A station's yaw is the heading the robot arrives on, and a dock approached
 * from the wrong side is not reached. Dragging says which way; releasing
 * without dragging has to mean something, and zero is the only answer that
 * does not pretend to know.
 */
const PLACE_DRAG_THRESHOLD_PX = 12

/** Where a placing gesture began, in screen pixels, while it is in flight. */
let placeFrom: { sx: number; sy: number; x: number; y: number } | null = null
const placePreview = ref<{ x: number; y: number; yaw: number } | null>(null)

// ── Projection ───────────────────────────────────────────────────────────────

function toScreen(x: number, y: number): { sx: number; sy: number } | null {
  const grid = props.grid
  const t = transform.value
  if (!grid || !t) return null
  const { gx, gy } = worldToGrid(grid, x, y, props.placement)
  return { sx: t.offsetX + gx * t.scale, sy: t.offsetY + gy * t.scale }
}

function toWorld(sx: number, sy: number): { x: number; y: number } | null {
  const grid = props.grid
  const t = transform.value
  if (!grid || !t || t.scale === 0) return null
  return gridToWorld(grid, (sx - t.offsetX) / t.scale, (sy - t.offsetY) / t.scale, props.placement)
}

function pointerAt(event: PointerEvent): { sx: number; sy: number } | null {
  const rect = wrapper.value?.getBoundingClientRect()
  if (!rect) return null
  return { sx: event.clientX - rect.left, sy: event.clientY - rect.top }
}

function stationAt(sx: number, sy: number): Station | null {
  // Reversed, so the marker drawn last — and therefore on top — is the one hit.
  for (let i = props.stations.length - 1; i >= 0; i -= 1) {
    const station = props.stations[i] as Station
    const screen = toScreen(station.x, station.y)
    if (!screen) continue
    if (Math.hypot(screen.sx - sx, screen.sy - sy) <= MARKER_RADIUS + 3) return station
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
  paintMarkers()
}

function drawMarker(context: CanvasRenderingContext2D, station: Station, selected: boolean) {
  const screen = toScreen(station.x, station.y)
  if (!screen) return
  const colour = STATION_TYPE_STYLE[station.type].colour

  // Heading first, so the disc covers its root rather than the arrow covering
  // the disc. An approach direction is not decoration: a dock reached from the
  // wrong side is not reached.
  const length = MARKER_RADIUS + 11
  context.strokeStyle = colour
  context.lineWidth = 2
  context.beginPath()
  context.moveTo(screen.sx, screen.sy)
  // Canvas y grows downward while a ROS yaw turns counter-clockwise.
  context.lineTo(
    screen.sx + Math.cos(station.yaw) * length,
    screen.sy - Math.sin(station.yaw) * length,
  )
  context.stroke()

  context.beginPath()
  context.arc(screen.sx, screen.sy, MARKER_RADIUS, 0, Math.PI * 2)
  context.fillStyle = colour
  context.fill()
  context.lineWidth = selected ? 3 : 2
  context.strokeStyle = selected ? '#0a0b0d' : '#ffffff'
  context.stroke()

  context.font = '11px Inter, system-ui, sans-serif'
  context.textAlign = 'center'
  context.textBaseline = 'top'
  const label = station.name
  const width = context.measureText(label).width
  const top = screen.sy + MARKER_RADIUS + 4
  context.fillStyle = 'rgba(255,255,255,0.88)'
  context.fillRect(screen.sx - width / 2 - 3, top - 1, width + 6, 14)
  context.fillStyle = '#0a0b0d'
  context.fillText(label, screen.sx, top)
}

/** The route's path, under the markers so the discs stay on top of it. */
function drawRoute(context: CanvasRenderingContext2D, points: { sx: number; sy: number }[]) {
  if (points.length < 2) return
  context.save()
  context.lineJoin = 'round'
  context.lineCap = 'round'
  // A white underlay, so the path stays legible across black walls.
  for (const [style, width] of [
    ['rgba(255,255,255,0.9)', 6],
    [ROUTE_COLOUR, 2.5],
  ] as const) {
    context.strokeStyle = style
    context.lineWidth = width
    context.setLineDash(style === ROUTE_COLOUR ? [7, 5] : [])
    context.beginPath()
    points.forEach((point, index) =>
      index === 0 ? context.moveTo(point.sx, point.sy) : context.lineTo(point.sx, point.sy),
    )
    context.stroke()
  }
  context.setLineDash([])

  // A chevron at each leg's midpoint: a dashed line alone does not say which
  // way round the loop goes.
  context.fillStyle = ROUTE_COLOUR
  for (let i = 1; i < points.length; i += 1) {
    const from = points[i - 1] as { sx: number; sy: number }
    const to = points[i] as { sx: number; sy: number }
    if (Math.hypot(to.sx - from.sx, to.sy - from.sy) < MARKER_RADIUS * 4) continue
    const angle = Math.atan2(to.sy - from.sy, to.sx - from.sx)
    const mx = (from.sx + to.sx) / 2
    const my = (from.sy + to.sy) / 2
    context.beginPath()
    context.moveTo(mx + Math.cos(angle) * 6, my + Math.sin(angle) * 6)
    context.lineTo(mx + Math.cos(angle + 2.5) * 6, my + Math.sin(angle + 2.5) * 6)
    context.lineTo(mx + Math.cos(angle - 2.5) * 6, my + Math.sin(angle - 2.5) * 6)
    context.closePath()
    context.fill()
  }
  context.restore()
}

/**
 * Step numbers beside each stop. A station visited twice gets "1·3", not two
 * badges stacked where only the top one can be read.
 */
function drawStepBadges(context: CanvasRenderingContext2D, route: string[]) {
  const numbers = new Map<string, number[]>()
  route.forEach((id, index) => numbers.set(id, [...(numbers.get(id) ?? []), index + 1]))
  context.save()
  context.font = '600 10px Inter, system-ui, sans-serif'
  context.textAlign = 'center'
  context.textBaseline = 'middle'
  for (const [id, steps] of numbers) {
    const station = props.stations.find((candidate) => candidate.id === id)
    const screen = station && toScreen(station.x, station.y)
    if (!screen) continue
    const label = steps.join('·')
    const width = Math.max(16, context.measureText(label).width + 8)
    const cx = screen.sx + MARKER_RADIUS + width / 2 - 2
    const cy = screen.sy - MARKER_RADIUS - 2
    context.beginPath()
    context.roundRect(cx - width / 2, cy - 8, width, 16, 8)
    context.fillStyle = ROUTE_COLOUR
    context.fill()
    context.strokeStyle = '#ffffff'
    context.lineWidth = 1.5
    context.stroke()
    context.fillStyle = '#ffffff'
    context.fillText(label, cx, cy + 0.5)
  }
  context.restore()
}

function paintMarkers() {
  const target = overlay.value
  if (!target || !props.grid) return
  const context = resetContext(target)
  if (!context) return

  if (props.robotPose) {
    const screen = toScreen(props.robotPose.x, props.robotPose.y)
    if (screen) {
      // Neutral, not another hue. The station types already use four saturated
      // colours, and the robot sharing one of them — it was the same blue as a
      // Pick station — makes two unrelated things read as the same kind.
      //
      // Drawn under the stations: it moves, and a moving marker must not cover
      // the fixed ones the operator is placing.
      const heading = {
        x: screen.sx + Math.cos(props.robotPose.yaw) * 17,
        y: screen.sy - Math.sin(props.robotPose.yaw) * 17,
      }
      // A white underlay first, so the marker stays legible over black walls.
      context.strokeStyle = 'rgba(255,255,255,0.9)'
      context.lineWidth = 5
      context.beginPath()
      context.moveTo(screen.sx, screen.sy)
      context.lineTo(heading.x, heading.y)
      context.stroke()

      context.beginPath()
      context.arc(screen.sx, screen.sy, 7, 0, Math.PI * 2)
      context.fillStyle = 'rgba(255,255,255,0.75)'
      context.fill()
      context.strokeStyle = ROBOT_COLOUR
      context.lineWidth = 2
      context.stroke()

      context.beginPath()
      context.moveTo(screen.sx, screen.sy)
      context.lineTo(heading.x, heading.y)
      context.stroke()
    }
  }

  const route = props.route ?? []
  if (route.length) {
    const points = route
      .map((id) => props.stations.find((station) => station.id === id))
      .map((station) => (station ? toScreen(station.x, station.y) : null))
      .filter((point): point is { sx: number; sy: number } => point !== null)
    drawRoute(context, points)
  }

  for (const station of props.stations) {
    drawMarker(context, station, station.id === props.selectedId)
  }

  if (route.length) drawStepBadges(context, route)

  // The gesture in flight, drawn last so it sits over everything it is being
  // aimed between.
  const preview = placePreview.value
  if (preview) {
    const screen = toScreen(preview.x, preview.y)
    if (screen) {
      const length = MARKER_RADIUS + 22
      const tip = {
        x: screen.sx + Math.cos(preview.yaw) * length,
        y: screen.sy - Math.sin(preview.yaw) * length,
      }
      context.strokeStyle = 'rgba(255,255,255,0.9)'
      context.lineWidth = 5
      context.beginPath()
      context.moveTo(screen.sx, screen.sy)
      context.lineTo(tip.x, tip.y)
      context.stroke()

      context.strokeStyle = '#0a0b0d'
      context.lineWidth = 2
      context.beginPath()
      context.moveTo(screen.sx, screen.sy)
      context.lineTo(tip.x, tip.y)
      context.stroke()

      // An arrowhead, because a bare line reads as a radius rather than a
      // direction: without it the operator cannot tell which end is the front.
      const wing = 7
      for (const side of [2.6, -2.6]) {
        context.beginPath()
        context.moveTo(tip.x, tip.y)
        context.lineTo(
          tip.x + Math.cos(preview.yaw + side) * wing,
          tip.y - Math.sin(preview.yaw + side) * wing,
        )
        context.stroke()
      }

      context.beginPath()
      context.arc(screen.sx, screen.sy, MARKER_RADIUS, 0, Math.PI * 2)
      context.fillStyle = 'rgba(255,255,255,0.85)'
      context.fill()
      context.strokeStyle = '#0a0b0d'
      context.lineWidth = 2
      context.stroke()
    }
  }
}

// ── Pointer ──────────────────────────────────────────────────────────────────

const panning = ref(false)
const dragging = ref<string | null>(null)
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

  const hit = stationAt(at.sx, at.sy)
  if (hit && props.movable === false) {
    emit('select', hit.id)
    return
  }
  if (hit) {
    dragging.value = hit.id
    activePointer = event.pointerId
    emit('select', hit.id)
    wrapper.value?.setPointerCapture(event.pointerId)
    return
  }
  // Empty space with no station under it pans, unless the operator has asked to
  // place one. Panning by default means the map can be explored without
  // scattering stations across it.
  if (!props.placing) {
    emit('select', null)
    startPan(event)
    return
  }

  const world = toWorld(at.sx, at.sy)
  if (!world) return
  placeFrom = { sx: at.sx, sy: at.sy, x: world.x, y: world.y }
  placePreview.value = { ...world, yaw: 0 }
  activePointer = event.pointerId
  wrapper.value?.setPointerCapture(event.pointerId)
  paintMarkers()
}

function onPointerMove(event: PointerEvent) {
  const at = pointerAt(event)
  if (at) {
    hoverWorld.value = toWorld(at.sx, at.sy)
    hoverStation.value = stationAt(at.sx, at.sy) !== null
  }

  if (panning.value && event.pointerId === activePointer) {
    view.value = {
      scale: panFrom.scale,
      offsetX: panFrom.offsetX + (event.clientX - panFrom.x),
      offsetY: panFrom.offsetY + (event.clientY - panFrom.y),
    }
    blit()
    return
  }

  if (dragging.value && event.pointerId === activePointer && at) {
    const world = toWorld(at.sx, at.sy)
    if (!world) return
    emit('move', { id: dragging.value, x: world.x, y: world.y })
    return
  }

  if (placeFrom && event.pointerId === activePointer && at) {
    const travelled = Math.hypot(at.sx - placeFrom.sx, at.sy - placeFrom.sy)
    // Canvas y grows downward while a ROS yaw turns counter-clockwise.
    const yaw =
      travelled < PLACE_DRAG_THRESHOLD_PX
        ? 0
        : Math.atan2(-(at.sy - placeFrom.sy), at.sx - placeFrom.sx)
    placePreview.value = { x: placeFrom.x, y: placeFrom.y, yaw }
    paintMarkers()
    return
  }

  paintMarkers()
}

function finishPointer(event: PointerEvent) {
  if (event.pointerId !== activePointer && !props.placing) return

  if (placeFrom && !panning.value && !dragging.value) {
    emit('place', placePreview.value ?? { x: placeFrom.x, y: placeFrom.y, yaw: 0 })
  }

  placeFrom = null
  placePreview.value = null
  dragging.value = null
  panning.value = false
  activePointer = null
  wrapper.value?.releasePointerCapture?.(event.pointerId)
}

function onPointerLeave() {
  if (panning.value || dragging.value) return
  hoverWorld.value = null
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
  [() => props.stations, () => props.selectedId, () => props.robotPose, () => props.route],
  () => paintMarkers(),
  { deep: true },
)

defineExpose({ resetView })
</script>

<template>
  <!--
    The map fills whatever it is given.

    No aspect-ratio box any more. Fitting the frame to the data only helps while
    the frame is a visible card, where leftover space reads as a mistake; once
    the map *is* the page, space around it reads as canvas — which is why every
    map tool letterboxes and nobody minds. Filling also means the map grows with
    the window instead of being capped by a number someone has to keep tuning.

    touch-none: otherwise the browser claims a finger drag as a scroll and
    cancels the pointer, so a pan or a marker drag stops after a few pixels.
  -->
  <div
    ref="wrapper"
    class="relative h-full w-full touch-none select-none overflow-hidden bg-[#e9ebee]"
    :class="
      props.placing
        ? 'cursor-crosshair'
        : dragging || panning
          ? 'cursor-grabbing'
          : hoverStation
            ? 'cursor-pointer'
            : 'cursor-grab'
    "
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

    <div
      v-if="props.placing"
      class="pointer-events-none absolute left-1/2 top-sm max-w-[calc(100%-1rem)] -translate-x-1/2 rounded-chip bg-primary px-sm py-xxs text-center text-caption text-on-primary shadow-soft"
    >
      Tap or click where the station goes, drag to aim it<span class="hidden lg:inline">
        · Esc to cancel</span>
    </div>

    <div class="absolute right-sm top-sm flex flex-col gap-xxs">
      <Button variant="secondary" size="icon-sm" title="Zoom in" @click="zoomCentre(ZOOM_STEP)">
        <Plus :size="13" />
      </Button>
      <Button
        variant="secondary"
        size="icon-sm"
        title="Zoom out"
        @click="zoomCentre(1 / ZOOM_STEP)"
      >
        <Minus :size="13" />
      </Button>
      <Button variant="secondary" size="icon-sm" title="Fit map" @click="resetView">
        <Maximize :size="13" />
      </Button>
    </div>

    <!--
      Over the map, not beside it. A readout in its own row costs a strip of map
      on every screen in order to show a number that is read occasionally.
    -->
    <div
      v-if="!props.hideLegend"
      class="pointer-events-none absolute bottom-sm left-sm flex max-w-[calc(100%-1rem)] flex-wrap items-center gap-x-base gap-y-xxs rounded-control bg-surface/85 px-sm py-xxs text-caption text-muted backdrop-blur-[2px]"
    >
      <slot name="legend" />
      <span v-if="hoverWorld" class="font-data text-ink">
        {{ hoverWorld.x.toFixed(2) }}, {{ hoverWorld.y.toFixed(2) }} m
      </span>
    </div>
  </div>
</template>
