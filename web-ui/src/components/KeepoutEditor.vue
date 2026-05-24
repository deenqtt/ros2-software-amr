<template>
  <div class="panel p-3 flex flex-col gap-3">
    <!-- Header -->
    <div class="panel-header">
      <ShieldOff :size="14" class="text-amr-warning" /> Keepout Zones
    </div>

    <!-- Draw button -->
    <button
      class="btn-warning w-full text-sm flex items-center justify-center gap-2"
      @click="startDraw"
    >
      <Pencil :size="14" /> Draw New Zone
    </button>

    <!-- Zone list -->
    <div class="flex flex-col gap-1 max-h-40 overflow-y-auto">
      <div
        v-if="store.keepoutZones.length === 0"
        class="text-xs text-slate-500 text-center py-3"
      >
        No keepout zones defined.
      </div>

      <div
        v-for="zone in store.keepoutZones"
        :key="zone.id"
        class="flex items-center gap-2 bg-slate-800/60 rounded px-2 py-1.5 group"
      >
        <div class="w-2.5 h-2.5 rounded-sm bg-amber-500 shrink-0" />
        <span class="flex-1 text-xs text-slate-200 truncate">{{ zone.name }}</span>
        <span class="text-[10px] text-slate-500 shrink-0">{{ zone.polygon.length }} vertices</span>
        <button
          class="text-red-400 hover:text-red-300 px-1 opacity-0 group-hover:opacity-100 transition-opacity flex items-center"
          @click="removeZone(zone.id)"
        ><X :size="13" /></button>
      </div>
    </div>

    <!-- Clear all -->
    <button
      v-if="store.keepoutZones.length > 0"
      class="btn-ghost text-xs w-full"
      @click="clearAll"
    >
      Clear All Zones
    </button>
  </div>
</template>

<script setup>
import { onMounted, watch } from 'vue'
import { useRobotStore } from '@/stores/robot'
import { useROS } from '@/composables/useROS'
import { useAPI } from '@/composables/useAPI'
import { useMapMode } from '@/composables/useMapMode'
import { ShieldOff, Pencil, X } from 'lucide-vue-next'

const store = useRobotStore()
const ros = useROS()
const api = useAPI()
const { setMode } = useMapMode()

async function fetchZones() {
  if (!store.activeMapId) return
  try {
    const zones = await api.get(`/keepout?map_id=${store.activeMapId}`)
    store.keepoutZones = zones
    ros.updateKeepoutZones(zones)
  } catch (err) {
    console.warn('[KeepoutEditor] fetch failed:', err)
  }
}

onMounted(fetchZones)
watch(() => store.activeMapId, fetchZones)

function startDraw() {
  setMode('keepout')
}

async function removeZone(id) {
  try {
    await api.del(`/keepout/${id}`)
  } catch (err) {
    console.warn('[KeepoutEditor] delete failed:', err)
  }
  store.removeKeepoutZone(id)
  ros.updateKeepoutZones(store.keepoutZones)
}

async function clearAll() {
  const ids = store.keepoutZones.map((z) => z.id)
  await Promise.allSettled(ids.map((id) => api.del(`/keepout/${id}`)))
  store.keepoutZones = []
  ros.updateKeepoutZones([])
}
</script>
