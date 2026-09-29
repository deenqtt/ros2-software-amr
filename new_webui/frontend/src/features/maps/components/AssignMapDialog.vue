<script setup lang="ts">
/**
 * Assign a map to robots.
 *
 * Per robot, not global. Robots in one building normally share a map — they
 * have to, or a station at (12.4, 3.1) names a different physical place for
 * each of them — but one being re-surveyed while another keeps working is
 * exactly what a single global setting cannot express.
 *
 * Assigning does not move the robot. Its agent notices the change, compares
 * the map's content hash against its local cache, downloads if needed, and
 * loads it the next time it is in navigation mode.
 */
import { computed, ref, watch } from 'vue'
import { Bot, Check } from 'lucide-vue-next'
import { Dialog } from '@/shared/ui/dialog'
import { Button } from '@/shared/ui/button'
import EmptyState from '@/shared/components/EmptyState.vue'
import { cn } from '@/shared/lib/utils'
import type { MapRecord, RobotConfig } from '@/domain/types'

const props = withDefaults(
  defineProps<{
    open: boolean
    map: MapRecord | null
    robots: RobotConfig[]
    pending?: boolean
    serverError?: string | null
  }>(),
  { pending: false, serverError: null },
)

const emit = defineEmits<{
  'update:open': [value: boolean]
  submit: [robotIds: string[]]
}>()

const selected = ref<Set<string>>(new Set())

watch(
  () => [props.open, props.map?.id] as const,
  ([open]) => {
    if (!open) return
    // Pre-tick the robots already on this map, so the dialog opens showing the
    // current state rather than an empty form that implies nothing is assigned.
    selected.value = new Set(
      props.robots.filter((r) => r.activeMapId === props.map?.id).map((r) => r.id),
    )
  },
  { immediate: true },
)

function toggle(robotId: string) {
  const next = new Set(selected.value)
  if (next.has(robotId)) next.delete(robotId)
  else next.add(robotId)
  selected.value = next
}

/** Robots whose assignment this dialog would actually change. */
const changes = computed(() => {
  const mapId = props.map?.id
  return props.robots.filter((robot) => {
    const wasAssigned = robot.activeMapId === mapId
    const willBeAssigned = selected.value.has(robot.id)
    return wasAssigned !== willBeAssigned
  })
})

const movingOffAnother = computed(() =>
  props.robots.filter(
    (robot) =>
      selected.value.has(robot.id) &&
      robot.activeMapId !== null &&
      robot.activeMapId !== props.map?.id,
  ),
)
</script>

<template>
  <Dialog
    :open="props.open"
    :pending="props.pending"
    :title="props.map ? `Assign ${props.map.name} v${props.map.version}` : 'Assign map'"
    description="Pick the robots that should run this map. Their agents fetch it and load it when next in navigation mode."
    @update:open="emit('update:open', $event)"
  >
    <EmptyState
      v-if="props.robots.length === 0"
      title="No robots registered"
      description="Register a robot before assigning a map to it."
    />

    <div v-else class="space-y-xs">
      <button
        v-for="robot in props.robots"
        :key="robot.id"
        type="button"
        :class="
          cn(
            'flex w-full items-center gap-sm rounded-control border px-sm py-xs text-left transition-colors',
            selected.has(robot.id)
              ? 'border-primary bg-primary/5'
              : 'border-hairline hover:border-muted',
          )
        "
        :aria-pressed="selected.has(robot.id)"
        @click="toggle(robot.id)"
      >
        <span
          class="flex h-7 w-7 shrink-0 items-center justify-center rounded-full text-white"
          :style="{ backgroundColor: `rgb(var(--robot-accent-${robot.accent}))` }"
        >
          <Bot :size="13" />
        </span>
        <span class="min-w-0 flex-1">
          <span class="block truncate text-body-md text-ink">{{ robot.name }}</span>
          <span class="block truncate text-caption text-muted">
            {{
              robot.activeMapId === null
                ? 'No map assigned'
                : robot.activeMapId === props.map?.id
                  ? 'Already on this map'
                  : 'On another map'
            }}
          </span>
        </span>
        <Check v-if="selected.has(robot.id)" :size="15" class="shrink-0 text-primary" />
      </button>

      <!-- Moving a robot between maps changes the frame its stations are in,
           which is not obvious from a checkbox. -->
      <p
        v-if="movingOffAnother.length"
        class="rounded-control bg-status-warn/10 px-sm py-xs text-caption text-status-warn"
      >
        {{ movingOffAnother.map((r) => r.name).join(', ') }}
        {{ movingOffAnother.length === 1 ? 'is' : 'are' }} currently on another map. Moving between
        maps changes the frame their stations are expressed in.
      </p>

      <p
        v-if="props.serverError"
        class="rounded-control border border-status-fault/40 bg-status-fault/10 px-sm py-xs text-body-sm text-status-fault"
        role="alert"
      >
        {{ props.serverError }}
      </p>
    </div>

    <template #footer>
      <Button variant="secondary" size="sm" :disabled="props.pending" @click="emit('update:open', false)">
        Cancel
      </Button>
      <Button
        size="sm"
        :disabled="props.pending || changes.length === 0"
        @click="emit('submit', [...selected])"
      >
        {{
          props.pending
            ? 'Saving…'
            : changes.length === 0
              ? 'No changes'
              : `Apply to ${changes.length} robot${changes.length === 1 ? '' : 's'}`
        }}
      </Button>
    </template>
  </Dialog>
</template>
