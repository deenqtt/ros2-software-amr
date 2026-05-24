<template>
  <div class="h-full flex flex-col gap-0 overflow-y-auto p-3 space-y-3">

    <!-- ── Connection ──────────────────────────────────────────────── -->
    <div class="panel-header"><Wifi :size="13" class="text-amr-accent" /> Connection</div>
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
        {{ store.rosConnected ? 'Disconnect' : 'Connect' }}
      </button>
    </div>

    <!-- ── Status ──────────────────────────────────────────────────── -->
    <div class="bg-slate-800/50 rounded-lg p-2 flex flex-col gap-1.5">
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
      <div class="flex items-center justify-between text-xs mt-1">
        <span class="text-slate-500">Nav</span>
        <span class="font-semibold text-slate-300">{{ store.navStatus.replace(/_/g, ' ').toUpperCase() }}</span>
      </div>
      <div v-if="store.missionRunning" class="flex items-center justify-between text-xs">
        <span class="text-slate-500">Waypoint</span>
        <span>
          <span class="text-white font-medium">{{ store.currentWaypointIndex + 1 }}</span>
          <span class="text-slate-500"> / </span>
          <span class="text-white font-medium">{{ store.waypoints.length }}</span>
        </span>
      </div>
    </div>

    <hr class="border-amr-border" />

    <!-- ── Single-Point Navigation ────────────────────────────────── -->
    <div class="panel-header"><Crosshair :size="13" class="text-amr-accent" /> Navigate To</div>
    <div class="grid grid-cols-3 gap-1.5">
      <div>
        <label class="text-[10px] text-slate-500 uppercase tracking-wider">X (m)</label>
        <input v-model.number="goal.x" type="number" step="0.1" class="input w-full text-sm font-mono mt-0.5" />
      </div>
      <div>
        <label class="text-[10px] text-slate-500 uppercase tracking-wider">Y (m)</label>
        <input v-model.number="goal.y" type="number" step="0.1" class="input w-full text-sm font-mono mt-0.5" />
      </div>
      <div>
        <label class="text-[10px] text-slate-500 uppercase tracking-wider">θ (deg)</label>
        <input v-model.number="goal.thetaDeg" type="number" step="5" class="input w-full text-sm font-mono mt-0.5" @keyup.enter="sendGoal" />
      </div>
    </div>
    <div class="flex gap-1.5">
      <button
        class="btn-primary flex-1 text-sm flex items-center justify-center gap-1.5"
        :disabled="!store.rosConnected || store.isNavigating"
        @click="sendGoal"
      >
        <Target :size="14" /> Send Goal
      </button>
      <button
        class="btn-danger text-sm px-3"
        :disabled="!store.rosConnected || store.isIdle"
        @click="cancelNav"
      >
        Stop
      </button>
    </div>


  </div>
</template>

<script setup>
import { ref, computed, reactive } from 'vue'
import { useRobotStore } from '@/stores/robot'
import { useROS } from '@/composables/useROS'
import { Wifi, Crosshair, Target } from 'lucide-vue-next'

const store = useRobotStore()
const ros   = useROS()
const api   = useAPI()
const toast = useToast()

// ── Connection ────────────────────────────────────────────────────────────────
const rosUrl = ref(store.rosUrl)

function toggleConnection() {
  if (store.rosConnected) {
    ros.disconnect()
  } else {
    store.rosUrl = rosUrl.value
    localStorage.setItem('amr_ros_url', rosUrl.value)
    ros.connect(rosUrl.value)
  }
}

// ── Pose ──────────────────────────────────────────────────────────────────────
const pose = computed(() => ({
  x:     store.robotPose.x.toFixed(2),
  y:     store.robotPose.y.toFixed(2),
  theta: ((store.robotPose.theta * 180) / Math.PI).toFixed(1),
}))

// ── Navigation ────────────────────────────────────────────────────────────────
const goal = reactive({ x: 0, y: 0, thetaDeg: 0 })

function sendGoal() {
  ros.navigateTo(goal.x, goal.y, (goal.thetaDeg * Math.PI) / 180)
}

function cancelNav() {
  ros.cancelNavigation()
}

</script>
