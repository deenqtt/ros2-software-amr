<script setup lang="ts">
/**
 * The map as it is being surveyed.
 *
 * Rendered straight onto a canvas through ImageData. The old UI built the grid,
 * called `canvas.toDataURL()` and handed the result to an image layer — a full
 * PNG encode plus base64 of the whole grid, synchronously, on the main thread,
 * for every message. In navigation mode /map is latched and arrives once, so
 * that was survivable. While mapping it republishes continuously as the map
 * grows, and a real warehouse grid is a few megabytes.
 *
 * Pan and zoom are the part that actually makes a scan readable. The old UI
 * got them free from Leaflet, and most of its legibility came from being able
 * to zoom in — not from how it drew individual points. A fit-to-panel view of
 * a 10 m room puts a 720-point scan into 390 pixels, where no dot size helps.
 */
import { computed, onBeforeUnmount, onMounted, ref, shallowRef, watch } from 'vue'
import { Crosshair, Minus, Plus } from 'lucide-vue-next'
import type { LaserScan, OccupancyGrid, Pose } from '@/domain/types'

const props = defineProps<{
  grid: OccupancyGrid | null
  pose: Pose | null
  scan: LaserScan | null
  footprint?: { length: number; width: number } | null
  /** Laser mounting offset in the robot's frame, when TF has told us. */
  sensorOffset?: { x: number; y: number; yaw: number } | null
}>()

const gridCanvas = ref<HTMLCanvasElement | null>(null)
const overlayCanvas = ref<HTMLCanvasElement | null>(null)
const wrapper = ref<HTMLElement | null>(null)

/** Offscreen buffer at grid resolution; the visible canvas scales it. */
const buffer = shallowRef<HTMLCanvasElement | null>(null)
const viewport = ref({ width: 0, height: 0 })

/**
 * Occupancy colours.
 *
 * Unknown is deliberately opaque. At the light alpha it had, unmapped space
 * blended into free space — and the boundary between "surveyed" and "not yet"
 * is the single most useful thing on screen while mapping.
 */
const COLOUR_UNKNOWN = [128, 132, 140, 200] as const
const COLOUR_FREE = [246, 247, 248, 255] as const

const ZOOM_MIN = 0.4
const ZOOM_MAX = 24
const ZOOM_STEP = 1.25

/**
 * User pan and zoom, or null while the view is auto-fitting.
 *
 * Staying in fit mode until the operator intervenes means a growing map keeps
 * fitting itself; once they zoom, the view stops moving under them.
 */
const view = ref<{ scale: number; offsetX: number; offsetY: number } | null>(null)

const fit = computed(() => {
  const grid = props.grid
  const { width: vw, height: vh } = viewport.value
  if (!grid || vw === 0 || vh === 0) return null
  const { width, height } = grid.info
  const scale = Math.min(vw / width, vh / height)
  return { scale, offsetX: (vw - width * scale) / 2, offsetY: (vh - height * scale) / 2 }
})

const transform = computed(() => {
  const grid = props.grid
  const base = view.value ?? fit.value
  if (!grid || !base) return null
  const { resolution, origin, height } = grid.info
  return {
    ...base,
    resolution,
    originX: origin.position.x,
    originY: origin.position.y,
    gridHeight: height,
  }
})

/** Screen pixels per metre, the number every visual size is derived from. */
const metresToPx = computed(() => {
  const t = transform.value
  return t ? t.scale / t.resolution : 0
})

function paintGrid(grid: OccupancyGrid) {
  const { width, height } = grid.info
  if (width === 0 || height === 0) return

  let target = buffer.value
  if (!target || target.width !== width || target.height !== height) {
    target = document.createElement('canvas')
    target.width = width
    target.height = height
    buffer.value = target
  }

  const context = target.getContext('2d')
  if (!context) return

  const image = context.createImageData(width, height)
  const pixels = image.data
  const data = grid.data

  for (let i = 0; i < data.length; i += 1) {
    const value = data[i] ?? -1
    // An OccupancyGrid's first row is the bottom one; a canvas starts at the
    // top. Without the flip the map is mirrored and every later click lands in
    // the wrong place.
    const row = height - 1 - Math.floor(i / width)
    const index = (row * width + (i % width)) * 4

    if (value < 0) {
      pixels[index] = COLOUR_UNKNOWN[0]
      pixels[index + 1] = COLOUR_UNKNOWN[1]
      pixels[index + 2] = COLOUR_UNKNOWN[2]
      pixels[index + 3] = COLOUR_UNKNOWN[3]
    } else if (value === 0) {
      pixels[index] = COLOUR_FREE[0]
      pixels[index + 1] = COLOUR_FREE[1]
      pixels[index + 2] = COLOUR_FREE[2]
      pixels[index + 3] = COLOUR_FREE[3]
    } else {
      const shade = Math.round(255 * (1 - value / 100))
      pixels[index] = shade
      pixels[index + 1] = shade
      pixels[index + 2] = shade
      pixels[index + 3] = 255
    }
  }
  context.putImageData(image, 0, 0)
  blit()
}

/** Map metres to canvas pixels. */
function project(x: number, y: number): { x: number; y: number } | null {
  const t = transform.value
  if (!t) return null
  return {
    x: t.offsetX + ((x - t.originX) / t.resolution) * t.scale,
    // Rows count upward from the origin; canvas y counts downward.
    y: t.offsetY + (t.gridHeight - (y - t.originY) / t.resolution) * t.scale,
  }
}

/**
 * Wipe a canvas and hand back a context in CSS pixels.
 *
 * `clearRect` is interpreted through the current transform, so clearing
 * correctly depends on that transform being what you assumed — and if it ever
 * is not, the symptom is drawings that accumulate rather than an error.
 */
function resetContext(canvas: HTMLCanvasElement): CanvasRenderingContext2D | null {
  const context = canvas.getContext('2d')
  if (!context) return null
  const ratio = window.devicePixelRatio || 1
  context.setTransform(1, 0, 0, 1, 0, 0)
  context.clearRect(0, 0, canvas.width, canvas.height)
  context.setTransform(ratio, 0, 0, ratio, 0, 0)
  return context
}

function blit() {
  const canvas = gridCanvas.value
  const source = buffer.value
  const t = transform.value
  if (!canvas || !source || !t) return

  const context = resetContext(canvas)
  if (!context) return
  // Nearest-neighbour: an occupancy grid is data, and smoothing it invents
  // free space between an obstacle and the cell beside it.
  context.imageSmoothingEnabled = false
  context.drawImage(source, t.offsetX, t.offsetY, source.width * t.scale, source.height * t.scale)
}

/**
 * Draw the robot top-down: body, wheels, and a heading arrow.
 *
 * The arrow matters more than the shape. A rectangle tells an operator where
 * the robot is; only the arrow tells them which way it will move when they
 * push the stick forward.
 */
function drawRobot(
  context: CanvasRenderingContext2D,
  centre: { x: number; y: number },
  theta: number,
  lengthPx: number,
  widthPx: number,
) {
  const half = { l: lengthPx / 2, w: widthPx / 2 }
  const wheelLength = Math.max(lengthPx * 0.3, 3)
  const wheelWidth = Math.max(widthPx * 0.14, 2)
  const arrow = Math.max(lengthPx * 0.32, 6)

  context.save()
  context.translate(centre.x, centre.y)
  // ROS yaw is counter-clockwise; canvas y grows downward, so the sense flips.
  context.rotate(-theta)

  context.fillStyle = 'rgb(23, 32, 48)'
  for (const side of [-1, 1]) {
    for (const end of [-1, 1]) {
      context.fillRect(
        end * (half.l - wheelLength) - wheelLength / 2,
        side * half.w - wheelWidth / 2,
        wheelLength,
        wheelWidth,
      )
    }
  }

  context.fillStyle = 'rgba(0, 82, 255, 0.92)'
  context.strokeStyle = 'rgb(255, 255, 255)'
  context.lineWidth = Math.max(lengthPx * 0.04, 1.25)
  context.beginPath()
  context.rect(-half.l, -half.w, lengthPx, widthPx)
  context.fill()
  context.stroke()

  context.fillStyle = 'rgb(255, 255, 255)'
  context.beginPath()
  context.moveTo(half.l + arrow, 0)
  context.lineTo(half.l - 1, -Math.max(widthPx * 0.3, 3))
  context.lineTo(half.l - 1, Math.max(widthPx * 0.3, 3))
  context.closePath()
  context.fill()

  context.restore()
}

function paintOverlay() {
  const canvas = overlayCanvas.value
  if (!canvas) return

  // Clear first and unconditionally. An early return before this point leaves
  // the previous frame on screen, which is how a moving robot turns into a
  // trail of every place it has been.
  const context = resetContext(canvas)
  if (!context) return
  const t = transform.value
  if (!t) return

  const pose = props.pose
  const scan = props.scan
  const ppm = metresToPx.value

  if (pose && scan) {
    // Place the sensor in the map frame first. Skipping this draws every point
    // as if the laser were at the robot's centre, which shifts the whole scan
    // by the mounting distance.
    const mount = props.sensorOffset ?? { x: 0, y: 0, yaw: 0 }
    const cos = Math.cos(pose.theta)
    const sin = Math.sin(pose.theta)
    const sensorX = pose.x + mount.x * cos - mount.y * sin
    const sensorY = pose.y + mount.x * sin + mount.y * cos
    const sensorYaw = pose.theta + mount.yaw

    // A laser return is a measurement of a place, so the dot is sized in
    // metres and clamped: large enough to see when zoomed out, never so large
    // that adjacent returns merge into a band when zoomed in.
    const dot = Math.min(Math.max(ppm * 0.05, 1.8), 5)

    context.fillStyle = 'rgba(207, 32, 47, 0.9)'
    const { angle_min, angle_increment, range_min, range_max, ranges } = scan
    for (let i = 0; i < ranges.length; i += 1) {
      const range = ranges[i]
      if (range === undefined || !Number.isFinite(range)) continue
      if (range < range_min || range > range_max) continue
      const angle = angle_min + i * angle_increment + sensorYaw
      const point = project(sensorX + range * Math.cos(angle), sensorY + range * Math.sin(angle))
      if (!point) continue
      context.fillRect(point.x - dot / 2, point.y - dot / 2, dot, dot)
    }
  }

  if (!pose) return
  const centre = project(pose.x, pose.y)
  if (!centre) return

  // True scale, so the operator can judge whether the robot fits through a
  // gap — with a floor so it never becomes an unfindable speck. The old UI
  // drew it permanently at three times life size, which is visible but makes
  // that judgement impossible.
  const length = Math.max((props.footprint?.length ?? 0.6) * ppm, 26)
  const width = Math.max((props.footprint?.width ?? 0.45) * ppm, 18)
  drawRobot(context, centre, pose.theta, length, width)
}

// ── Pan and zoom ─────────────────────────────────────────────────────────────

function currentView() {
  return view.value ?? fit.value
}

/** Zoom about a point, so what is under the cursor stays under the cursor. */
function zoomAt(factor: number, anchorX: number, anchorY: number) {
  const base = currentView()
  if (!base) return
  const next = Math.min(Math.max(base.scale * factor, ZOOM_MIN), ZOOM_MAX)
  const ratio = next / base.scale
  view.value = {
    scale: next,
    offsetX: anchorX - (anchorX - base.offsetX) * ratio,
    offsetY: anchorY - (anchorY - base.offsetY) * ratio,
  }
  blit()
  paintOverlay()
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
  paintOverlay()
}

const panning = ref(false)
let panPointer: number | null = null
let panFrom = { x: 0, y: 0, offsetX: 0, offsetY: 0 }

function onPointerDown(event: PointerEvent) {
  const base = currentView()
  if (!base) return
  panning.value = true
  panPointer = event.pointerId
  wrapper.value?.setPointerCapture(event.pointerId)
  panFrom = { x: event.clientX, y: event.clientY, offsetX: base.offsetX, offsetY: base.offsetY }
  // Taking a copy pins the view: without it a map that keeps growing would
  // re-fit under the operator's hand mid-drag.
  view.value = { ...base }
}

function onPointerMove(event: PointerEvent) {
  if (!panning.value || event.pointerId !== panPointer) return
  const base = view.value
  if (!base) return
  view.value = {
    scale: base.scale,
    offsetX: panFrom.offsetX + (event.clientX - panFrom.x),
    offsetY: panFrom.offsetY + (event.clientY - panFrom.y),
  }
  blit()
  paintOverlay()
}

function onPointerUp(event: PointerEvent) {
  if (event.pointerId !== panPointer) return
  wrapper.value?.releasePointerCapture?.(event.pointerId)
  panning.value = false
  panPointer = null
}

// ── Sizing ───────────────────────────────────────────────────────────────────

function resize() {
  const element = wrapper.value
  if (!element) return
  const ratio = window.devicePixelRatio || 1
  const width = element.clientWidth
  const height = element.clientHeight
  viewport.value = { width, height }

  for (const canvas of [gridCanvas.value, overlayCanvas.value]) {
    if (!canvas) continue
    canvas.width = width * ratio
    canvas.height = height * ratio
    canvas.style.width = `${width}px`
    canvas.style.height = `${height}px`
  }
  blit()
  paintOverlay()
}

let observer: ResizeObserver | null = null

onMounted(() => {
  observer = new ResizeObserver(resize)
  if (wrapper.value) observer.observe(wrapper.value)
  resize()
  if (props.grid) paintGrid(props.grid)
})

onBeforeUnmount(() => observer?.disconnect())

watch(
  () => props.grid,
  (grid) => {
    if (grid) paintGrid(grid)
    else resetContext(gridCanvas.value!)
  },
)
watch([() => props.pose, () => props.scan], paintOverlay)

const zoomLabel = computed(() => (metresToPx.value ? `${Math.round(metresToPx.value)} px/m` : ''))
</script>

<template>
  <div
    ref="wrapper"
    class="relative h-full w-full touch-none overflow-hidden rounded-control bg-surface-soft"
    :class="panning ? 'cursor-grabbing' : 'cursor-grab'"
    @wheel="onWheel"
    @pointerdown="onPointerDown"
    @pointermove="onPointerMove"
    @pointerup="onPointerUp"
    @pointercancel="onPointerUp"
  >
    <canvas ref="gridCanvas" class="absolute inset-0" />
    <canvas ref="overlayCanvas" class="absolute inset-0" />

    <div
      v-if="!props.grid"
      class="absolute inset-0 flex flex-col items-center justify-center gap-xs text-center"
    >
      <p class="text-body-sm text-muted">Waiting for the first map update</p>
      <p class="text-caption text-muted-soft">
        SLAM publishes once it has seen enough to build a grid.
      </p>
    </div>

    <!-- The map can render without a pose, so name the piece that is missing
         rather than leaving an empty map to be puzzled over. -->
    <p
      v-else-if="!props.pose"
      class="absolute left-1/2 top-sm -translate-x-1/2 rounded-chip bg-status-warn/15 px-sm py-xxs text-caption text-status-warn"
    >
      No pose yet — waiting for SLAM to localise
    </p>

    <div v-if="props.grid" class="absolute right-sm top-sm flex flex-col gap-xxs">
      <button
        v-for="control in [
          { label: 'Zoom in', icon: Plus, run: () => zoomCentre(ZOOM_STEP) },
          { label: 'Zoom out', icon: Minus, run: () => zoomCentre(1 / ZOOM_STEP) },
          { label: 'Fit to view', icon: Crosshair, run: resetView },
        ]"
        :key="control.label"
        type="button"
        :title="control.label"
        :aria-label="control.label"
        class="flex h-7 w-7 items-center justify-center rounded-control border border-hairline bg-surface/90 text-muted backdrop-blur-[2px] transition-colors hover:border-primary hover:text-primary touch:h-11 touch:w-11"
        @pointerdown.stop
        @click="control.run()"
      >
        <component :is="control.icon" :size="14" />
      </button>
    </div>

    <div
      v-if="props.grid"
      class="pointer-events-none absolute bottom-sm left-sm flex flex-wrap items-center gap-sm rounded-chip bg-surface/85 px-sm py-xxs text-caption text-muted backdrop-blur-[2px]"
    >
      <!-- On a phone only the overlays: free, occupied and unknown read off the
           map itself, and the full legend wrapped over it. -->
      <span class="flex items-center gap-xxs">
        <span class="h-2 w-3 rounded-[1px] bg-[rgb(0,82,255)]" /> robot
      </span>
      <span class="flex items-center gap-xxs">
        <span class="h-2 w-2 rounded-[1px] bg-[rgb(207,32,47)]" /> laser
      </span>
      <span class="hidden items-center gap-xxs md:flex">
        <span class="h-2 w-2 rounded-[1px] border border-hairline bg-[#f6f7f8]" /> free
      </span>
      <span class="hidden items-center gap-xxs md:flex">
        <span class="h-2 w-2 rounded-[1px] bg-[#1a1a1a]" /> occupied
      </span>
      <span class="hidden items-center gap-xxs md:flex">
        <span class="h-2 w-2 rounded-[1px] bg-[rgb(128,132,140)]" /> unknown
      </span>
      <span v-if="zoomLabel" class="font-data">{{ zoomLabel }}</span>
    </div>
  </div>
</template>
