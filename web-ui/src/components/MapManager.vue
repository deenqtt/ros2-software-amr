<template>
  <div class="panel p-3 flex flex-col gap-3">
    <div class="flex items-center justify-between">
      <div class="panel-header"><Map :size="14" class="text-amr-accent" /> Map Management</div>
      <button class="btn-ghost text-xs px-2 py-1" :disabled="loading" @click="refresh">
        {{ loading ? '…' : 'Refresh' }}
      </button>
    </div>

    <div v-if="error" class="text-xs text-red-400 bg-red-900/20 rounded px-2 py-1">
      {{ error }}
    </div>

    <!-- Map list -->
    <div class="flex flex-col gap-1 max-h-48 overflow-y-auto">
      <div
        v-if="!loading && store.maps.length === 0"
        class="text-xs text-slate-500 text-center py-4"
      >
        Belum ada map. Upload map di bawah.
      </div>

      <div
        v-for="map in store.maps"
        :key="map.id"
        class="flex items-center gap-2 bg-slate-800 rounded px-2 py-2 group"
        :class="{ 'ring-1 ring-cyan-600 bg-cyan-950/30': store.activeMapId === map.id }"
      >
        <!-- Active indicator dot -->
        <div
          class="w-2 h-2 rounded-full shrink-0"
          :class="store.activeMapId === map.id ? 'bg-cyan-400' : 'bg-slate-600'"
        />

        <!-- Info -->
        <div class="flex-1 min-w-0">
          <div class="text-xs text-slate-200 truncate font-medium">{{ map.name }}</div>
          <div class="text-xs text-slate-500 font-mono truncate">
            {{ map.yaml_file }}
            <span v-if="map.resolution"> · {{ map.resolution }}m/px</span>
            <span v-if="map.width"> · {{ map.width }}×{{ map.height }}</span>
          </div>
        </div>

        <!-- Activate button -->
        <button
          class="text-xs px-2 py-0.5 rounded shrink-0 transition-colors"
          :class="store.activeMapId === map.id
            ? 'bg-cyan-800/60 text-cyan-300 cursor-default'
            : 'btn-ghost hover:bg-cyan-800/60 hover:text-cyan-300'"
          :disabled="activating === map.id || store.activeMapId === map.id"
          @click="activateMap(map)"
        >
          {{ store.activeMapId === map.id ? 'Active' : (activating === map.id ? '…' : 'Activate') }}
        </button>
      </div>
    </div>

    <hr class="border-amr-border" />

    <!-- Upload map -->
    <div class="flex flex-col gap-2">
      <div class="panel-header"><Upload :size="13" class="text-amr-accent" /> Upload Map</div>

      <!-- Drop zone -->
      <div
        class="border-2 border-dashed rounded-lg p-3 text-center cursor-pointer transition-colors"
        :class="isDragging
          ? 'border-cyan-500 bg-cyan-950/20'
          : 'border-amr-border hover:border-slate-500'"
        @dragover.prevent="isDragging = true"
        @dragleave="isDragging = false"
        @drop.prevent="onDrop"
        @click="triggerFilePicker"
      >
        <div class="text-xs text-slate-400 flex flex-col items-center gap-1">
          <Upload :size="18" class="text-slate-500" />
          <span v-if="!uploadFiles.yaml && !uploadFiles.pgm">
            Drop <code>.yaml</code> + <code>.pgm</code> atau klik untuk pilih
          </span>
          <span v-else class="text-left w-full space-y-0.5">
            <div class="flex items-center gap-1" :class="uploadFiles.yaml ? 'text-cyan-400' : 'text-slate-500'">
              <CheckCircle v-if="uploadFiles.yaml" :size="12" />
              <span v-else class="w-3 h-3 rounded-full border border-slate-600 inline-block" />
              {{ uploadFiles.yaml?.name ?? '.yaml — belum dipilih' }}
            </div>
            <div class="flex items-center gap-1" :class="uploadFiles.pgm ? 'text-cyan-400' : 'text-slate-500'">
              <CheckCircle v-if="uploadFiles.pgm" :size="12" />
              <span v-else class="w-3 h-3 rounded-full border border-slate-600 inline-block" />
              {{ uploadFiles.pgm?.name ?? '.pgm/.png — belum dipilih' }}
            </div>
          </span>
        </div>
        <!-- Hidden file input -->
        <input
          ref="fileInputEl"
          type="file"
          multiple
          accept=".yaml,.pgm,.png"
          class="hidden"
          @change="onFileInput"
        />
      </div>

      <!-- Upload progress bar -->
      <div v-if="uploading" class="w-full bg-slate-700 rounded-full h-1.5">
        <div
          class="bg-cyan-500 h-1.5 rounded-full transition-all duration-300"
          :style="{ width: uploadProgress + '%' }"
        />
      </div>

      <!-- Upload button -->
      <button
        class="btn-primary w-full text-sm flex items-center justify-center gap-2"
        :disabled="!uploadFiles.yaml || !uploadFiles.pgm || uploading"
        @click="doUpload"
      >
        <Upload v-if="!uploading" :size="14" />
        <span v-if="uploading" class="animate-spin text-base">⟳</span>
        {{ uploading ? 'Uploading…' : 'Upload Map' }}
      </button>

      <!-- Clear selection -->
      <button
        v-if="uploadFiles.yaml || uploadFiles.pgm"
        class="text-xs text-slate-500 hover:text-slate-300 text-center transition-colors"
        @click="clearFiles"
      >
        Batal pilihan
      </button>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useRobotStore } from '@/stores/robot'
import { useAPI } from '@/composables/useAPI'
import { useROS } from '@/composables/useROS'
import { useToast } from '@/composables/useToast'
import { Map, Upload, CheckCircle } from 'lucide-vue-next'

const store = useRobotStore()
const api   = useAPI()
const ros   = useROS()
const toast = useToast()

const loading   = ref(false)
const error     = ref('')
const activating = ref(null)

// Upload state
const fileInputEl    = ref(null)
const isDragging     = ref(false)
const uploading      = ref(false)
const uploadProgress = ref(0)
const uploadFiles    = ref({ yaml: null, pgm: null })

// ── Error helper ─────────────────────────────────────────────────────────────
let _errorTimer = null
function setError(msg) {
  error.value = msg
  if (_errorTimer) clearTimeout(_errorTimer)
  if (msg) _errorTimer = setTimeout(() => { error.value = '' }, 5000)
}

// ── Map list ─────────────────────────────────────────────────────────────────
async function refresh() {
  loading.value = true
  setError('')
  try {
    store.setMaps(await api.get('/maps'))
  } catch (err) {
    setError('Backend tidak tersedia: ' + err.message)
  } finally {
    loading.value = false
  }
}

async function activateMap(map) {
  activating.value = map.id
  setError('')
  try {
    const result = await api.post(`/maps/${map.id}/activate`, {})
    store.setActiveMap(map.id)
    ros.loadMap(result.yaml_path)

    const [keepouts] = await Promise.all([
      api.get(`/keepout?map_id=${map.id}`),
      api.get(`/docks?map_id=${map.id}`),
    ])
    store.keepoutZones = keepouts
    ros.updateKeepoutZones(keepouts)
    toast.success(`Map "${map.name}" activated`)
  } catch (err) {
    setError('Activate gagal: ' + err.message)
    toast.error('Activate gagal: ' + err.message)
  } finally {
    activating.value = null
  }
}

// ── Upload helpers ────────────────────────────────────────────────────────────
function classifyFiles(files) {
  for (const file of files) {
    if (file.name.endsWith('.yaml')) uploadFiles.value.yaml = file
    else if (file.name.endsWith('.pgm') || file.name.endsWith('.png')) uploadFiles.value.pgm = file
  }
}

function triggerFilePicker() {
  fileInputEl.value?.click()
}

function onFileInput(e) {
  classifyFiles(Array.from(e.target.files))
  e.target.value = '' // reset so same file can be re-selected
}

function onDrop(e) {
  isDragging.value = false
  classifyFiles(Array.from(e.dataTransfer.files))
}

function clearFiles() {
  uploadFiles.value = { yaml: null, pgm: null }
}

async function doUpload() {
  if (!uploadFiles.value.yaml || !uploadFiles.value.pgm) return
  uploading.value = true
  uploadProgress.value = 10

  const form = new FormData()
  form.append('yaml_file', uploadFiles.value.yaml)
  form.append('pgm_file',  uploadFiles.value.pgm)

  try {
    uploadProgress.value = 40
    const newMap = await api.upload('/maps/upload', form)
    uploadProgress.value = 90
    // Add to store if not already listed
    if (!store.maps.find((m) => m.id === newMap.id)) {
      store.maps.push(newMap)
    }
    uploadProgress.value = 100
    toast.success(`Map "${newMap.name}" berhasil diupload`)
    clearFiles()
  } catch (err) {
    toast.error('Upload gagal: ' + err.message)
  } finally {
    uploading.value = false
    setTimeout(() => { uploadProgress.value = 0 }, 600)
  }
}

onMounted(refresh)
</script>
