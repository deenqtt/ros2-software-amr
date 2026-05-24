<template>
  <div class="space-y-4">

    <!-- ── Destination Points ──────────────────────────────────────── -->
    <div>
      <div class="flex items-center justify-between mb-2">
        <div class="text-[10px] font-semibold tracking-widest text-muted-foreground uppercase flex items-center gap-1.5">
          <MapPin :size="10" class="text-amr-ok" /> Destinations
          <span class="font-data">({{ store.destinations.length }})</span>
        </div>
        <div class="flex gap-1">
          <Button variant="ghost" size="sm" class="h-6 px-2 text-xs" @click="fetchDestinations" title="Refresh">
            <RefreshCw :size="11" />
          </Button>
          <Button variant="ghost" size="sm" class="h-6 px-2 text-xs" @click="showDestList = true">List</Button>
          <Button size="sm" class="h-6 px-2 text-xs"
            :variant="isAdding ? 'destructive' : 'outline'"
            @click="toggleAddMode">
            {{ isAdding ? '✕ Cancel' : '+ Add' }}
          </Button>
        </div>
      </div>

      <!-- Add mode hint -->
      <div v-if="isAdding" class="rounded-md border border-amr-ok/30 bg-amr-ok/5 p-2 text-xs text-amr-ok flex items-center gap-2 mb-2">
        <MapPin :size="11" />
        Click on map to add destination point
        <div class="flex gap-1 ml-auto">
          <button v-for="opt in typeOptions" :key="opt.value"
            class="px-1.5 py-0.5 rounded text-[10px] border transition-colors"
            :class="pendingType === opt.value
              ? 'bg-foreground text-background border-transparent'
              : 'border-border text-muted-foreground hover:text-foreground'"
            @click="pendingType = opt.value">
            {{ opt.label }}
          </button>
        </div>
      </div>
    </div>

    <Separator />

    <!-- ── Waypoints ───────────────────────────────────────────────── -->
    <div>
      <div class="flex items-center justify-between mb-2">
        <div class="text-[10px] font-semibold tracking-widest text-muted-foreground uppercase flex items-center gap-1.5">
          <Route :size="10" /> Waypoints
          <span class="font-data" :class="store.waypoints.length >= 5 ? 'text-amr-danger' : ''">
            {{ store.waypoints.length }}/5
          </span>
        </div>
        <div class="flex gap-1">
          <Button variant="ghost" size="sm" class="h-6 px-2 text-xs" @click="showSave = true">Save</Button>
          <Button variant="ghost" size="sm" class="h-6 px-2 text-xs" @click="openLoad">Load</Button>
          <Button variant="destructive" size="sm" class="h-6 px-2 text-xs" @click="store.clearWaypoints">Clear</Button>
        </div>
      </div>

      <!-- Mission progress bar -->
      <div v-if="store.missionRunning" class="mb-2 space-y-1">
        <div class="flex justify-between text-[10px] text-muted-foreground">
          <span>Waypoint {{ store.currentWaypointIndex + 1 }} / {{ store.waypoints.length }}</span>
          <span class="font-data">{{ missionProgress }}%</span>
        </div>
        <Progress :model-value="missionProgress" class="h-1.5" />
      </div>

      <!-- Waypoint list -->
      <div class="space-y-1 max-h-40 overflow-y-auto mb-2">
        <div v-if="store.waypoints.length === 0"
          class="text-center text-muted-foreground text-xs py-4 border border-dashed border-border rounded-md">
          No waypoints. Add destinations first, then add them as waypoints below.
        </div>

        <div v-for="(wp, i) in store.waypoints" :key="wp.id"
          class="group rounded-md border border-border bg-card p-2 space-y-1.5"
          :class="{ 'border-amr-info/60 bg-amr-info/5': store.currentWaypointIndex === i && store.missionRunning }">
          <div class="flex items-center gap-2">
            <span class="w-4 text-[10px] text-muted-foreground text-center shrink-0 font-data">{{ i + 1 }}</span>
            <input :value="wp.name"
              class="flex-1 bg-transparent text-xs text-foreground outline-none min-w-0 border-b border-transparent focus:border-border"
              @change="store.updateWaypoint(wp.id, { name: $event.target.value })" />
            <span class="text-[10px] font-data text-muted-foreground shrink-0">
              ({{ wp.x.toFixed(1) }}, {{ wp.y.toFixed(1) }})
            </span>
            <div class="flex gap-0.5 opacity-0 group-hover:opacity-100 transition-opacity">
              <button class="p-0.5 text-muted-foreground hover:text-foreground" :disabled="i === 0" @click="moveUp(i)">
                <ChevronUp :size="12" />
              </button>
              <button class="p-0.5 text-muted-foreground hover:text-foreground" :disabled="i === store.waypoints.length - 1" @click="moveDown(i)">
                <ChevronDown :size="12" />
              </button>
              <button class="p-0.5 text-amr-danger hover:text-amr-danger/80" @click="store.removeWaypoint(wp.id)">
                <X :size="12" />
              </button>
            </div>
          </div>
          <div class="flex gap-2 pl-6">
            <div class="flex items-center gap-1">
              <span class="text-[10px] text-muted-foreground">Task</span>
              <select :value="wp.task"
                class="bg-secondary border border-border rounded px-1 py-0.5 text-[10px] text-foreground"
                @change="store.updateWaypoint(wp.id, { task: $event.target.value })">
                <option value="NoAction">No Action</option>
                <option value="Pick">Pick</option>
                <option value="Drop">Drop</option>
                <option value="DropPick">Pick &amp; Drop</option>
              </select>
            </div>
            <div class="flex items-center gap-1">
              <span class="text-[10px] text-muted-foreground">Mode</span>
              <select :value="wp.continueMode"
                class="bg-secondary border border-border rounded px-1 py-0.5 text-[10px] text-foreground"
                @change="store.updateWaypoint(wp.id, { continueMode: $event.target.value })">
                <option value="Auto">Auto</option>
                <option value="Manual">Manual</option>
              </select>
            </div>
          </div>
        </div>
      </div>

      <p v-if="store.waypoints.length >= 5" class="text-[10px] text-amr-danger mt-1">
        Maximum 5 waypoints reached.
      </p>
    </div>

    <Separator />

    <!-- ── Mission Options ─────────────────────────────────────────── -->
    <div class="flex items-center gap-4 flex-wrap">
      <div class="flex items-center gap-2">
        <Switch :model-value="store.missionLoop" @update:model-value="store.missionLoop = $event" id="loop-sw" />
        <Label for="loop-sw" class="text-xs cursor-pointer">Loop</Label>
      </div>
      <div v-if="store.missionLoop" class="flex items-center gap-1.5">
        <Label class="text-xs text-muted-foreground">Count</Label>
        <Input v-model.number="store.missionLoopCount" type="number" min="0" step="1"
          class="w-14 h-6 text-xs font-data px-2" placeholder="0=∞" />
      </div>
      <div class="flex items-center gap-1.5">
        <Label class="text-xs text-muted-foreground">Timeout</Label>
        <Input v-model.number="store.missionTimeoutSec" type="number" min="10" step="10"
          class="w-14 h-6 text-xs font-data px-2" />
        <span class="text-xs text-muted-foreground">s</span>
      </div>
    </div>

    <!-- ── Mission Controls ─────────────────────────────────────────── -->
    <div class="flex gap-2">
      <Button class="flex-1 text-xs bg-amr-ok text-black hover:bg-amr-ok/90"
        :disabled="!store.rosConnected || store.waypoints.length === 0 || store.missionRunning"
        @click="startMission">
        <Play :size="12" class="mr-1" /> Start
      </Button>
      <Button variant="outline" size="sm" class="text-xs px-3"
        :disabled="!store.missionRunning" @click="pauseMission">
        <Pause :size="12" />
      </Button>
      <Button variant="destructive" size="sm" class="text-xs px-3"
        :disabled="!store.rosConnected" @click="stopMission">
        <Square :size="12" />
      </Button>
    </div>

    <!-- ── Manual Confirm Button (visible saat WAITING_CONFIRM) ──────── -->
    <div v-if="store.navStatus === 'waiting_confirm'"
      class="rounded-md border border-yellow-500/40 bg-yellow-500/10 p-2 flex items-center gap-2">
      <span class="text-xs text-yellow-400 flex-1">Waiting operator confirmation...</span>
      <Button size="sm" class="h-6 px-3 text-xs bg-yellow-500 text-black hover:bg-yellow-400"
        @click="doConfirm">
        Confirm
      </Button>
    </div>

    <!-- ── Destination List Dialog ─────────────────────────────────── -->
    <Dialog :open="showDestList" @update:open="showDestList = $event">
      <DialogContent class="max-w-sm max-h-[80vh] flex flex-col">
        <DialogHeader>
          <DialogTitle class="flex items-center gap-2 text-sm">
            <MapPin :size="14" class="text-amr-ok" /> Destination Points
          </DialogTitle>
        </DialogHeader>
        <ScrollArea class="flex-1 min-h-0 pr-1">
          <div v-if="store.destinations.length === 0"
            class="text-center text-muted-foreground text-xs py-6">
            No destination points yet.
          </div>
          <div v-else class="space-y-2 p-1">
            <div v-for="(dest, i) in store.destinations" :key="dest.id"
              class="rounded-md border border-border bg-card p-2.5 space-y-2">
              <div class="flex items-center gap-2">
                <span class="w-5 h-5 rounded-full bg-amr-ok/20 text-amr-ok flex items-center justify-center text-[10px] font-bold shrink-0">
                  {{ i + 1 }}
                </span>
                <input :value="dest.name"
                  class="flex-1 bg-transparent text-xs text-foreground outline-none min-w-0 border-b border-transparent focus:border-border"
                  @change="renameDestination(dest, $event.target.value)"
                  @keyup.enter="renameDestination(dest, $event.target.value)" />
                <button class="p-1 text-muted-foreground hover:text-amr-danger transition-colors"
                  @click="deleteDestination(dest)">
                  <Trash2 :size="12" />
                </button>
              </div>
              <div class="flex items-center gap-2 pl-7">
                <span class="text-[10px] font-data text-muted-foreground">
                  x={{ dest.x.toFixed(2) }}, y={{ dest.y.toFixed(2) }}
                </span>
                <div class="flex items-center gap-1 ml-auto">
                  <span class="text-[10px] text-muted-foreground">yaw</span>
                  <input type="number" step="0.1" :value="(dest.yaw ?? 0).toFixed(2)"
                    class="w-16 bg-secondary border border-border rounded px-1 py-0.5 text-[10px] font-data text-foreground outline-none"
                    @change="updateDestYaw(dest, Number($event.target.value))" />
                </div>
                <select :value="dest.station_type"
                  class="text-[10px] rounded px-1 py-0.5 bg-secondary border border-border text-foreground"
                  @change="changeDestType(dest, Number($event.target.value))">
                  <option v-for="opt in typeOptions" :key="opt.value" :value="opt.value">
                    {{ opt.label }}
                  </option>
                </select>
                <Button size="sm" variant="outline" class="h-5 px-1.5 text-[10px]"
                  :disabled="store.waypoints.length >= 5"
                  @click="quickAddToWaypoint(dest, i); showDestList = false">
                  + WP
                </Button>
              </div>
            </div>
          </div>
        </ScrollArea>
        <DialogFooter>
          <Button variant="outline" size="sm" @click="showDestList = false">Close</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>

    <!-- ── Save Mission Dialog ─────────────────────────────────────── -->
    <Dialog :open="showSave" @update:open="showSave = $event">
      <DialogContent class="max-w-xs">
        <DialogHeader>
          <DialogTitle class="text-sm">Save Mission</DialogTitle>
        </DialogHeader>
        <Input v-model="saveName" placeholder="Mission name" class="text-sm"
          @keyup.enter="doSave" />
        <DialogFooter class="gap-2">
          <Button variant="outline" size="sm" @click="showSave = false">Cancel</Button>
          <Button size="sm" :disabled="saving" @click="doSave">
            {{ saving ? 'Saving…' : 'Save' }}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>

    <!-- ── Load Mission Dialog ─────────────────────────────────────── -->
    <Dialog :open="showLoad" @update:open="showLoad = $event">
      <DialogContent class="max-w-sm max-h-[70vh] flex flex-col">
        <DialogHeader>
          <DialogTitle class="text-sm">Load Mission</DialogTitle>
        </DialogHeader>
        <ScrollArea class="flex-1 min-h-0">
          <div v-if="loadingMissions" class="text-center text-muted-foreground text-xs py-6">Loading…</div>
          <div v-else-if="loadError" class="text-xs text-amr-danger p-2">{{ loadError }}</div>
          <div v-else-if="savedMissions.length === 0" class="text-center text-muted-foreground text-xs py-6">
            No saved missions.
          </div>
          <div v-else class="space-y-1.5 p-1">
            <div v-for="m in savedMissions" :key="m.id"
              class="flex items-center gap-2 rounded-md border border-border bg-card px-3 py-2">
              <span class="flex-1 text-xs text-foreground">{{ m.name }}</span>
              <span class="text-[10px] text-muted-foreground font-data">{{ m.waypoints.length }}pts</span>
              <Button size="sm" class="h-6 px-2 text-[10px]" @click="doLoad(m)">Load</Button>
              <Button size="sm" variant="destructive" class="h-6 px-2 text-[10px]" @click="doDeleteMission(m.id)">✕</Button>
            </div>
          </div>
        </ScrollArea>
        <DialogFooter>
          <Button variant="outline" size="sm" @click="showLoad = false">Close</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>

  </div>
</template>

<script setup>
import { ref, computed, watch, onMounted } from 'vue'
import { useRobotStore } from '@/stores/robot'
import { useROS }        from '@/composables/useROS'
import { useAPI }        from '@/composables/useAPI'
import { useMapMode }    from '@/composables/useMapMode'
import { MapPin, Route, ChevronUp, ChevronDown, X, Trash2, Play, Pause, Square, RefreshCw } from 'lucide-vue-next'
import { toast } from 'vue-sonner'

import { Button }     from '@/components/ui/button'
import { Progress }   from '@/components/ui/progress'
import { Separator }  from '@/components/ui/separator'
import { Switch }     from '@/components/ui/switch'
import { Input }      from '@/components/ui/input'
import { Label }      from '@/components/ui/label'
import { ScrollArea } from '@/components/ui/scroll-area'
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from '@/components/ui/dialog'

const store = useRobotStore()
const ros   = useROS()
const api   = useAPI()
const { setMode, mapMode } = useMapMode()

// ── Destination Points ────────────────────────────────────────────────────────
const isAdding    = ref(false)
const showDestList = ref(false)
const pendingType  = ref(2)

const typeOptions = [
  { value: 0, label: 'Pick' },
  { value: 1, label: 'Drop' },
  { value: 2, label: 'P&D' },
]

function typeLabel(t) { return typeOptions.find(o => o.value === t)?.label ?? 'P&D' }

onMounted(fetchDestinations)
watch(() => store.activeMapId, fetchDestinations)

async function fetchDestinations() {
  try {
    const url = store.activeMapId ? `/destinations?map_id=${store.activeMapId}` : '/destinations'
    store.setDestinations(await api.get(url))
  } catch (err) {
    console.error('[Destinations] fetch failed:', err)
    toast.error('Gagal memuat destinations: ' + err.message)
  }
}

function toggleAddMode() {
  isAdding.value = !isAdding.value
  setMode(isAdding.value ? 'destination' : 'navigate')
}

watch(mapMode, m => { if (m !== 'destination') isAdding.value = false })

async function onMapClick(x, y, yaw = 0) {
  const name = `Point ${store.destinations.length + 1}`
  try {
    const saved = await api.post('/destinations', {
      map_id: store.activeMapId ?? null, name, x, y, yaw, station_type: pendingType.value,
    })
    store.addDestination(saved)
    ros.configStation({ station_id: saved.name, station_type: saved.station_type, action: 1, x: saved.x, y: saved.y, yaw: saved.yaw ?? 0 })
    toast.success(`${name} (${typeLabel(saved.station_type)}) added`)
  } catch (err) {
    toast.error('Failed to save destination: ' + err.message)
  }
}

async function changeDestType(dest, newType) {
  if (newType === dest.station_type) return
  try {
    await api.put(`/destinations/${dest.id}`, { name: dest.name, x: dest.x, y: dest.y, station_type: newType })
    dest.station_type = newType
    ros.configStation({ station_id: dest.name, station_type: newType, action: 1, x: dest.x, y: dest.y, yaw: dest.yaw ?? 0 })
  } catch (err) {
    toast.error('Gagal ubah type: ' + err.message)
  }
}

async function renameDestination(dest, newName) {
  if (!newName.trim() || newName.trim() === dest.name) return
  try {
    await api.put(`/destinations/${dest.id}`, { name: newName.trim(), x: dest.x, y: dest.y, yaw: dest.yaw ?? 0, station_type: dest.station_type ?? 2 })
    dest.name = newName.trim()
    ros.configStation({ station_id: dest.name, station_type: dest.station_type ?? 2, action: 1, x: dest.x, y: dest.y, yaw: dest.yaw ?? 0 })
  } catch (err) { toast.error('Rename failed: ' + err.message) }
}

async function updateDestYaw(dest, newYaw) {
  if (newYaw === dest.yaw) return
  try {
    await api.put(`/destinations/${dest.id}`, { name: dest.name, x: dest.x, y: dest.y, yaw: newYaw, station_type: dest.station_type ?? 2 })
    dest.yaw = newYaw
    ros.configStation({ station_id: dest.name, station_type: dest.station_type ?? 2, action: 1, x: dest.x, y: dest.y, yaw: newYaw })
  } catch (err) { toast.error('Update yaw failed: ' + err.message) }
}

async function deleteDestination(dest) {
  try {
    ros.configStation({ station_id: dest.name, station_type: dest.station_type ?? 2, action: 0, x: dest.x, y: dest.y, yaw: dest.yaw ?? 0 })
    await api.del(`/destinations/${dest.id}`)
    store.removeDestination(dest.id)
  } catch (err) { toast.error('Delete failed: ' + err.message) }
}

// ── Waypoints ─────────────────────────────────────────────────────────────────
function _taskFromType(t) { return t === 1 ? 'Drop' : 'Pick' }

function quickAddToWaypoint(dest, i) {
  const added = store.addWaypoint(dest.x, dest.y, dest.yaw ?? 0, `Point ${i + 1} — ${dest.name}`, _taskFromType(dest.station_type ?? 2), 'Auto', i + 1, dest.name)
  if (!added) toast.error('Maximum 5 waypoints reached')
}

function moveUp(i) { const w = [...store.waypoints]; [w[i-1],w[i]]=[w[i],w[i-1]]; store.reorderWaypoints(w) }
function moveDown(i) { const w = [...store.waypoints]; [w[i],w[i+1]]=[w[i+1],w[i]]; store.reorderWaypoints(w) }

// ── Mission progress ──────────────────────────────────────────────────────────
const missionProgress = computed(() => {
  if (!store.waypoints.length) return 0
  return Math.round((store.currentWaypointIndex / store.waypoints.length) * 100)
})

// ── Mission controls ──────────────────────────────────────────────────────────
const _loopActive = ref(false)
let _loopIteration = 0, _loopMax = 0

watch(() => store.missionRunning, (running) => {
  if (running || !_loopActive.value) return
  _loopIteration++
  if (_loopMax === 0 || _loopIteration < _loopMax) ros.followWaypoints(store.waypoints)
  else _loopActive.value = false
})

function startMission() {
  // Pastikan semua waypoint punya stationId — fallback ke nama waypoint
  console.info('[MissionPanel] Start mission clicked', {
    waypointCount: store.waypoints.length,
    missionLoop: store.missionLoop,
    missionLoopCount: store.missionLoopCount,
    missionTimeoutSec: store.missionTimeoutSec,
  })
  store.waypoints.forEach(w => {
    if (!w.stationId) {
      const sid = w.name.replace(/\s+/g, '_')
      store.updateWaypoint(w.id, { stationId: sid })
      w.stationId = sid
    }
    // Re-register station ke robot supaya mission_manager tau posisinya
    ros.configStation({
      station_id: w.stationId,
      station_type: { NoAction: 2, Pick: 0, Drop: 1, DropPick: 2 }[w.task] ?? 0,
      action: 1,
      x: w.x, y: w.y, yaw: w.theta ?? 0,
    })
  })
  _loopIteration = 0
  _loopActive.value = store.missionLoop
  _loopMax = store.missionLoop && store.missionLoopCount > 0 ? store.missionLoopCount : 0
  console.info('[MissionPanel] Publishing mission payload', store.waypoints.map(w => ({
    name: w.name,
    stationId: w.stationId,
    task: w.task,
    continueMode: w.continueMode,
  })))
  ros.publishMissionPayload(store.waypoints)
  console.info('[MissionPanel] Starting mission execution')
  ros.followWaypoints(store.waypoints)
}

function pauseMission() { _loopActive.value = false; ros.cancelNavigation(); store.pauseMission() }
function stopMission()  { _loopActive.value = false; ros.cancelNavigation(); store.stopMission() }

function doConfirm() {
  ros.confirmMission({
    onError: (err) => toast.error('Confirm failed: ' + err),
  })
}

// ── Save / Load ───────────────────────────────────────────────────────────────
const showSave       = ref(false)
const showLoad       = ref(false)
const saving         = ref(false)
const saveName       = ref('')
const savedMissions  = ref([])
const loadingMissions = ref(false)
const loadError      = ref('')

async function openLoad() {
  showLoad.value = true; loadError.value = ''; loadingMissions.value = true; savedMissions.value = []
  try {
    savedMissions.value = await api.get(store.activeMapId ? `/missions?map_id=${store.activeMapId}` : '/missions')
  } catch (err) { loadError.value = err.message }
  finally { loadingMissions.value = false }
}

async function doSave() {
  if (!saveName.value.trim()) return
  saving.value = true
  try {
    await api.post('/missions', {
      name: saveName.value.trim(), map_id: store.activeMapId,
      waypoints: store.waypoints.map(w => ({ name: w.name, x: w.x, y: w.y, theta: w.theta ?? 0, task: w.task ?? 'NoAction', continue_mode: w.continueMode ?? 'Auto', dest_point: w.destPoint ?? null, station_id: w.stationId ?? null })),
      loop: store.missionLoop, loop_count: store.missionLoopCount,
    })
    const name = saveName.value.trim(); showSave.value = false; saveName.value = ''
    toast.success(`Mission "${name}" saved`)
  } catch (err) { toast.error('Save failed: ' + err.message) }
  finally { saving.value = false }
}

function doLoad(m) {
  store.waypoints = m.waypoints.map((w, i) => ({ id: Date.now() + i, name: w.name, x: w.x, y: w.y, theta: w.theta ?? 0, task: w.task ?? 'NoAction', continueMode: w.continue_mode ?? 'Auto', destPoint: w.dest_point ?? null, stationId: w.station_id ?? null }))
  store.missionLoop = m.loop; store.missionLoopCount = m.loop_count
  showLoad.value = false; toast.success(`Mission "${m.name}" loaded`)
}

async function doDeleteMission(id) {
  try { await api.del(`/missions/${id}`); savedMissions.value = savedMissions.value.filter(m => m.id !== id) }
  catch (err) { toast.error('Delete failed: ' + err.message) }
}

defineExpose({ onMapClick })
</script>
