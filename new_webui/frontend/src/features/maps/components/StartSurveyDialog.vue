<script setup lang="ts">
/**
 * Pick the robot that will do the survey.
 *
 * Mapping is not a background task: the robot leaves navigation mode, stops
 * whatever it was doing, and cannot navigate again until a map is loaded. The
 * dialog says which robots are in a state to be asked, and why the others are
 * not, rather than offering a list where half the entries silently fail.
 */
import { computed } from 'vue'
import { Bot } from 'lucide-vue-next'
import { Dialog } from '@/shared/ui/dialog'
import { Button } from '@/shared/ui/button'
import EmptyState from '@/shared/components/EmptyState.vue'
import LinkIndicator from '@/shared/components/LinkIndicator.vue'
import { cn } from '@/shared/lib/utils'
import type { LinkState } from '@/domain/ros/link'
import type { RobotConfig } from '@/domain/types'

const props = defineProps<{
  open: boolean
  robots: RobotConfig[]
  linkFor: (robotId: string) => LinkState
}>()

const emit = defineEmits<{
  'update:open': [value: boolean]
  select: [robotId: string]
}>()

interface Candidate {
  robot: RobotConfig
  link: LinkState
  /** Why this robot cannot be asked, or null when it can. */
  blocked: string | null
}

const candidates = computed<Candidate[]>(() =>
  props.robots.map((robot) => {
    const link = props.linkFor(robot.id)
    let blocked: string | null = null
    if (link === 'muted') blocked = 'Monitoring is muted'
    else if (link === 'offline') blocked = 'No link to this robot'
    else if (link === 'connecting') blocked = 'Still connecting'
    else if (link === 'stale') blocked = 'Telemetry has gone quiet'
    return { robot, link, blocked }
  }),
)

const anyAvailable = computed(() => candidates.value.some((c) => c.blocked === null))
</script>

<template>
  <Dialog
    :open="props.open"
    title="Create a map"
    description="Pick the robot that will drive the survey. It leaves navigation mode and starts SLAM."
    @update:open="emit('update:open', $event)"
  >
    <EmptyState
      v-if="props.robots.length === 0"
      title="No robots registered"
      description="Register a robot before surveying with it."
    />

    <div v-else class="space-y-xs">
      <button
        v-for="candidate in candidates"
        :key="candidate.robot.id"
        type="button"
        :disabled="candidate.blocked !== null"
        :class="
          cn(
            'flex w-full items-center gap-sm rounded-control border px-sm py-xs text-left transition-colors',
            candidate.blocked
              ? 'cursor-not-allowed border-hairline opacity-60'
              : 'border-hairline hover:border-primary',
          )
        "
        @click="emit('select', candidate.robot.id)"
      >
        <span
          class="flex h-7 w-7 shrink-0 items-center justify-center rounded-full text-white"
          :style="{ backgroundColor: `rgb(var(--robot-accent-${candidate.robot.accent}))` }"
        >
          <Bot :size="13" />
        </span>
        <span class="min-w-0 flex-1">
          <span class="block truncate text-body-md text-ink">{{ candidate.robot.name }}</span>
          <span class="block truncate text-caption text-muted">
            {{ candidate.blocked ?? 'Ready to survey' }}
          </span>
        </span>
        <LinkIndicator :state="candidate.link" :show-label="false" />
      </button>

      <p v-if="!anyAvailable" class="text-caption text-muted">
        No robot is reachable right now. A survey needs a live link — the page has to stream the
        map back while the robot drives.
      </p>
    </div>

    <template #footer>
      <Button variant="secondary" size="sm" @click="emit('update:open', false)">Cancel</Button>
    </template>
  </Dialog>
</template>
