<template>
  <div class="space-y-4">

    <!-- ── Status ──────────────────────────────────────────────────── -->
    <div>
      <div class="text-[10px] font-semibold tracking-widest text-muted-foreground uppercase flex items-center gap-1.5 mb-2">
        <ScanLine :size="10" /> Manual Mapping
      </div>
      <div class="flex items-center justify-between rounded-md border border-border bg-card px-3 py-2">
        <span class="text-xs text-muted-foreground">SLAM</span>
        <Badge :variant="store.hasMap ? 'default' : 'outline'" class="text-[10px] font-mono uppercase">
          {{ store.hasMap ? 'ACTIVE' : 'WAITING' }}
        </Badge>
      </div>
    </div>

    <Separator />

    <!-- ── Speed Settings ──────────────────────────────────────────── -->
    <div>
      <div class="text-[10px] font-semibold tracking-widest text-muted-foreground uppercase flex items-center gap-1.5 mb-3">
        <Gauge :size="10" /> Speed Settings
      </div>

      <div class="space-y-4">
        <div>
          <div class="flex justify-between text-[10px] text-muted-foreground mb-2">
            <span>Linear (fwd/bwd)</span>
            <span class="font-data text-amr-data">{{ maxLinear.toFixed(2) }} m/s</span>
          </div>
          <Slider :model-value="[maxLinear]" @update:model-value="maxLinear = $event[0]"
            :min="0.05" :max="1.0" :step="0.05" />
        </div>
        <div>
          <div class="flex justify-between text-[10px] text-muted-foreground mb-2">
            <span>Angular (turn)</span>
            <span class="font-data text-amr-warning">{{ maxAngular.toFixed(2) }} r/s</span>
          </div>
          <Slider :model-value="[maxAngular]" @update:model-value="maxAngular = $event[0]"
            :min="0.1" :max="2.0" :step="0.1" />
        </div>

        <!-- Preset buttons -->
        <div class="flex gap-1.5">
          <button v-for="p in presets" :key="p.label"
            class="flex-1 text-xs py-1.5 rounded-md border transition-[background-color,color,border-color,transform] duration-150 active:scale-[0.96]"
            :class="activePreset === p.label
              ? 'bg-foreground text-background border-transparent'
              : 'border-border text-muted-foreground hover:text-foreground hover:bg-accent'"
            @click="applyPreset(p)">
            {{ p.label }}
          </button>
        </div>
      </div>
    </div>

    <Separator />

    <!-- ── Joystick Control ─────────────────────────────────────────── -->
    <div>
      <div class="text-[10px] font-semibold tracking-widest text-muted-foreground uppercase flex items-center gap-1.5 mb-3">
        <Gamepad2 :size="10" /> Control
      </div>

      <!-- Velocity readout -->
      <div class="flex gap-2 justify-center mb-3">
        <div class="flex items-center gap-1.5 rounded-md border border-border bg-card px-2.5 py-1.5">
          <span class="text-[10px] text-muted-foreground">LIN</span>
          <span class="w-14 text-right text-xs font-data font-bold"
            :class="Math.abs(cmdLinear) > 0.01 ? 'text-amr-data' : 'text-muted-foreground'">
            {{ cmdLinear >= 0 ? '+' : '' }}{{ cmdLinear.toFixed(2) }}
          </span>
          <span class="text-[10px] text-muted-foreground">m/s</span>
        </div>
        <div class="flex items-center gap-1.5 rounded-md border border-border bg-card px-2.5 py-1.5">
          <span class="text-[10px] text-muted-foreground">ANG</span>
          <span class="w-14 text-right text-xs font-data font-bold"
            :class="Math.abs(cmdAngular) > 0.01 ? 'text-amr-warning' : 'text-muted-foreground'">
            {{ cmdAngular >= 0 ? '+' : '' }}{{ cmdAngular.toFixed(2) }}
          </span>
          <span class="text-[10px] text-muted-foreground">r/s</span>
        </div>
      </div>

      <!-- Joystick pad -->
      <div class="flex justify-center mb-3">
        <div ref="padEl" class="joystick-pad touch-none"
          :style="{ width: PAD + 'px', height: PAD + 'px' }"
          @pointerdown.prevent="onPointerDown">
          <svg class="absolute inset-0 pointer-events-none" :width="PAD" :height="PAD">
            <circle :cx="PAD/2" :cy="PAD/2" :r="PAD/2 - 2"
              stroke="hsl(var(--border))" stroke-width="1" fill="none" stroke-dasharray="4 4"/>
            <line :x1="PAD/2" y1="4" :x2="PAD/2" :y2="PAD-4"
              stroke="hsl(var(--border))" stroke-width="1"/>
            <line x1="4" :y1="PAD/2" :x2="PAD-4" :y2="PAD/2"
              stroke="hsl(var(--border))" stroke-width="1"/>
          </svg>
          <div class="joystick-thumb flex items-center justify-center"
            :class="isDragging ? 'active' : ''"
            :style="{
              left: thumbX + 'px', top: thumbY + 'px',
              transition: isDragging ? 'none' : 'left 0.12s ease-out, top 0.12s ease-out',
            }">
            <div class="w-2 h-2 rounded-full bg-muted-foreground/60" />
          </div>
        </div>
      </div>

      <!-- D-pad -->
      <div class="grid grid-cols-3 gap-1.5 px-8">
        <div />
        <button class="py-2 rounded-md border border-border bg-card text-foreground hover:bg-accent flex items-center justify-center touch-none select-none transition-[background-color,transform] duration-100 active:scale-[0.93] active:bg-accent"
          @pointerdown.prevent="startDir(maxLinear, 0)" @pointerup.prevent="stopDir" @pointercancel.prevent="stopDir">
          <ChevronUp :size="16" />
        </button>
        <div />
        <button class="py-2 rounded-md border border-border bg-card text-foreground hover:bg-accent flex items-center justify-center touch-none select-none transition-[background-color,transform] duration-100 active:scale-[0.93] active:bg-accent"
          @pointerdown.prevent="startDir(0, maxAngular)" @pointerup.prevent="stopDir" @pointercancel.prevent="stopDir">
          <ChevronLeft :size="16" />
        </button>
        <button class="py-2 rounded-md border border-destructive/50 bg-destructive/10 text-destructive hover:bg-destructive/20 flex items-center justify-center select-none transition-[background-color,transform] duration-100 active:scale-[0.93]"
          @click="ros.stopRobot(); cmdLinear = 0; cmdAngular = 0">
          <Square :size="13" />
        </button>
        <button class="py-2 rounded-md border border-border bg-card text-foreground hover:bg-accent flex items-center justify-center touch-none select-none transition-[background-color,transform] duration-100 active:scale-[0.93] active:bg-accent"
          @pointerdown.prevent="startDir(0, -maxAngular)" @pointerup.prevent="stopDir" @pointercancel.prevent="stopDir">
          <ChevronRight :size="16" />
        </button>
        <div />
        <button class="py-2 rounded-md border border-border bg-card text-foreground hover:bg-accent flex items-center justify-center touch-none select-none transition-[background-color,transform] duration-100 active:scale-[0.93] active:bg-accent"
          @pointerdown.prevent="startDir(-maxLinear * 0.5, 0)" @pointerup.prevent="stopDir" @pointercancel.prevent="stopDir">
          <ChevronDown :size="16" />
        </button>
        <div />
      </div>
    </div>

    <Separator />

    <!-- ── Save Map ─────────────────────────────────────────────────── -->
    <div>
      <div class="text-[10px] font-semibold tracking-widest text-muted-foreground uppercase flex items-center gap-1.5 mb-2">
        <Save :size="10" /> Save Map
      </div>

      <div class="space-y-2">
        <div>
          <Label class="text-[10px] text-muted-foreground">Filename</Label>
          <Input v-model="mapFilename" class="mt-1 text-xs font-data h-8"
            placeholder="amr_map" @keyup.enter="doSaveMap" />
        </div>

        <Button class="w-full text-xs"
          :disabled="!store.rosConnected || !store.hasMap || saving"
          @click="doSaveMap">
          <Save v-if="!saving" :size="12" class="mr-1.5" />
          <Loader2 v-else :size="12" class="mr-1.5 animate-spin" />
          {{ saving ? 'Saving…' : 'Save Map to Robot' }}
        </Button>

        <p class="text-[10px] text-muted-foreground text-center">
          Saves to <code class="text-foreground">/maps/{{ mapFilename || 'amr_map' }}.yaml</code>
        </p>
      </div>
    </div>

  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted } from 'vue'
import { useRobotStore } from '@/stores/robot'
import { useROS }        from '@/composables/useROS'
import {
  ScanLine, Gauge, Gamepad2, Save, Square, Loader2,
  ChevronUp, ChevronDown, ChevronLeft, ChevronRight,
} from 'lucide-vue-next'
import { toast } from 'vue-sonner'

import { Button }    from '@/components/ui/button'
import { Badge }     from '@/components/ui/badge'
import { Slider }    from '@/components/ui/slider'
import { Input }     from '@/components/ui/input'
import { Label }     from '@/components/ui/label'
import { Separator } from '@/components/ui/separator'

const store = useRobotStore()
const ros   = useROS()

// ── Speed settings ────────────────────────────────────────────────────────────
const maxLinear    = ref(0.3)
const maxAngular   = ref(1.0)
const activePreset = ref('Normal')

const presets = [
  { label: 'Slow',   linear: 0.15, angular: 0.5 },
  { label: 'Normal', linear: 0.3,  angular: 1.0 },
  { label: 'Fast',   linear: 0.5,  angular: 1.5 },
]

function applyPreset(p) {
  activePreset.value = p.label; maxLinear.value = p.linear; maxAngular.value = p.angular
}

// ── Joystick ──────────────────────────────────────────────────────────────────
const PAD    = 160
const THUMB  = 36
const RADIUS = PAD / 2 - THUMB / 2 - 6

const padEl      = ref(null)
const isDragging = ref(false)
const thumbX     = ref(PAD / 2)
const thumbY     = ref(PAD / 2)
const cmdLinear  = ref(0)
const cmdAngular = ref(0)

let _publishInterval = null
let _capturedId = null

function _setVelocity(dx, dy) {
  const dist  = Math.sqrt(dx * dx + dy * dy)
  const ratio = Math.min(dist, RADIUS) / RADIUS
  const angle = Math.atan2(dy, dx)
  thumbX.value = PAD / 2 + Math.cos(angle) * ratio * RADIUS
  thumbY.value = PAD / 2 + Math.sin(angle) * ratio * RADIUS
  cmdLinear.value  = parseFloat(((-thumbY.value + PAD / 2) / RADIUS * maxLinear.value).toFixed(3))
  cmdAngular.value = parseFloat(((-thumbX.value + PAD / 2) / RADIUS * maxAngular.value).toFixed(3))
}

function _reset() {
  isDragging.value = false; _capturedId = null
  thumbX.value = PAD / 2; thumbY.value = PAD / 2
  cmdLinear.value = 0; cmdAngular.value = 0
  if (_publishInterval) { clearInterval(_publishInterval); _publishInterval = null }
  ros.stopRobot()
}

function onPointerDown(e) {
  if (!store.rosConnected) return
  isDragging.value = true; _capturedId = e.pointerId
  padEl.value?.setPointerCapture(e.pointerId)
  const rect = padEl.value.getBoundingClientRect()
  _setVelocity(e.clientX - rect.left - PAD / 2, e.clientY - rect.top - PAD / 2)
  _publishInterval = setInterval(() => ros.publishCmdVel(cmdLinear.value, cmdAngular.value), 80)
}

function _onWindowMove(e) {
  if (!isDragging.value || e.pointerId !== _capturedId) return
  const rect = padEl.value?.getBoundingClientRect()
  if (!rect) return
  _setVelocity(e.clientX - rect.left - PAD / 2, e.clientY - rect.top - PAD / 2)
}

function _onWindowUp(e) { if (e.pointerId === _capturedId) _reset() }

onMounted(() => {
  window.addEventListener('pointermove', _onWindowMove)
  window.addEventListener('pointerup',   _onWindowUp)
  window.addEventListener('pointercancel', _onWindowUp)
})

onUnmounted(() => {
  window.removeEventListener('pointermove', _onWindowMove)
  window.removeEventListener('pointerup',   _onWindowUp)
  window.removeEventListener('pointercancel', _onWindowUp)
  _reset()
})

// ── D-pad ─────────────────────────────────────────────────────────────────────
let _dirInterval = null

function startDir(linear, angular) {
  if (!store.rosConnected) return
  cmdLinear.value = linear; cmdAngular.value = angular
  ros.publishCmdVel(linear, angular)
  _dirInterval = setInterval(() => ros.publishCmdVel(linear, angular), 80)
}

function stopDir() {
  if (_dirInterval) { clearInterval(_dirInterval); _dirInterval = null }
  cmdLinear.value = 0; cmdAngular.value = 0; ros.stopRobot()
}

// ── Save map ──────────────────────────────────────────────────────────────────
const mapFilename = ref('amr_map')
const saving      = ref(false)

function doSaveMap() {
  if (!store.rosConnected || !store.hasMap) return
  saving.value = true
  const name = mapFilename.value.trim() || 'amr_map'
  toast.info(`Saving map as ${name}.yaml...`, { id: 'save-map' })
  
  ros.saveMap(name, {
    onSuccess: () => {
      saving.value = false
      toast.success(`Map saved successfully!`, {
        description: `Saved to /maps/${name}.yaml`,
        id: 'save-map'
      })
    },
    onError: (err) => {
      saving.value = false
      toast.error('Map save failed', {
        description: String(err),
        id: 'save-map'
      })
    },
  })
}
</script>
