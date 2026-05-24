<template>
  <div class="space-y-4">

    <!-- ── System Stats ────────────────────────────────────────────── -->
    <div class="grid grid-cols-3 gap-2">
      <div v-for="(val, key) in { CPU: stats.cpu, MEM: stats.mem, LAT: stats.latency }" :key="key"
        class="rounded-md border border-border bg-card p-2 text-center">
        <div class="text-[9px] text-muted-foreground uppercase tracking-wider mb-1">{{ key }}</div>
        <div class="text-xs font-data font-bold text-foreground">{{ val }}</div>
      </div>
    </div>

    <Separator />

    <!-- ── Maps ────────────────────────────────────────────────────── -->
    <div>
      <div class="flex items-center justify-between mb-2">
        <div class="text-[10px] font-semibold tracking-widest text-muted-foreground uppercase flex items-center gap-1.5">
          <Map :size="10" /> Maps
        </div>
        <Button variant="ghost" size="sm" class="h-6 px-2 text-xs" :disabled="loading" @click="refresh">
          <RefreshCw :size="10" class="mr-1" :class="loading ? 'animate-spin' : ''" />
          Refresh
        </Button>
      </div>

      <div v-if="mapError" class="text-xs text-amr-danger bg-amr-danger/5 border border-amr-danger/20 rounded-md px-2 py-1.5 mb-2">
        {{ mapError }}
      </div>

      <div class="space-y-1 max-h-32 overflow-y-auto mb-2">
        <div v-if="!loading && store.maps.length === 0"
          class="text-center text-muted-foreground text-xs py-4 border border-dashed border-border rounded-md">
          No maps. Upload one below.
        </div>
        <div v-for="map in store.maps" :key="map.id"
          class="flex items-center gap-2 rounded-md border bg-card px-2 py-2"
          :class="store.activeMapId === map.id ? 'border-amr-data/40 bg-amr-data/5' : 'border-border'">
          <div class="w-2 h-2 rounded-full shrink-0"
            :class="store.activeMapId === map.id ? 'bg-amr-data' : 'bg-muted-foreground/30'" />
          <div class="flex-1 min-w-0">
            <div class="text-xs text-foreground truncate font-medium">{{ map.name }}</div>
            <div class="text-[10px] font-data text-muted-foreground truncate">
              {{ map.yaml_file }}<span v-if="map.resolution"> · {{ map.resolution }}m/px</span>
            </div>
          </div>
          <Button size="sm" class="text-[10px] h-6 px-2 shrink-0"
            :variant="store.activeMapId === map.id ? 'default' : 'outline'"
            :disabled="activating === map.id || store.activeMapId === map.id"
            @click="activateMap(map)">
            {{ store.activeMapId === map.id ? 'Active' : (activating === map.id ? '…' : 'Activate') }}
          </Button>
        </div>
      </div>

      <!-- Upload Map -->
      <div class="text-[10px] font-semibold tracking-widest text-muted-foreground uppercase flex items-center gap-1.5 mb-2">
        <Upload :size="10" /> Upload Map
      </div>

      <div class="border-2 border-dashed rounded-lg p-3 text-center cursor-pointer transition-colors"
        :class="isDragging ? 'border-amr-data/60 bg-amr-data/5' : 'border-border hover:border-muted-foreground/30'"
        @dragover.prevent="isDragging = true" @dragleave="isDragging = false"
        @drop.prevent="onDrop" @click="triggerFilePicker">
        <div class="text-xs text-muted-foreground flex flex-col items-center gap-1.5">
          <Upload :size="14" />
          <span v-if="!uploadFiles.yaml && !uploadFiles.pgm">
            Drop <code>.yaml</code> + <code>.pgm/.png</code> or click
          </span>
          <div v-else class="text-left w-full space-y-0.5">
            <div class="flex items-center gap-1.5" :class="uploadFiles.yaml ? 'text-amr-ok' : ''">
              <CheckCircle v-if="uploadFiles.yaml" :size="11" />
              <span v-else class="w-2.5 h-2.5 rounded-full border border-border inline-block" />
              <span class="text-[10px] truncate">{{ uploadFiles.yaml?.name ?? '.yaml — missing' }}</span>
            </div>
            <div class="flex items-center gap-1.5" :class="uploadFiles.pgm ? 'text-amr-ok' : ''">
              <CheckCircle v-if="uploadFiles.pgm" :size="11" />
              <span v-else class="w-2.5 h-2.5 rounded-full border border-border inline-block" />
              <span class="text-[10px] truncate">{{ uploadFiles.pgm?.name ?? '.pgm — missing' }}</span>
            </div>
          </div>
        </div>
        <input ref="fileInputEl" type="file" multiple accept=".yaml,.pgm,.png" class="hidden" @change="onFileInput" />
      </div>

      <div v-if="uploading" class="mt-1.5">
        <Progress :model-value="uploadProgress" class="h-1" />
      </div>

      <div class="flex gap-1.5 mt-2">
        <Button class="flex-1 text-xs"
          :disabled="!uploadFiles.yaml || !uploadFiles.pgm || uploading"
          @click="doUpload">
          <Upload v-if="!uploading" :size="11" class="mr-1.5" />
          <span v-else class="mr-1.5 animate-spin">⟳</span>
          {{ uploading ? 'Uploading…' : 'Upload Map' }}
        </Button>
        <Button v-if="uploadFiles.yaml || uploadFiles.pgm" variant="ghost" size="sm"
          class="text-xs h-8 px-2" @click="clearFiles">Clear</Button>
      </div>
    </div>

    <Separator />

    <!-- ── Keepout Zones ────────────────────────────────────────────── -->
    <div>
      <div class="text-[10px] font-semibold tracking-widest text-muted-foreground uppercase flex items-center gap-1.5 mb-2">
        <ShieldOff :size="10" class="text-amr-warning" /> Keepout Zones
      </div>

      <Button class="w-full text-xs mb-2 bg-amr-warning text-black hover:bg-amr-warning/90" @click="startDraw">
        <Pencil :size="11" class="mr-1.5" /> Draw New Zone
      </Button>

      <div class="space-y-1 max-h-32 overflow-y-auto mb-2">
        <div v-if="store.keepoutZones.length === 0"
          class="text-center text-muted-foreground text-xs py-3 border border-dashed border-border rounded-md">
          No keepout zones.
        </div>
        <div v-for="zone in store.keepoutZones" :key="zone.id"
          class="group flex items-center gap-2 rounded-md border border-border bg-card px-2 py-1.5">
          <div class="w-2.5 h-2.5 rounded-sm bg-amr-warning shrink-0" />
          <span class="flex-1 text-xs text-foreground truncate">{{ zone.name }}</span>
          <span class="text-[10px] text-muted-foreground font-data shrink-0">{{ zone.polygon.length }}v</span>
          <button class="p-0.5 text-amr-danger opacity-0 group-hover:opacity-100 transition-opacity"
            @click="removeZone(zone.id)"><X :size="12" /></button>
        </div>
      </div>

      <Button v-if="store.keepoutZones.length > 0" variant="ghost" size="sm"
        class="w-full text-xs text-amr-danger hover:text-amr-danger" @click="clearAllZones">
        Clear All Zones
      </Button>
    </div>

  </div>
</template>

<script setup>
import { ref, computed, watch, onMounted } from 'vue'
import { useRobotStore }  from '@/stores/robot'
import { useROS }         from '@/composables/useROS'
import { useAPI }         from '@/composables/useAPI'
import { useMapMode }     from '@/composables/useMapMode'
import { useSystemStats } from '@/composables/useSystemStats'
import { Map, Upload, CheckCircle, ShieldOff, Pencil, X, RefreshCw } from 'lucide-vue-next'
import { toast } from 'vue-sonner'

import { Button }    from '@/components/ui/button'
import { Progress }  from '@/components/ui/progress'
import { Separator } from '@/components/ui/separator'

const store = useRobotStore()
const ros   = useROS()
const api   = useAPI()
const stats = useSystemStats()
const { setMode } = useMapMode()

// ── Maps ──────────────────────────────────────────────────────────────────────
const loading    = ref(false)
const mapError   = ref('')
const activating = ref(null)

function setMapError(msg) {
  mapError.value = msg
  if (msg) setTimeout(() => { mapError.value = '' }, 5000)
}

async function refresh() {
  loading.value = true; setMapError('')
  try { store.setMaps(await api.get('/maps')) }
  catch (err) { setMapError('Backend unavailable: ' + err.message) }
  finally { loading.value = false }
}

async function activateMap(map) {
  activating.value = map.id; setMapError('')
  try {
    const result = await api.post(`/maps/${map.id}/activate`, {})
    store.setActiveMap(map.id)
    ros.loadMap(result.yaml_path)
    const keepouts = await api.get(`/keepout?map_id=${map.id}`)
    store.keepoutZones = keepouts; ros.updateKeepoutZones(keepouts)
    toast.success(`Map "${map.name}" activated`)
  } catch (err) { setMapError('Activate failed: ' + err.message); toast.error('Activate failed: ' + err.message) }
  finally { activating.value = null }
}

// ── Upload ────────────────────────────────────────────────────────────────────
const fileInputEl    = ref(null)
const isDragging     = ref(false)
const uploading      = ref(false)
const uploadProgress = ref(0)
const uploadFiles    = ref({ yaml: null, pgm: null })

function classifyFiles(files) {
  for (const file of files) {
    if (file.name.endsWith('.yaml')) uploadFiles.value.yaml = file
    else if (file.name.endsWith('.pgm') || file.name.endsWith('.png')) uploadFiles.value.pgm = file
  }
}

function triggerFilePicker() { fileInputEl.value?.click() }
function onFileInput(e) { classifyFiles(Array.from(e.target.files)); e.target.value = '' }
function onDrop(e) { isDragging.value = false; classifyFiles(Array.from(e.dataTransfer.files)) }
function clearFiles() { uploadFiles.value = { yaml: null, pgm: null } }

async function doUpload() {
  if (!uploadFiles.value.yaml || !uploadFiles.value.pgm) return
  uploading.value = true; uploadProgress.value = 10
  const form = new FormData()
  form.append('yaml_file', uploadFiles.value.yaml)
  form.append('pgm_file', uploadFiles.value.pgm)
  try {
    uploadProgress.value = 40
    const newMap = await api.upload('/maps/upload', form)
    uploadProgress.value = 90
    if (!store.maps.find(m => m.id === newMap.id)) store.maps.push(newMap)
    uploadProgress.value = 100
    toast.success(`Map "${newMap.name}" uploaded`)
    clearFiles()
  } catch (err) { toast.error('Upload failed: ' + err.message) }
  finally { uploading.value = false; setTimeout(() => { uploadProgress.value = 0 }, 600) }
}

// ── Keepout Zones ─────────────────────────────────────────────────────────────
async function fetchZones() {
  if (!store.activeMapId) return
  try {
    const zones = await api.get(`/keepout?map_id=${store.activeMapId}`)
    store.keepoutZones = zones; ros.updateKeepoutZones(zones)
  } catch (err) { console.warn('[SetupPanel] fetch zones failed:', err) }
}

onMounted(() => { refresh(); fetchZones() })
watch(() => store.activeMapId, fetchZones)

function startDraw() { setMode('keepout') }

async function removeZone(id) {
  try { await api.del(`/keepout/${id}`) } catch (err) { console.warn('[SetupPanel] keepout delete failed:', err) }
  store.removeKeepoutZone(id); ros.updateKeepoutZones(store.keepoutZones)
}

async function clearAllZones() {
  await Promise.allSettled(store.keepoutZones.map(z => api.del(`/keepout/${z.id}`)))
  store.keepoutZones = []; ros.updateKeepoutZones([])
}
</script>
