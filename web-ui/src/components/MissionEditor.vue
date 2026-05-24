<template>
  <div class="panel p-3 flex flex-col gap-3">
    <div class="flex items-center justify-between">
      <div class="panel-header"><MapPin :size="14" class="text-amr-purple" /> Waypoint Mission</div>
      <div class="flex items-center gap-2">
        <span class="text-xs font-mono" :class="store.waypoints.length >= 5 ? 'text-red-400' : 'text-slate-400'">
          {{ store.waypoints.length }}/5
        </span>
        <button class="btn-ghost text-xs px-2 py-1" @click="showSave = true">Save</button>
        <button class="btn-ghost text-xs px-2 py-1" @click="openLoad">Load</button>
        <button class="btn-danger text-xs px-2 py-1" @click="store.clearWaypoints">Clear</button>
      </div>
    </div>

    <!-- Waypoint list -->
    <div class="max-h-48 overflow-y-auto flex flex-col gap-1">
      <div
        v-if="store.waypoints.length === 0"
        class="text-center text-slate-500 text-xs py-6"
      >
        No waypoints yet.<br />
        Click map in "Waypoint" mode or use the + button.
      </div>

      <div
        v-for="(wp, i) in store.waypoints"
        :key="wp.id"
        class="flex flex-col gap-1 bg-slate-800 rounded px-2 py-1.5 group"
        :class="{ 'ring-1 ring-blue-500': store.currentWaypointIndex === i && store.missionRunning }"
      >
        <!-- Row 1: index, name, coords, actions -->
        <div class="flex items-center gap-2">
          <!-- Index badge -->
          <span class="text-xs text-slate-400 w-5 text-center shrink-0">{{ i + 1 }}</span>

          <!-- Name (editable) -->
          <input
            :value="wp.name"
            class="flex-1 bg-transparent text-sm text-slate-200 outline-none min-w-0 border-b border-transparent focus:border-amr-border"
            @change="store.updateWaypoint(wp.id, { name: $event.target.value })"
          />

          <!-- Coords -->
          <span class="text-xs font-mono text-slate-500 shrink-0">
            ({{ wp.x.toFixed(1) }}, {{ wp.y.toFixed(1) }})
          </span>

          <!-- Up / Down / Delete -->
          <div class="flex gap-0.5 opacity-0 group-hover:opacity-100 transition-opacity shrink-0">
            <button
              class="text-slate-400 hover:text-white px-1 flex items-center"
              :disabled="i === 0"
              @click="moveUp(i)"
            ><ChevronUp :size="13" /></button>
            <button
              class="text-slate-400 hover:text-white px-1 flex items-center"
              :disabled="i === store.waypoints.length - 1"
              @click="moveDown(i)"
            ><ChevronDown :size="13" /></button>
            <button
              class="text-red-400 hover:text-red-300 px-1 flex items-center"
              @click="store.removeWaypoint(wp.id)"
            ><X :size="13" /></button>
          </div>
        </div>

        <!-- Row 2: Task + Continue Mode -->
        <div class="flex gap-2 pl-7">
          <div class="flex items-center gap-1">
            <span class="text-xs text-slate-500">Task:</span>
            <select
              :value="wp.task"
              class="bg-slate-700 border border-amr-border rounded px-1 py-0.5 text-xs text-slate-200"
              @change="store.updateWaypoint(wp.id, { task: $event.target.value })"
            >
              <option value="NoAction">No Action</option>
              <option value="Pick">Pick</option>
              <option value="Drop">Drop</option>
              <option value="DropPick">Pick &amp; Drop</option>
            </select>
          </div>
          <div class="flex items-center gap-1">
            <span class="text-xs text-slate-500">Mode:</span>
            <select
              :value="wp.continueMode"
              class="bg-slate-700 border border-amr-border rounded px-1 py-0.5 text-xs text-slate-200"
              @change="store.updateWaypoint(wp.id, { continueMode: $event.target.value })"
            >
              <option value="Auto">Auto</option>
              <option value="Manual">Manual</option>
            </select>
          </div>
        </div>
      </div>
    </div>

    <!-- Add destinasi dari daftar destination points -->
    <div class="flex flex-col gap-1">
      <div
        v-if="store.destinations.length === 0"
        class="text-xs text-slate-500 text-center py-1"
      >
        Buat destination point dulu di panel "Destination Points"
      </div>
      <div v-else class="flex gap-1 flex-wrap">
        <select
          v-model="newDestId"
          class="flex-1 bg-slate-800 border border-amr-border rounded px-1 py-1 text-xs text-slate-200"
        >
          <option :value="null" disabled>Pilih titik...</option>
          <option v-for="(d, i) in store.destinations" :key="d.id" :value="d.id">
            Point {{ i + 1 }} — {{ d.name }}
          </option>
        </select>
        <select
          v-model="newTask"
          class="bg-slate-800 border border-amr-border rounded px-1 py-1 text-xs text-slate-200"
        >
          <option value="NoAction">No Action (0)</option>
          <option value="Pick">Pick (1)</option>
          <option value="Drop">Drop (2)</option>
          <option value="DropPick">Pick &amp; Drop (3)</option>
        </select>
        <select
          v-model="newContinueMode"
          class="bg-slate-800 border border-amr-border rounded px-1 py-1 text-xs text-slate-200"
        >
          <option value="Auto">Auto (1)</option>
          <option value="Manual">Manual (2)</option>
        </select>
        <button
          class="btn-purple text-xs px-2 py-1"
          :disabled="store.waypoints.length >= 5 || !newDestId"
          @click="addFromDest"
        >+ Add</button>
      </div>
      <p v-if="store.waypoints.length >= 5" class="text-xs text-red-400">
        Maksimum 5 destinasi tercapai.
      </p>
    </div>

    <hr class="border-amr-border" />

    <!-- Mission options -->
    <div class="flex items-center gap-3 flex-wrap">
      <label class="flex items-center gap-1.5 text-xs text-slate-300 cursor-pointer">
        <input type="checkbox" v-model="store.missionLoop" class="accent-blue-500" />
        Loop
      </label>
      <div v-if="store.missionLoop" class="flex items-center gap-1 text-xs text-slate-400">
        Count:
        <input
          v-model.number="store.missionLoopCount"
          type="number" min="0" step="1"
          class="w-14 bg-slate-800 border border-amr-border rounded px-1 py-0.5 text-xs font-mono text-slate-200"
          placeholder="0=∞"
        />
      </div>
      <div class="flex items-center gap-1 text-xs text-slate-400">
        Timeout:
        <input
          v-model.number="store.missionTimeoutSec"
          type="number" min="10" step="10"
          class="w-14 bg-slate-800 border border-amr-border rounded px-1 py-0.5 text-xs font-mono text-slate-200"
          title="Seconds per waypoint before forcing advance"
        />s
      </div>
    </div>

    <!-- Mission controls: Start / Pause / Stop (no Resume — too buggy) -->
    <div class="flex gap-2">
      <button
        class="btn-success flex-1 text-sm"
        :disabled="!store.rosConnected || store.waypoints.length === 0 || store.missionRunning"
        @click="startMission"
      >
        Start
      </button>
      <button
        class="btn-warning text-sm px-3"
        :disabled="!store.missionRunning"
        @click="pauseMission"
      >
        Pause
      </button>
      <button
        class="btn-danger text-sm px-3"
        :disabled="!store.rosConnected"
        @click="stopMission"
      >
        Stop
      </button>
    </div>

    <!-- Save modal -->
    <div
      v-if="showSave"
      class="fixed inset-0 bg-black/60 flex items-center justify-center z-[2000]"
      @click.self="showSave = false"
    >
      <div class="panel p-4 w-72 flex flex-col gap-3">
        <div class="text-sm font-medium">Save Mission</div>
        <input
          v-model="saveName"
          class="bg-slate-800 border border-amr-border rounded px-2 py-1 text-sm text-slate-200"
          placeholder="Mission name"
          @keyup.enter="doSave"
        />
        <div class="flex gap-2">
          <button class="btn-primary flex-1 text-sm" :disabled="saving" @click="doSave">
            {{ saving ? 'Saving…' : 'Save' }}
          </button>
          <button class="btn-ghost flex-1 text-sm" @click="showSave = false">Cancel</button>
        </div>
      </div>
    </div>

    <!-- Load modal -->
    <div
      v-if="showLoad"
      class="fixed inset-0 bg-black/60 flex items-center justify-center z-[2000]"
      @click.self="showLoad = false"
    >
      <div class="panel p-4 w-72 flex flex-col gap-3">
        <div class="text-sm font-medium">Load Mission</div>
        <div v-if="loadingMissions" class="text-xs text-slate-500 text-center py-4">
          Loading...
        </div>
        <div v-else-if="loadError" class="text-xs text-red-400">{{ loadError }}</div>
        <div
          v-else-if="savedMissions.length === 0"
          class="text-xs text-slate-500 text-center py-4"
        >
          No saved missions.
        </div>
        <div
          v-else
          v-for="m in savedMissions"
          :key="m.id"
          class="flex items-center gap-2 bg-slate-800 rounded px-2 py-1.5"
        >
          <span class="flex-1 text-sm text-slate-200">{{ m.name }}</span>
          <span class="text-xs text-slate-500">{{ m.waypoints.length }} pts</span>
          <button class="btn-primary text-xs px-2 py-0.5" @click="doLoad(m)">Load</button>
          <button class="btn-danger text-xs px-2 py-0.5" @click="doDeleteMission(m.id)">✕</button>
        </div>
        <button class="btn-ghost text-sm" @click="showLoad = false">Close</button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, watch } from 'vue'
import { useRobotStore } from '@/stores/robot'
import { useROS } from '@/composables/useROS'
import { useAPI } from '@/composables/useAPI'
import { useToast } from '@/composables/useToast'
import { MapPin, ChevronUp, ChevronDown, X } from 'lucide-vue-next'

const store = useRobotStore()
const ros = useROS()
const api = useAPI()
const toast = useToast()

const newDestId = ref(null)
const newTask = ref('NoAction')
const newContinueMode = ref('Auto')
const showSave = ref(false)
const showLoad = ref(false)
const saving = ref(false)
const loadingMissions = ref(false)
const saveName = ref('')
const savedMissions = ref([])
const loadError = ref('')

// ── Loop control state ────────────────────────────────────────────────────────
const _loopActive = ref(false)
let _loopIteration = 0
let _loopMax = 0

// Event-driven loop restart: watch for mission completion instead of polling
watch(() => store.missionRunning, (running) => {
  if (running || !_loopActive.value) return
  _loopIteration++
  // _loopMax === 0 means infinite; otherwise respect the count
  if (_loopMax === 0 || _loopIteration < _loopMax) {
    ros.followWaypoints(store.waypoints)
  } else {
    _loopActive.value = false
  }
})

// ── Waypoint management ───────────────────────────────────────────────────────

function addFromDest() {
  if (!newDestId.value) return
  const dest = store.destinations.find((d) => d.id === newDestId.value)
  if (!dest) return
  const pointNum = store.destinations.indexOf(dest) + 1
  const added = store.addWaypoint(dest.x, dest.y, 0, `Point ${pointNum} — ${dest.name}`, newTask.value, newContinueMode.value, pointNum)
  if (!added) {
    toast.error('Maksimum 5 destinasi')
    return
  }
  newDestId.value = null
}

function moveUp(i) {
  const wps = [...store.waypoints]
  ;[wps[i - 1], wps[i]] = [wps[i], wps[i - 1]]
  store.reorderWaypoints(wps)
}

function moveDown(i) {
  const wps = [...store.waypoints]
  ;[wps[i], wps[i + 1]] = [wps[i + 1], wps[i]]
  store.reorderWaypoints(wps)
}

// ── Mission controls ──────────────────────────────────────────────────────────

function startMission() {
  _loopIteration = 0
  if (store.missionLoop) {
    _loopActive.value = true
    _loopMax = store.missionLoopCount > 0 ? store.missionLoopCount : 0
  } else {
    _loopActive.value = false
  }
  // Publish payload numerik ke robot
  ros.publishMissionPayload(store.waypoints)
  // Kirim ke Nav2 untuk eksekusi navigasi
  ros.followWaypoints(store.waypoints)
}

function pauseMission() {
  _loopActive.value = false // stop loop on pause
  ros.cancelNavigation()
  store.pauseMission()
}

function stopMission() {
  _loopActive.value = false
  ros.cancelNavigation()
  store.stopMission()
}

// ── Save / load ───────────────────────────────────────────────────────────────

async function openLoad() {
  showLoad.value = true
  loadError.value = ''
  loadingMissions.value = true
  savedMissions.value = []
  try {
    const url = store.activeMapId ? `/missions?map_id=${store.activeMapId}` : '/missions'
    savedMissions.value = await api.get(url)
  } catch (err) {
    loadError.value = err.message
  } finally {
    loadingMissions.value = false
  }
}

async function doSave() {
  if (!saveName.value.trim()) return
  saving.value = true
  try {
    await api.post('/missions', {
      name: saveName.value.trim(),
      map_id: store.activeMapId,
      waypoints: store.waypoints.map((w) => ({
        name: w.name, x: w.x, y: w.y, theta: w.theta ?? 0,
        task: w.task ?? 'NoAction', continue_mode: w.continueMode ?? 'Auto',
        dest_point: w.destPoint ?? null,
      })),
      loop: store.missionLoop,
      loop_count: store.missionLoopCount,
    })
    showSave.value = false
    const name = saveName.value.trim()
    saveName.value = ''
    toast.success(`Mission "${name}" saved`)
  } catch (err) {
    console.error('[MissionEditor] save failed:', err)
    toast.error('Save failed: ' + err.message)
  } finally {
    saving.value = false
  }
}

function doLoad(mission) {
  store.waypoints = mission.waypoints.map((w, i) => ({
    id: Date.now() + i,
    name: w.name,
    x: w.x,
    y: w.y,
    theta: w.theta ?? 0,
    task: w.task ?? 'NoAction',
    continueMode: w.continue_mode ?? 'Auto',
    destPoint: w.dest_point ?? null,
  }))
  store.missionLoop = mission.loop
  store.missionLoopCount = mission.loop_count
  showLoad.value = false
  toast.success(`Mission "${mission.name}" loaded`)
}

async function doDeleteMission(id) {
  try {
    await api.del(`/missions/${id}`)
    savedMissions.value = savedMissions.value.filter((m) => m.id !== id)
  } catch (err) {
    console.error('[MissionEditor] delete failed:', err)
    toast.error('Delete failed: ' + err.message)
  }
}
</script>
