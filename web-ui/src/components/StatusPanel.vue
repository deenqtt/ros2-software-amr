<template>
  <div class="panel p-3 flex flex-col gap-3">
    <!-- Header -->
    <div class="panel-header">
      <Zap :size="14" class="text-amr-accent" /> Robot Status
    </div>

    <!-- Connection row -->
    <div class="flex items-center justify-between text-xs">
      <span class="text-slate-400">Connection</span>
      <span
        class="font-semibold flex items-center gap-1"
        :class="store.rosConnected ? 'text-cyan-400' : 'text-red-400'"
      >
        <Wifi v-if="store.rosConnected" :size="13" />
        <WifiOff v-else :size="13" />
        {{ store.rosConnected ? 'CONNECTED' : 'DISCONNECTED' }}
      </span>
    </div>

    <!-- Navigation status row -->
    <div class="flex items-center justify-between text-xs">
      <span class="text-slate-400">Navigation</span>
      <span class="font-semibold flex items-center gap-1 text-slate-300">
        <Navigation :size="13" />
        {{ store.navStatus.replace(/_/g, ' ').toUpperCase() }}
      </span>
    </div>

    <!-- Position -->
    <div class="bg-slate-800/50 rounded-lg p-2 flex flex-col gap-1.5">
      <div class="text-[10px] text-slate-500 uppercase tracking-widest">Position</div>
      <div class="grid grid-cols-3 gap-2">
        <div>
          <div class="text-[10px] text-slate-500">X</div>
          <div class="text-sm font-mono font-semibold text-cyan-400">{{ pose.x }}m</div>
        </div>
        <div>
          <div class="text-[10px] text-slate-500">Y</div>
          <div class="text-sm font-mono font-semibold text-cyan-400">{{ pose.y }}m</div>
        </div>
        <div>
          <div class="text-[10px] text-slate-500">θ</div>
          <div class="text-sm font-mono font-semibold text-cyan-400">{{ pose.theta }}°</div>
        </div>
      </div>
    </div>

    <!-- Mission progress -->
    <div v-if="store.missionRunning" class="text-xs text-slate-400 flex items-center justify-between">
      <span>Waypoint</span>
      <span>
        <span class="text-white font-medium">{{ store.currentWaypointIndex + 1 }}</span>
        <span class="text-slate-500"> / </span>
        <span class="text-white font-medium">{{ store.waypoints.length }}</span>
        <span v-if="store.missionLoop" class="text-slate-500 ml-1">
          · {{ store.missionLoopCount > 0 ? store.missionLoopCount + 'x' : '∞' }}
        </span>
      </span>
    </div>

    <hr class="border-amr-border" />

    <!-- ROS URL + connect/disconnect -->
    <div class="flex gap-1.5">
      <input
        v-model="rosUrl"
        class="input flex-1 text-xs font-mono"
        placeholder="ws://localhost:8765"
        @keyup.enter="toggleConnection"
      />
      <button
        class="btn text-xs px-2 py-1"
        :class="store.rosConnected ? 'btn-danger' : 'btn-success'"
        @click="toggleConnection"
      >
        {{ store.rosConnected ? 'Disc.' : 'Connect' }}
      </button>
    </div>

    <hr class="border-amr-border" />

    <!-- Map save -->
    <div>
      <div class="text-[10px] text-slate-500 uppercase tracking-widest mb-1.5">Save Map</div>
      <div class="flex gap-1.5">
        <input
          v-model="mapFilename"
          class="input flex-1 text-xs font-mono"
          placeholder="amr_map"
        />
        <button
          class="btn-primary text-xs px-2 py-1"
          :disabled="!store.rosConnected || !store.hasMap || savingMap"
          @click="saveMap"
        >
          {{ savingMap ? '...' : 'Save' }}
        </button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'
import { useRobotStore } from '@/stores/robot'
import { useROS } from '@/composables/useROS'
import { useToast } from '@/composables/useToast'
import { Zap, Wifi, WifiOff, Navigation } from 'lucide-vue-next'

const store = useRobotStore()
const ros   = useROS()
const toast = useToast()

const rosUrl     = ref(store.rosUrl)
const mapFilename = ref('amr_map')
const savingMap  = ref(false)

const pose = computed(() => ({
  x:     store.robotPose.x.toFixed(2),
  y:     store.robotPose.y.toFixed(2),
  theta: ((store.robotPose.theta * 180) / Math.PI).toFixed(1),
}))

function toggleConnection() {
  if (store.rosConnected) {
    ros.disconnect()
  } else {
    store.rosUrl = rosUrl.value
    localStorage.setItem('amr_ros_url', rosUrl.value)
    ros.connect(rosUrl.value)
  }
}

function saveMap() {
  savingMap.value = true
  ros.saveMap(mapFilename.value, {
    onSuccess: () => { savingMap.value = false; toast.success(`Map saved: ${mapFilename.value}`) },
    onError:   (err) => { savingMap.value = false; toast.error('Map save failed: ' + err) },
  })
}
</script>
