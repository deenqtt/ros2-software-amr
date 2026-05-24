<template>
  <div class="space-y-4">

    <!-- ── Status & Controls ──────────────────────────────────────── -->
    <div>
      <div class="text-[10px] font-semibold tracking-widest text-muted-foreground uppercase flex items-center gap-1.5 mb-2">
        <PlugZap :size="10" /> Docking Control
      </div>

      <div class="flex items-center justify-between rounded-md border border-border bg-card px-3 py-2 mb-3">
        <span class="text-xs text-muted-foreground">Status</span>
        <Badge :variant="dockVariant" class="text-[10px] font-mono uppercase">
          {{ store.dockingStatus }}
        </Badge>
      </div>

      <div class="space-y-1 mb-3">
        <Label class="text-[10px] text-muted-foreground">Target Station</Label>
        <select v-model="selectedDockId"
          class="w-full bg-secondary border border-border rounded-md px-2 py-1.5 text-xs text-foreground outline-none focus:ring-1 focus:ring-ring">
          <option :value="null" disabled>— Select dock —</option>
          <option v-for="d in store.dockStations" :key="d.id" :value="d.id">{{ d.name }}</option>
        </select>
        <div v-if="selectedDock" class="text-[10px] font-data text-muted-foreground">
          x={{ selectedDock.target.x.toFixed(2) }}, y={{ selectedDock.target.y.toFixed(2) }}, yaw={{ selectedDock.target.yaw.toFixed(2) }}
        </div>
      </div>

      <div class="flex flex-col gap-1.5">
        <Button class="w-full text-xs bg-amr-ok text-black hover:bg-amr-ok/90"
          :disabled="!store.rosConnected || store.dockingActive || !selectedDock || dockPending"
          @click="dock">
          <Anchor :size="12" class="mr-1.5" />
          {{ dockPending ? 'Sending…' : 'Send to Dock' }}
        </Button>
        <div class="flex gap-1.5">
          <Button variant="outline" class="flex-1 text-xs"
            :disabled="!store.rosConnected || store.dockingStatus !== 'docked' || undockPending"
            @click="undock">
            {{ undockPending ? '…' : 'Undock' }}
          </Button>
          <Button v-if="store.dockingActive" variant="destructive" class="flex-1 text-xs" @click="cancelDock">
            Cancel
          </Button>
        </div>
      </div>
    </div>

    <Separator />

    <!-- ── Auto-Docking ────────────────────────────────────────────── -->
    <div>
      <div class="text-[10px] font-semibold tracking-widest text-muted-foreground uppercase flex items-center gap-1.5 mb-3">
        <Zap :size="10" class="text-amr-warning" /> Auto-Docking
      </div>

      <div class="rounded-md border border-border bg-card p-3 space-y-3">
        <div class="flex items-center justify-between">
          <Label class="text-xs cursor-pointer" for="autodock-sw">Enable Auto-Dock</Label>
          <Switch id="autodock-sw"
            :model-value="store.autoDockEnabled"
            @update:model-value="store.setAutoDockEnabled($event)" />
        </div>

        <div class="space-y-1.5">
          <div class="flex justify-between text-[10px] text-muted-foreground">
            <span>Battery Threshold</span>
            <span class="font-data text-amr-warning">{{ store.lowBatteryThreshold }}%</span>
          </div>
          <Slider
            :model-value="[store.lowBatteryThreshold]"
            @update:model-value="store.lowBatteryThreshold = $event[0]"
            :min="5" :max="50" :step="1" class="w-full" />
        </div>

        <div class="space-y-1">
          <Label class="text-[10px] text-muted-foreground">Target Dock</Label>
          <select :value="store.autoDockTargetId"
            @change="store.setAutoDockTargetId(Number($event.target.value))"
            class="w-full bg-background border border-border rounded-md px-2 py-1 text-xs text-foreground outline-none">
            <option :value="0">— Select Dock —</option>
            <option v-for="d in store.dockStations" :key="d.id" :value="d.id">{{ d.name }}</option>
          </select>
        </div>

        <div v-if="store.autoDockEnabled && !store.autoDockTargetId"
          class="text-[10px] text-amr-danger bg-amr-danger/10 border border-amr-danger/20 rounded px-2 py-1.5">
          Select a target dock to enable auto-docking.
        </div>
      </div>
    </div>

    <Separator />

    <!-- ── Dock Stations ───────────────────────────────────────────── -->
    <div>
      <div class="flex items-center justify-between mb-2">
        <div class="text-[10px] font-semibold tracking-widest text-muted-foreground uppercase flex items-center gap-1.5">
          <MapPin :size="10" /> Dock Stations
        </div>
        <Button variant="ghost" size="sm" class="h-6 px-2 text-xs" @click="startDockPlacement">
          <Pencil :size="10" class="mr-1" /> Place
        </Button>
      </div>

      <div class="space-y-1 max-h-40 overflow-y-auto mb-3">
        <div v-if="store.dockStations.length === 0"
          class="text-center text-muted-foreground text-xs py-4 border border-dashed border-border rounded-md">
          No dock stations.
        </div>

        <div v-for="dock in store.dockStations" :key="dock.id"
          class="group rounded-md border border-border bg-card p-2 space-y-1">
          <div class="flex items-center gap-2">
            <span class="w-2 h-2 rounded-full shrink-0"
              :class="selectedDockId === dock.id ? 'bg-amr-warning' : 'bg-muted-foreground/30'" />
            <template v-if="editingId === dock.id">
              <input v-model="editingName"
                class="flex-1 bg-background border border-border rounded px-1.5 py-0.5 text-xs text-foreground outline-none focus:ring-1 focus:ring-ring"
                @keyup.enter="saveRename(dock)" @keyup.escape="editingId = null" @blur="saveRename(dock)" />
            </template>
            <span v-else class="flex-1 text-xs text-foreground truncate cursor-pointer hover:text-muted-foreground"
              @click="selectedDockId = dock.id">
              {{ dock.name }}
            </span>
            <button class="p-0.5 text-muted-foreground hover:text-foreground opacity-0 group-hover:opacity-100 transition-opacity"
              @click="startRename(dock)"><Pencil :size="11" /></button>
            <button class="p-0.5 text-amr-danger opacity-0 group-hover:opacity-100 transition-opacity"
              @click="removeDock(dock.id)"><X :size="11" /></button>
          </div>
          <div class="text-[10px] font-data text-muted-foreground pl-4">
            x={{ dock.target.x.toFixed(2) }}, y={{ dock.target.y.toFixed(2) }}, yaw={{ dock.target.yaw.toFixed(2) }}
          </div>
        </div>
      </div>
    </div>

    <Separator />

    <!-- ── Add Dock Station ────────────────────────────────────────── -->
    <div>
      <div class="text-[10px] font-semibold tracking-widest text-muted-foreground uppercase flex items-center gap-1.5 mb-2">
        <Plus :size="10" /> Add Dock Station
      </div>

      <div class="space-y-2">
        <Input v-model="newDock.name" placeholder="Dock name" class="text-xs h-8" />

        <div>
          <Label class="text-[10px] text-muted-foreground uppercase tracking-wider">Target</Label>
          <div class="grid grid-cols-3 gap-1 mt-1">
            <Input v-model.number="newDock.target.x" type="number" step="0.1" placeholder="X"
              class="text-xs h-7 font-data px-2" />
            <Input v-model.number="newDock.target.y" type="number" step="0.1" placeholder="Y"
              class="text-xs h-7 font-data px-2" />
            <Input v-model.number="newDock.target.yaw" type="number" step="0.1" placeholder="Yaw"
              class="text-xs h-7 font-data px-2" />
          </div>
        </div>

        <Button class="w-full text-xs" :disabled="!newDock.name || addingDock" @click="addDock">
          {{ addingDock ? 'Adding…' : 'Add Dock Station' }}
        </Button>
      </div>
    </div>

  </div>
</template>

<script setup>
import { ref, computed, watch, onMounted } from 'vue'
import { useRobotStore } from '@/stores/robot'
import { useROS }        from '@/composables/useROS'
import { useAPI }        from '@/composables/useAPI'
import { useMapMode }    from '@/composables/useMapMode'
import { PlugZap, Zap, MapPin, Pencil, Plus, X, Anchor } from 'lucide-vue-next'
import { toast } from 'vue-sonner'

import { Button }    from '@/components/ui/button'
import { Badge }     from '@/components/ui/badge'
import { Switch }    from '@/components/ui/switch'
import { Slider }    from '@/components/ui/slider'
import { Input }     from '@/components/ui/input'
import { Label }     from '@/components/ui/label'
import { Separator } from '@/components/ui/separator'

const store = useRobotStore()
const ros   = useROS()
const api   = useAPI()
const { setMode } = useMapMode()

const selectedDockId = ref(null)
const dockPending    = ref(false)
const undockPending  = ref(false)
const addingDock     = ref(false)
const editingId      = ref(null)
const editingName    = ref('')

const newDock = ref({
  name: '', target: { x: 0, y: 0, yaw: 0 },
})

const selectedDock = computed(() => store.dockStations.find(d => d.id === selectedDockId.value) ?? null)

const dockVariant = computed(() => {
  const s = store.dockingStatus
  if (s === 'error')    return 'destructive'
  if (s === 'docked')   return 'default'
  return 'outline'
})

async function fetchDocks() {
  try {
    const url = store.activeMapId ? `/docks?map_id=${store.activeMapId}` : '/docks'
    const list = await api.get(url)
    store.setDockStations(list)
    if (list.length > 0 && !selectedDockId.value) selectedDockId.value = list[0].id
    list.forEach(dock => {
      ros.configStation({ station_id: dock.name, station_type: 3, action: 1,
        x: dock.target.x, y: dock.target.y, yaw: dock.target.yaw })
    })
  } catch (err) { console.warn('[DockingPanel] fetch docks failed:', err) }
}

onMounted(fetchDocks)
watch(() => store.activeMapId, fetchDocks)

function dock() {
  if (!selectedDock.value) return
  dockPending.value = true
  ros.sendToDock(selectedDock.value)
  toast.info(`Sending to dock: ${selectedDock.value.name}`)
  const unwatch = watch(() => store.dockingStatus, s => {
    if (s !== 'idle') { dockPending.value = false; unwatch() }
  })
}

function undock() {
  if (!selectedDock.value) return
  undockPending.value = true; ros.undock(selectedDock.value); store.setDockingStatus('undocking'); toast.info(`Undocking from ${selectedDock.value.name}…`)
  const unwatch = watch(() => store.dockingStatus, s => {
    if (s !== 'docked') { undockPending.value = false; unwatch() }
  })
}

function cancelDock() { ros.cancelNavigation(); store.setDockingStatus('idle'); toast.info('Docking cancelled') }
function startDockPlacement() { setMode('dock_placement') }

async function addDock() {
  if (!newDock.value.name) return
  addingDock.value = true
  try {
    const created = await api.post('/docks', { map_id: store.activeMapId ?? null, name: newDock.value.name, target: { ...newDock.value.target } })
    store.addDockStation(created)
    selectedDockId.value = created.id
    await ros.configStation({ station_id: created.name, station_type: 3, action: 1,
      x: created.target.x, y: created.target.y, yaw: created.target.yaw })
    newDock.value = { name: '', target: { x: 0, y: 0, yaw: 0 } }
    toast.success(`Dock "${created.name}" added`)
  } catch (err) { toast.error('Failed to add dock: ' + err.message) }
  finally { addingDock.value = false }
}

async function removeDock(id) {
  try {
    const dock = store.dockStations.find(d => d.id === id)
    if (dock) ros.configStation({ station_id: dock.name, station_type: 3, action: 0 })
    await api.del(`/docks/${id}`)
    store.removeDockStation(id)
    if (selectedDockId.value === id) selectedDockId.value = store.dockStations[0]?.id ?? null
    toast.success('Dock station removed')
  } catch (err) { toast.error('Failed to remove dock: ' + err.message) }
}

function startRename(dock) { editingId.value = dock.id; editingName.value = dock.name }

async function saveRename(dock) {
  if (!editingName.value || editingName.value === dock.name) { editingId.value = null; return }
  try {
    const updated = await api.put(`/docks/${dock.id}`, { map_id: dock.map_id, name: editingName.value, target: { ...dock.target } })
    const found = store.dockStations.find(d => d.id === dock.id)
    if (found) found.name = updated.name
    ros.configStation({ station_id: updated.name, station_type: 3, action: 1,
      x: dock.target.x, y: dock.target.y, yaw: dock.target.yaw })
    toast.success('Dock renamed')
  } catch (err) { toast.error('Failed to rename dock: ' + err.message) }
  finally { editingId.value = null }
}
</script>
