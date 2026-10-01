<script setup lang="ts">
/**
 * One robot on its map, with everything that explains what it is doing.
 *
 * Each layer answers a different question, which is why they are separate and
 * separately switchable:
 *
 *   map        what the building looks like
 *   costmap    what the planner thinks of it
 *   zones      the rules that apply in a place
 *   scan       what the robot can see right now
 *   particles  whether it knows where it is
 *   plan       where it intends to go
 *   mission    the stops of the route it is running, and which are behind it
 *   robot      where it is, and which way it faces
 *
 * The two that are usually missing are the two that matter most when something
 * is wrong. Without `particles`, a lost robot looks exactly like a stopped one.
 * Without `plan`, a thinking robot looks exactly like a stuck one.
 *
 * Both tools use the same gesture — press, drag, release — because both set a
 * pose, and a pose is a place plus a direction. A plain click keeps the current
 * heading rather than silently meaning zero.
 */
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { Maximize, Minus, Plus } from 'lucide-vue-next'
import type {
  LaserScan,
  NavPath,
  OccupancyGrid,
  Pose,
  PoseCloud,
  Zone,
} from '@/domain/types'
import { ZONE_KIND_STYLE } from '@/features/zones/zoneKind'
import { Button } from '@/shared/ui/button'
import type { MissionOverlay, StepStatus } from '../missionMarkers'

export type MapTool = 'view' | 'initialPose' | 'goal'

const props = defineProps<{
  grid: OccupancyGrid | null
  costmap: OccupancyGrid | null
  plan: NavPath | null
  particles: PoseCloud | null
  scan: LaserScan | null
  pose: Pose | null
  /** Where the laser sits relative to the base, so returns land in the right place. */
  sensorOffset: { x: number; y: number; yaw: number } | null
  zones: Zone[]
  footprint: { length: number; width: number } | null
  /** The stops of the route being run, when there is one. */
  mission?: MissionOverlay | null
  layers: Record<string, boolean>
  tool: MapTool
}>()

const emit = defineEmits<{
  /** A pose the operator drew, in map metres. */
  pick: [pose: { x: number; y: number; theta: number }]
}>()

const COLOUR_UNKNOWN = [128, 132, 140, 200] as const
const COLOUR_FREE = [246, 247, 248, 255] as const

const ZOOM_MIN = 0.4
const ZOOM_MAX = 40
const ZOOM_STEP = 1.25
/** Below this drag distance the gesture is a click, and the heading is kept. */
const DRAG_THRESHOLD_PX = 12

const wrapper = ref<HTMLDivElement | null>(null)
const base = ref<HTMLCanvasElement | null>(null)
const overlay = ref<HTMLCanvasElement | null>(null)
const viewport = ref({ width: 0, height: 0 })

let mapBuffer: HTMLCanvasElement | null = null
let costBuffer: HTMLCanvasElement | null = null

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
  const current = view.value ?? fit.value
  if (!grid || !current) return null
  return {
    ...current,
    resolution: grid.info.resolution,
    originX: grid.info.origin.position.x,
    originY: grid.info.origin.position.y,
    gridHeight: grid.info.height,
  }
})

const metresToPx = computed(() => {
  const t = transform.value
  return t ? t.scale / t.resolution : 0
})

/** World metres to screen pixels. Rows count up from the origin; canvas y counts down. */
function project(x: number, y: number): { sx: number; sy: number } | null {
  const t = transform.value
  if (!t) return null
  return {
    sx: t.offsetX + ((x - t.originX) / t.resolution) * t.scale,
    sy: t.offsetY + (t.gridHeight - (y - t.originY) / t.resolution) * t.scale,
  }
}

function unproject(sx: number, sy: number): { x: number; y: number } | null {
  const t = transform.value
  if (!t || t.scale === 0) return null
  return {
    x: t.originX + ((sx - t.offsetX) / t.scale) * t.resolution,
    y: t.originY + (t.gridHeight - (sy - t.offsetY) / t.scale) * t.resolution,
  }
}

// ── Grid rendering ───────────────────────────────────────────────────────────

/**
 * Paint an occupancy grid into an offscreen canvas.
 *
 * Not through toDataURL: that is a full PNG encode of the whole grid on every
 * message, which a costmap updating several times a second cannot afford. The
 * buffer is drawn straight onto the visible canvas instead.
 */
function paintGrid(target: HTMLCanvasElement, grid: OccupancyGrid, costmapStyle: boolean) {
  const { width, height } = grid.info
  target.width = width
  target.height = height
  const context = target.getContext('2d')
  if (!context) return
  const image = context.createImageData(width, height)
  const pixels = image.data
  const data = grid.data

  for (let i = 0; i < data.length; i += 1) {
    const value = (data as number[])[i] ?? -1
    // An OccupancyGrid's first row is the bottom one; a canvas starts at the
    // top. Without the flip the map is mirrored and every click lands wrong.
    const row = height - 1 - Math.floor(i / width)
    const at = (row * width + (i % width)) * 4

    if (costmapStyle) {
      // Cost as heat, and transparent where it is free — the map underneath has
      // to stay readable or the overlay replaces it rather than annotating it.
      if (value <= 0) {
        pixels[at + 3] = 0
        continue
      }
      pixels[at] = 40 + Math.round(value * 2.1)
      pixels[at + 1] = Math.round(120 - value * 0.9)
      pixels[at + 2] = Math.round(245 - value * 1.4)
      pixels[at + 3] = 120
      continue
    }

    if (value < 0) {
      pixels[at] = COLOUR_UNKNOWN[0]
      pixels[at + 1] = COLOUR_UNKNOWN[1]
      pixels[at + 2] = COLOUR_UNKNOWN[2]
      pixels[at + 3] = COLOUR_UNKNOWN[3]
    } else if (value === 0) {
      pixels[at] = COLOUR_FREE[0]
      pixels[at + 1] = COLOUR_FREE[1]
      pixels[at + 2] = COLOUR_FREE[2]
      pixels[at + 3] = COLOUR_FREE[3]
    } else {
      const shade = Math.round(255 * (1 - value / 100))
      pixels[at] = shade
      pixels[at + 1] = shade
      pixels[at + 2] = shade
      pixels[at + 3] = 255
    }
  }
  context.putImageData(image, 0, 0)
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
  const target = base.value
  const t = transform.value
  if (!target || !t) return
  const context = resetContext(target)
  if (!context) return
  context.imageSmoothingEnabled = false

  if (mapBuffer && props.layers.map !== false) {
    context.drawImage(
      mapBuffer,
      t.offsetX,
      t.offsetY,
      mapBuffer.width * t.scale,
      mapBuffer.height * t.scale,
    )
  }
  if (costBuffer && props.layers.costmap) {
    context.drawImage(
      costBuffer,
      t.offsetX,
      t.offsetY,
      costBuffer.width * t.scale,
      costBuffer.height * t.scale,
    )
  }
  paintOverlay()
}

// ── Overlay ──────────────────────────────────────────────────────────────────

function drawZones(context: CanvasRenderingContext2D) {
  for (const zone of props.zones) {
    if (!zone.enabled || zone.polygon.length < 3) continue
    const colour = ZONE_KIND_STYLE[zone.kind].colour
    context.beginPath()
    zone.polygon.forEach((point, index) => {
      const screen = project(point[0], point[1])
      if (!screen) return
      if (index === 0) context.moveTo(screen.sx, screen.sy)
      else context.lineTo(screen.sx, screen.sy)
    })
    context.closePath()
    context.fillStyle = colour
    context.globalAlpha = 0.14
    context.fill()
    context.globalAlpha = 1
    context.strokeStyle = colour
    context.lineWidth = 1.5
    context.stroke()
  }
}

function drawParticles(context: CanvasRenderingContext2D) {
  const cloud = props.particles
  if (!cloud?.poses?.length) return
  // Small and translucent: a thousand of them, and the shape of the cloud is
  // the reading, not any single particle.
  context.fillStyle = 'rgba(122,61,245,0.55)'
  for (const particle of cloud.poses) {
    const screen = project(particle.position.x, particle.position.y)
    if (!screen) continue
    context.fillRect(screen.sx - 1, screen.sy - 1, 2, 2)
  }
}

function drawPlan(context: CanvasRenderingContext2D) {
  const path = props.plan
  if (!path?.poses?.length) return
  context.beginPath()
  path.poses.forEach((step, index) => {
    const screen = project(step.pose.position.x, step.pose.position.y)
    if (!screen) return
    if (index === 0) context.moveTo(screen.sx, screen.sy)
    else context.lineTo(screen.sx, screen.sy)
  })
  context.strokeStyle = '#0f9d58'
  context.lineWidth = 2.5
  context.setLineDash([7, 5])
  context.stroke()
  context.setLineDash([])
}

/**
 * Done, current and still to come must be told apart at a glance and from
 * across the room: filled green, filled blue with a halo, and hollow.
 */
const STEP_STYLE: Record<StepStatus, { fill: string; stroke: string; text: string }> = {
  done: { fill: '#0f9d58', stroke: '#ffffff', text: '#ffffff' },
  current: { fill: '#1a6ef5', stroke: '#ffffff', text: '#ffffff' },
  pending: { fill: '#ffffff', stroke: '#5b6472', text: '#2b3038' },
}
const STEP_RADIUS = 11

function drawMission(context: CanvasRenderingContext2D) {
  const mission = props.mission
  if (!mission?.markers.length) return

  // The order of the route, faint: it says "then here", it is not a path the
  // robot will follow. The planner's line is the one that means that.
  if (mission.route.length > 1) {
    context.beginPath()
    mission.route.forEach((point, index) => {
      const screen = project(point.x, point.y)
      if (!screen) return
      if (index === 0) context.moveTo(screen.sx, screen.sy)
      else context.lineTo(screen.sx, screen.sy)
    })
    context.strokeStyle = 'rgba(91,100,114,0.55)'
    context.lineWidth = 1.5
    context.setLineDash([3, 4])
    context.stroke()
    context.setLineDash([])
  }

  // Current last, so it is never covered by a neighbour.
  const ordered = [...mission.markers].sort(
    (a, b) => Number(a.status === 'current') - Number(b.status === 'current'),
  )
  for (const marker of ordered) {
    const screen = project(marker.x, marker.y)
    if (!screen) continue
    const style = STEP_STYLE[marker.status]

    // Arrival heading first, so the disc covers its root.
    context.strokeStyle = marker.status === 'pending' ? style.stroke : style.fill
    context.lineWidth = 2
    context.beginPath()
    context.moveTo(screen.sx, screen.sy)
    context.lineTo(
      screen.sx + Math.cos(marker.yaw) * (STEP_RADIUS + 10),
      screen.sy - Math.sin(marker.yaw) * (STEP_RADIUS + 10),
    )
    context.stroke()

    if (marker.status === 'current') {
      context.beginPath()
      context.arc(screen.sx, screen.sy, STEP_RADIUS + 5, 0, Math.PI * 2)
      context.fillStyle = 'rgba(26,110,245,0.22)'
      context.fill()
    }

    context.beginPath()
    context.arc(screen.sx, screen.sy, STEP_RADIUS, 0, Math.PI * 2)
    context.fillStyle = style.fill
    context.fill()
    context.lineWidth = 2
    context.strokeStyle = style.stroke
    context.stroke()

    const number = marker.ordinals.join('·')
    context.font = `600 ${number.length > 2 ? 9 : 11}px Inter, system-ui, sans-serif`
    context.textAlign = 'center'
    context.textBaseline = 'middle'
    context.fillStyle = style.text
    context.fillText(number, screen.sx, screen.sy + 0.5)

    context.font = '11px Inter, system-ui, sans-serif'
    context.textBaseline = 'top'
    const width = context.measureText(marker.name).width
    const top = screen.sy + STEP_RADIUS + 4
    context.fillStyle = 'rgba(255,255,255,0.88)'
    context.fillRect(screen.sx - width / 2 - 3, top - 1, width + 6, 14)
    context.fillStyle = '#0a0b0d'
    context.fillText(marker.name, screen.sx, top)
  }
}

function drawScan(context: CanvasRenderingContext2D) {
  const scan = props.scan
  const pose = props.pose
  if (!scan || !pose) return
  const offset = props.sensorOffset ?? { x: 0, y: 0, yaw: 0 }
  const sensorX = pose.x + offset.x * Math.cos(pose.theta) - offset.y * Math.sin(pose.theta)
  const sensorY = pose.y + offset.x * Math.sin(pose.theta) + offset.y * Math.cos(pose.theta)
  const heading = pose.theta + offset.yaw

  // Sized in metres and clamped: large enough to see zoomed out, never so large
  // that adjacent returns merge into a band zoomed in.
  const dot = Math.min(Math.max(metresToPx.value * 0.05, 1.8), 5)
  context.fillStyle = 'rgba(229,72,77,0.85)'
  for (let i = 0; i < scan.ranges.length; i += 1) {
    const range = scan.ranges[i] as number
    if (!Number.isFinite(range) || range < scan.range_min || range > scan.range_max) continue
    const angle = heading + scan.angle_min + i * scan.angle_increment
    const screen = project(sensorX + range * Math.cos(angle), sensorY + range * Math.sin(angle))
    if (!screen) continue
    context.beginPath()
    context.arc(screen.sx, screen.sy, dot / 2, 0, Math.PI * 2)
    context.fill()
  }
}

function drawRobot(context: CanvasRenderingContext2D) {
  const pose = props.pose
  const screen = pose ? project(pose.x, pose.y) : null
  if (!pose || !screen) return

  const ppm = metresToPx.value
  // True scale, so an operator can judge whether the robot fits through a gap.
  const length = Math.max((props.footprint?.length ?? 0.6) * ppm, 20)
  const width = Math.max((props.footprint?.width ?? 0.45) * ppm, 14)

  context.save()
  context.translate(screen.sx, screen.sy)
  context.rotate(-pose.theta)
  context.fillStyle = 'rgba(20,110,245,0.28)'
  context.strokeStyle = '#1a6ef5'
  context.lineWidth = 2
  context.beginPath()
  context.rect(-length / 2, -width / 2, length, width)
  context.fill()
  context.stroke()
  context.beginPath()
  context.moveTo(0, 0)
  context.lineTo(length / 2 + 8, 0)
  context.stroke()
  context.restore()
}

function drawDraft(context: CanvasRenderingContext2D) {
  const draft = dragPose.value
  if (!draft) return
  const screen = project(draft.x, draft.y)
  if (!screen) return
  const colour = props.tool === 'goal' ? '#0f9d58' : '#f0a020'
  context.strokeStyle = colour
  context.fillStyle = colour
  context.lineWidth = 2
  context.beginPath()
  context.arc(screen.sx, screen.sy, 7, 0, Math.PI * 2)
  context.stroke()
  context.beginPath()
  context.moveTo(screen.sx, screen.sy)
  context.lineTo(
    screen.sx + Math.cos(draft.theta) * 30,
    screen.sy - Math.sin(draft.theta) * 30,
  )
  context.stroke()
}

function paintOverlay() {
  const target = overlay.value
  if (!target || !props.grid) return
  const context = resetContext(target)
  if (!context) return

  if (props.layers.zones !== false) drawZones(context)
  if (props.layers.particles) drawParticles(context)
  if (props.layers.plan !== false) drawPlan(context)
  if (props.layers.mission !== false) drawMission(context)
  if (props.layers.scan !== false) drawScan(context)
  if (props.layers.robot !== false) drawRobot(context)
  drawDraft(context)
}

// ── Pointer ──────────────────────────────────────────────────────────────────

const panning = ref(false)
const dragPose = ref<{ x: number; y: number; theta: number } | null>(null)
let activePointer: number | null = null
let panFrom = { x: 0, y: 0, offsetX: 0, offsetY: 0, scale: 1 }
let pickFrom: { sx: number; sy: number } | null = null

function pointerAt(event: PointerEvent): { sx: number; sy: number } | null {
  const rect = wrapper.value?.getBoundingClientRect()
  if (!rect) return null
  return { sx: event.clientX - rect.left, sy: event.clientY - rect.top }
}

function startPan(event: PointerEvent) {
  const current = transform.value
  if (!current) return
  panning.value = true
  activePointer = event.pointerId
  panFrom = {
    x: event.clientX,
    y: event.clientY,
    offsetX: current.offsetX,
    offsetY: current.offsetY,
    scale: current.scale,
  }
  view.value = { scale: current.scale, offsetX: current.offsetX, offsetY: current.offsetY }
  wrapper.value?.setPointerCapture(event.pointerId)
}

function onPointerDown(event: PointerEvent) {
  if (event.button !== 0 || props.tool === 'view') {
    event.preventDefault()
    startPan(event)
    return
  }
  const at = pointerAt(event)
  const world = at ? unproject(at.sx, at.sy) : null
  if (!at || !world) return
  activePointer = event.pointerId
  pickFrom = at
  dragPose.value = { ...world, theta: props.pose?.theta ?? 0 }
  wrapper.value?.setPointerCapture(event.pointerId)
  paintOverlay()
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

  if (!pickFrom || event.pointerId !== activePointer) return
  const at = pointerAt(event)
  const start = unproject(pickFrom.sx, pickFrom.sy)
  if (!at || !start) return
  const travelled = Math.hypot(at.sx - pickFrom.sx, at.sy - pickFrom.sy)
  // Below the threshold this is a click, and a click keeps the robot's current
  // heading — silently meaning "face east" would be a surprise.
  const theta =
    travelled < DRAG_THRESHOLD_PX
      ? (props.pose?.theta ?? 0)
      : Math.atan2(-(at.sy - pickFrom.sy), at.sx - pickFrom.sx)
  dragPose.value = { ...start, theta }
  paintOverlay()
}

function finishPointer(event: PointerEvent) {
  if (event.pointerId !== activePointer) return
  if (pickFrom && dragPose.value) emit('pick', dragPose.value)

  pickFrom = null
  dragPose.value = null
  panning.value = false
  activePointer = null
  wrapper.value?.releasePointerCapture?.(event.pointerId)
  paintOverlay()
}

// ── Zoom ─────────────────────────────────────────────────────────────────────

function zoomAt(factor: number, anchorX: number, anchorY: number) {
  const current = transform.value
  if (!current) return
  const next = Math.min(Math.max(current.scale * factor, ZOOM_MIN), ZOOM_MAX)
  const ratio = next / current.scale
  view.value = {
    scale: next,
    offsetX: anchorX - (anchorX - current.offsetX) * ratio,
    offsetY: anchorY - (anchorY - current.offsetY) * ratio,
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
  if (!host || !base.value || !overlay.value) return
  const ratio = window.devicePixelRatio || 1
  const { width, height } = host.getBoundingClientRect()
  viewport.value = { width, height }
  for (const surface of [base.value, overlay.value]) {
    surface.width = Math.max(1, Math.round(width * ratio))
    surface.height = Math.max(1, Math.round(height * ratio))
    surface.style.width = `${width}px`
    surface.style.height = `${height}px`
  }
  blit()
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
  (grid) => {
    if (!grid) return
    mapBuffer = mapBuffer ?? document.createElement('canvas')
    paintGrid(mapBuffer, grid, false)
    blit()
  },
  { immediate: true },
)

watch(
  () => props.costmap,
  (grid) => {
    if (!grid) return
    costBuffer = costBuffer ?? document.createElement('canvas')
    paintGrid(costBuffer, grid, true)
    blit()
  },
)

watch(() => props.layers, () => blit(), { deep: true })

watch(
  [
    () => props.pose,
    () => props.scan,
    () => props.plan,
    () => props.particles,
    () => props.zones,
    () => props.mission,
    () => props.tool,
  ],
  () => paintOverlay(),
  { deep: true },
)

defineExpose({ resetView })
</script>

<template>
  <div
    ref="wrapper"
    class="relative h-full w-full select-none overflow-hidden bg-[#e9ebee]"
    :class="props.tool === 'view' ? 'cursor-grab' : 'cursor-crosshair'"
    @pointerdown="onPointerDown"
    @pointermove="onPointerMove"
    @pointerup="finishPointer"
    @pointercancel="finishPointer"
    @wheel="onWheel"
    @contextmenu.prevent
  >
    <canvas ref="base" class="absolute inset-0" />
    <canvas ref="overlay" class="pointer-events-none absolute inset-0" />

    <div
      v-if="props.tool !== 'view'"
      class="pointer-events-none absolute left-1/2 top-sm -translate-x-1/2 rounded-chip bg-primary px-sm py-xxs text-caption text-on-primary shadow-soft"
    >
      {{
        props.tool === 'initialPose'
          ? 'Drag to place the robot and its heading'
          : 'Drag to set the goal and the heading to arrive on'
      }}
    </div>

    <div v-if="!props.grid" class="absolute inset-0 flex items-center justify-center">
      <p class="rounded-control bg-surface/85 px-sm py-xxs text-caption text-muted">
        Waiting for <span class="font-ident">/map</span>
      </p>
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
      <span v-if="props.pose" class="font-data text-ink">
        {{ props.pose.x.toFixed(2) }}, {{ props.pose.y.toFixed(2) }} m
      </span>
      <span v-else class="text-status-warn">no pose — is AMCL localised?</span>
    </div>
  </div>
</template>
