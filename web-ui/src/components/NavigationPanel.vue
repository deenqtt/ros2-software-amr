<template>
  <div class="panel p-3 flex flex-col gap-3">
    <!-- Header -->
    <div class="panel-header">
      <Crosshair :size="14" class="text-amr-accent" /> Single-Point Navigation
    </div>

    <!-- Coordinate inputs -->
    <div class="grid grid-cols-3 gap-1.5">
      <div>
        <label class="text-[10px] text-slate-500 uppercase tracking-wider"
          >X (m)</label
        >
        <input
          v-model.number="goal.x"
          type="number"
          step="0.1"
          class="input w-full text-sm font-mono mt-0.5"
        />
      </div>
      <div>
        <label class="text-[10px] text-slate-500 uppercase tracking-wider"
          >Y (m)</label
        >
        <input
          v-model.number="goal.y"
          type="number"
          step="0.1"
          class="input w-full text-sm font-mono mt-0.5"
        />
      </div>
      <div>
        <label class="text-[10px] text-slate-500 uppercase tracking-wider"
          >θ (deg)</label
        >
        <input
          v-model.number="goal.thetaDeg"
          type="number"
          step="5"
          class="input w-full text-sm font-mono mt-0.5"
          @keyup.enter="sendGoal"
        />
      </div>
    </div>

    <button
      class="btn-primary w-full text-sm flex items-center justify-center gap-2"
      :disabled="!store.rosConnected || store.isNavigating"
      @click="sendGoal"
    >
      <Target :size="15" /> Send Goal
    </button>

    <div class="flex items-center justify-between">
      <span class="text-[10px] text-slate-500"
        >Or click map in Navigate mode</span
      >
      <button
        class="btn-danger text-xs px-2 py-1"
        :disabled="!store.rosConnected || store.isIdle"
        @click="cancel"
      >
        Stop
      </button>
    </div>

    <hr class="border-amr-border" />

    <!-- AMCL initial pose -->
    <div class="panel-header">
      <LocateFixed :size="14" class="text-amr-accent" /> AMCL Initial Pose
    </div>

    <div class="grid grid-cols-3 gap-1.5">
      <div>
        <label class="text-[10px] text-slate-500 uppercase tracking-wider"
          >X</label
        >
        <input
          v-model.number="initPose.x"
          type="number"
          step="0.1"
          class="input w-full text-sm font-mono mt-0.5"
        />
      </div>
      <div>
        <label class="text-[10px] text-slate-500 uppercase tracking-wider"
          >Y</label
        >
        <input
          v-model.number="initPose.y"
          type="number"
          step="0.1"
          class="input w-full text-sm font-mono mt-0.5"
        />
      </div>
      <div>
        <label class="text-[10px] text-slate-500 uppercase tracking-wider"
          >θ (deg)</label
        >
        <input
          v-model.number="initPose.thetaDeg"
          type="number"
          step="5"
          class="input w-full text-sm font-mono mt-0.5"
          @keyup.enter="setInitPose"
        />
      </div>
    </div>

    <button
      class="btn-ghost text-xs w-full"
      :disabled="!store.rosConnected"
      @click="setInitPose"
    >
      Set Initial Pose
    </button>
  </div>
</template>

<script setup>
import { reactive } from "vue";
import { useRobotStore } from "@/stores/robot";
import { useROS } from "@/composables/useROS";
import { Crosshair, LocateFixed, Target } from "lucide-vue-next";

const store = useRobotStore();
const ros = useROS();

const goal = reactive({ x: 0, y: 0, thetaDeg: 0 });
const initPose = reactive({ x: 0, y: 0, thetaDeg: 0 });

function sendGoal() {
  ros.navigateTo(goal.x, goal.y, (goal.thetaDeg * Math.PI) / 180);
}

function cancel() {
  ros.cancelNavigation();
}

function setInitPose() {
  ros.setInitialPose(
    initPose.x,
    initPose.y,
    (initPose.thetaDeg * Math.PI) / 180,
  );
}
</script>
