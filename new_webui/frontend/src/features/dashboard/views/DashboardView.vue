<script setup lang="ts">
/**
 * The floor, right now.
 *
 * Three bands, in the order somebody arriving actually needs them:
 *
 *   1. What needs a person. Empty most of the time — and that emptiness is the
 *      message. A screen that shows six robots and leaves the operator to work
 *      out which one is in trouble has made them do the scanning.
 *   2. The counts, so "is anything happening" is answered without reading.
 *   3. One row per robot: link, what it should be doing, what it is doing.
 *
 * Nothing here changes a robot's state on load. Opening a page is not a command
 * — see the Mode column, which reports intent and reality as two things.
 */
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { RouterLink } from 'vue-router'
import {
  Activity,
  AlertCircle,
  Ban,
  CheckCircle2,
  Info,
  Play,
  TriangleAlert,
} from 'lucide-vue-next'
import { toast } from 'vue-sonner'
import { useFleetStore } from '@/stores/fleet'
import { useLinkStore } from '@/stores/links'
import { useMissionStore } from '@/stores/missions'
import { useMapStore } from '@/stores/maps'
import { useRosPool } from '@/app/ros/pool'
import { DESIRED_MODE_LABEL, type DesiredMode, type MissionRun } from '@/domain/types'
import { attentionItems, fleetCounts, type AgentSnapshot, type AttentionSeverity } from '../attention'
import { stackSummary, type StackSummary } from '../stackStatus'
import { Card, CardContent } from '@/shared/ui/card'
import { Button } from '@/shared/ui/button'
import { Badge } from '@/shared/ui/badge'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/shared/ui/table'
import PanelToolbar from '@/shared/components/PanelToolbar.vue'
import LinkIndicator from '@/shared/components/LinkIndicator.vue'
import MetricTile from '@/shared/components/MetricTile.vue'
import EmptyState from '@/shared/components/EmptyState.vue'
import StatusBadge from '@/shared/components/StatusBadge.vue'
import { cn } from '@/shared/lib/utils'

const fleet = useFleetStore()
const links = useLinkStore()
const missions = useMissionStore()
const maps = useMapStore()
const pool = useRosPool()

/**
 * The agent's own report, per robot.
 *
 * Read straight from the connection pool rather than through a per-robot
 * telemetry composable: the dashboard needs one field from each robot, and a
 * composable each would open a second subscription to every topic on the fleet.
 */
const agents = ref<Map<string, AgentSnapshot>>(new Map())

function readAgents() {
  const next = new Map<string, AgentSnapshot>()
  for (const robot of fleet.robots) {
    const raw = pool.clientFor(robot.id)?.latest('robotModeStatus') as
      | { data?: string }
      | undefined
    if (!raw?.data) continue
    try {
      const parsed = JSON.parse(raw.data) as Partial<AgentSnapshot>
      next.set(robot.id, {
        mode: String(parsed.mode ?? 'unknown'),
        state: String(parsed.state ?? 'idle'),
        detail: String(parsed.detail ?? ''),
        backend: String(parsed.backend ?? 'unknown'),
      })
    } catch {
      // A malformed status is the same as no status: the robot is saying
      // something this version does not understand, not something alarming.
    }
  }
  agents.value = next
}

const input = computed(() => ({
  robots: fleet.robots,
  linkFor: (id: string) => links.stateFor(id),
  agentFor: (id: string) => agents.value.get(id) ?? null,
  runFor: (id: string) => missions.runForRobot(id),
}))

/**
 * Park a robot, or release it back to navigating.
 *
 * The dashboard used to show a "Parked" icon and nothing else, so a robot that
 * had been parked — which is what the agent leaves behind after a survey — could
 * never be released from anywhere in the UI. Navigation was unreachable.
 *
 * Writing the registry is the whole action: the agent reconciles towards it on
 * its own loop, so this does not wait for Nav2 to come up and does not pretend
 * to know whether it will.
 */
const modePending = ref<string | null>(null)

async function toggleParked(robotId: string, desired: DesiredMode) {
  const next: DesiredMode = desired === 'idle' ? 'nav' : 'idle'
  modePending.value = robotId
  try {
    await fleet.setMode(robotId, next)
    toast.success(next === 'nav' ? 'Released' : 'Parked', {
      description:
        next === 'nav'
          ? 'The robot will start navigating once it has a map.'
          : 'The robot will stop and stay stopped.',
    })
  } catch (error) {
    toast.error('Could not change mode', {
      description: error instanceof Error ? error.message : String(error),
    })
  } finally {
    modePending.value = null
  }
}

const attention = computed(() => attentionItems(input.value))
const counts = computed(() => fleetCounts(input.value, attention.value))

const SEVERITY_STYLE: Record<AttentionSeverity, { icon: typeof Info; class: string }> = {
  fault: { icon: AlertCircle, class: 'text-status-fault' },
  warn: { icon: TriangleAlert, class: 'text-status-warn' },
  info: { icon: Info, class: 'text-muted' },
}

const summary = computed(() => [
  { label: 'Robots', value: String(counts.value.total), unit: `${counts.value.online} online` },
  {
    label: 'Working',
    value: String(counts.value.working),
    unit: counts.value.parked ? `${counts.value.parked} parked` : 'missions running',
  },
  {
    label: 'Needs attention',
    value: String(counts.value.needsAttention),
    unit: counts.value.needsAttention === 0 ? 'all clear' : 'see below',
  },
])

function mapName(id: string | null): string {
  if (!id) return '—'
  const found = maps.byId(id)
  return found ? `${found.name} v${found.version}` : 'unknown map'
}

function stackFor(robotId: string): StackSummary {
  return stackSummary(agents.value.get(robotId) ?? null)
}

/** "Nav2 running", "SLAM starting", "Stopped", "Unknown". */
function stackLabel(summary: StackSummary): string {
  return summary.stack ? `${summary.stack} ${summary.label.toLowerCase()}` : summary.label
}

/** What the robot reports it is doing, as opposed to what it should be doing. */
function actualMode(robotId: string): string {
  const agent = agents.value.get(robotId)
  if (!agent) return '—'
  if (agent.state === 'starting') return 'starting…'
  if (agent.state === 'stopping') return 'stopping…'
  if (agent.state === 'failed') return 'failed'
  if (agent.mode === 'unknown') return 'idle'
  return agent.mode === 'map' ? 'surveying' : 'navigating'
}

/** True when intent and reality disagree, which is what colours the cell. */
function modeDrifted(robotId: string): boolean {
  const robot = fleet.robots.find((r) => r.id === robotId)
  const agent = agents.value.get(robotId)
  if (!robot || !agent || links.stateFor(robotId) !== 'online') return false
  if (agent.state === 'starting' || agent.state === 'stopping') return false
  const expected = robot.desiredMode === 'idle' ? 'unknown' : robot.desiredMode
  return agent.mode !== expected
}

function runLabel(run: MissionRun | null): string {
  if (!run) return 'idle'
  const lap =
    run.mode === 'once' ? '' : run.mode === 'laps' ? ` · lap ${run.lap}/${run.lapsTarget}` : ` · lap ${run.lap}`
  return `${run.missionName} · step ${run.stepIndex + 1}${lap}`
}

// ── Polling ──────────────────────────────────────────────────────────────────
//
// Runs are written by each robot's agent, so the only way to see progress move
// is to ask. The agent status arrives over ROS and is only read here.

let poll: ReturnType<typeof setInterval> | null = null

onMounted(async () => {
  await Promise.all([fleet.load(), maps.load()])
  await missions.refreshRuns()
  readAgents()
  poll = setInterval(() => {
    readAgents()
    void missions.refreshRuns()
  }, 2000)
})

onBeforeUnmount(() => {
  if (poll !== null) clearInterval(poll)
})

// A robot added or removed elsewhere changes what has to be read.
watch(() => fleet.count, readAgents)
</script>

<template>
  <div class="space-y-base p-lg">
    <!--
      Attention first. Anything below it is context for a floor that is fine;
      this is the part that is read when it is not.
    -->
    <Card v-if="attention.length">
      <PanelToolbar
        title="Needs attention"
        :subtitle="`${counts.needsAttention} robot${counts.needsAttention === 1 ? '' : 's'}`"
      >
        <template #icon><TriangleAlert :size="14" class="shrink-0 text-status-warn" /></template>
      </PanelToolbar>
      <CardContent class="space-y-xs">
        <div
          v-for="item in attention"
          :key="item.key"
          class="flex items-start gap-sm rounded-control border border-hairline p-sm"
        >
          <component
            :is="SEVERITY_STYLE[item.severity].icon"
            :size="15"
            :class="cn('mt-px shrink-0', SEVERITY_STYLE[item.severity].class)"
          />
          <div class="min-w-0 flex-1">
            <p class="text-body-md text-ink">
              <span class="font-medium">{{ item.robotName }}</span>
              — {{ item.title }}
            </p>
            <p v-if="item.action" class="text-caption text-muted">{{ item.action }}</p>
          </div>
          <Button variant="ghost" size="sm" as-child>
            <RouterLink :to="`/robot/${item.robotId}/nav`">Open navigation</RouterLink>
          </Button>
        </div>
      </CardContent>
    </Card>

    <div class="grid gap-sm sm:grid-cols-3">
      <MetricTile
        v-for="item in summary"
        :key="item.label"
        :label="item.label"
        :value="item.value"
        :unit="item.unit"
        size="lg"
      />
    </div>

    <Card>
      <PanelToolbar title="Fleet" :subtitle="`${counts.total} registered`">
        <template #icon><Activity :size="14" class="shrink-0 text-muted" /></template>
        <template #actions>
          <Button variant="ghost" size="sm" as-child>
            <RouterLink to="/robot">Manage robots</RouterLink>
          </Button>
        </template>
      </PanelToolbar>

      <CardContent>
        <EmptyState
          v-if="!fleet.count && !fleet.loading"
          title="No robots registered"
          description="Register a robot and assign it a map. It starts navigating on its own — there is no button to press."
        >
          <template #action>
            <Button size="sm" as-child>
              <RouterLink to="/robot">Add a robot</RouterLink>
            </Button>
          </template>
        </EmptyState>

        <template v-else>
          <!--
            A table from 1024px up — the sidebar takes ~230px, so below that the
            content area is too narrow for one. The robot's name is the row's primary link,
            so the most used action sits in the first column — not past a
            horizontal scroll at the far right. When the table is still wider
            than the screen, the name and the actions stay pinned at the edges
            and only the columns between them scroll.
          -->
          <div class="hidden lg:block">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead class="sticky left-0 z-[1] bg-surface">Robot</TableHead>
                  <TableHead>Link</TableHead>
                  <TableHead class="hidden xl:table-cell">Mode</TableHead>
                  <TableHead>Stack</TableHead>
                  <TableHead class="hidden xl:table-cell">Map</TableHead>
                  <TableHead class="w-full min-w-[9rem]">Doing</TableHead>
                  <TableHead align="right" class="sticky right-0 z-[1] bg-surface">Actions</TableHead>
                </TableRow>
              </TableHeader>

              <TableBody>
                <TableRow v-for="robot in fleet.robots" :key="robot.id" interactive>
                  <TableCell
                    class="sticky left-0 z-[1] bg-surface transition-colors group-hover:bg-surface-soft"
                  >
                    <RouterLink
                      :to="`/robot/${robot.id}/nav`"
                      class="flex items-center gap-sm whitespace-nowrap text-body-md font-medium text-ink hover:text-primary hover:underline"
                      :title="`Open ${robot.name} navigation`"
                    >
                      <span
                        class="h-2.5 w-2.5 shrink-0 rounded-full"
                        :style="{ backgroundColor: `rgb(var(--robot-accent-${robot.accent}))` }"
                      />
                      {{ robot.name }}
                    </RouterLink>
                  </TableCell>

                  <TableCell>
                    <LinkIndicator
                      :state="links.stateFor(robot.id)"
                      :attempt="links.linkFor(robot.id).attempt"
                    />
                  </TableCell>

                  <!--
                    Intent and reality, side by side. They are two different
                    things, and the whole point of recording intent was that
                    nothing used to notice when they parted company.
                  -->
                  <TableCell class="hidden xl:table-cell">
                    <div class="flex items-center gap-xxs whitespace-nowrap">
                      <Badge
                        :class="
                          robot.desiredMode === 'idle'
                            ? 'bg-surface-strong text-muted'
                            : 'bg-surface-strong text-body'
                        "
                      >
                        {{ DESIRED_MODE_LABEL[robot.desiredMode] }}
                      </Badge>
                      <span
                        class="font-data text-caption"
                        :class="modeDrifted(robot.id) ? 'text-status-warn' : 'text-muted-soft'"
                      >
                        {{ actualMode(robot.id) }}
                      </span>
                    </div>
                  </TableCell>

                  <TableCell>
                    <span class="whitespace-nowrap" :title="stackFor(robot.id).detail">
                      <StatusBadge
                        :tone="stackFor(robot.id).tone"
                        :label="stackLabel(stackFor(robot.id))"
                      />
                    </span>
                  </TableCell>

                  <TableCell class="hidden xl:table-cell">
                    <span
                      class="whitespace-nowrap text-body-sm"
                      :class="robot.activeMapId ? 'text-body' : 'text-status-warn'"
                    >
                      {{ mapName(robot.activeMapId) }}
                    </span>
                  </TableCell>

                  <TableCell class="w-full min-w-[9rem] max-w-0">
                    <div class="flex min-w-0 items-center gap-xs">
                      <component
                        :is="missions.runForRobot(robot.id) ? Play : CheckCircle2"
                        :size="13"
                        :class="
                          missions.runForRobot(robot.id)
                            ? 'shrink-0 text-status-run'
                            : 'shrink-0 text-muted-soft'
                        "
                      />
                      <span
                        class="truncate text-body-sm text-body"
                        :title="runLabel(missions.runForRobot(robot.id))"
                      >
                        {{ runLabel(missions.runForRobot(robot.id)) }}
                      </span>
                    </div>
                  </TableCell>

                  <TableCell
                    align="right"
                    class="sticky right-0 z-[1] bg-surface transition-colors group-hover:bg-surface-soft"
                  >
                    <div class="flex justify-end gap-xxs whitespace-nowrap">
                      <Button
                        v-if="robot.desiredMode !== 'map'"
                        variant="ghost"
                        size="sm"
                        :disabled="modePending === robot.id"
                        :title="
                          robot.desiredMode === 'idle'
                            ? 'Parked — will not start navigation. Release it.'
                            : 'Stop navigating and stay stopped.'
                        "
                        @click="toggleParked(robot.id, robot.desiredMode)"
                      >
                        <Ban
                          v-if="robot.desiredMode === 'idle'"
                          :size="13"
                          class="mr-xxs text-muted-soft"
                        />
                        {{ robot.desiredMode === 'idle' ? 'Release' : 'Park' }}
                      </Button>
                      <Button variant="ghost" size="sm" as-child>
                        <RouterLink :to="`/robot/${robot.id}/nav`">Navigation</RouterLink>
                      </Button>
                    </div>
                  </TableCell>
                </TableRow>
              </TableBody>
            </Table>
          </div>

          <!--
            One card per robot below 1024px. A narrow screen does not fit seven columns,
            and a table it has to be dragged sideways to use is not usable at all.
            Everything an operator acts on stays visible on the card.
          -->
          <ul class="grid gap-sm sm:grid-cols-2 lg:hidden">
            <li
              v-for="robot in fleet.robots"
              :key="robot.id"
              class="rounded-control border border-hairline p-sm"
            >
              <div class="flex items-center justify-between gap-sm">
                <RouterLink
                  :to="`/robot/${robot.id}/nav`"
                  class="flex min-w-0 items-center gap-sm text-body-md font-medium text-ink hover:text-primary"
                >
                  <span
                    class="h-2.5 w-2.5 shrink-0 rounded-full"
                    :style="{ backgroundColor: `rgb(var(--robot-accent-${robot.accent}))` }"
                  />
                  <span class="truncate">{{ robot.name }}</span>
                </RouterLink>
                <LinkIndicator
                  :state="links.stateFor(robot.id)"
                  :attempt="links.linkFor(robot.id).attempt"
                />
              </div>

              <div class="mt-xs flex flex-wrap items-center gap-xs">
                <Badge class="bg-surface-strong text-body">
                  {{ DESIRED_MODE_LABEL[robot.desiredMode] }}
                </Badge>
                <span :title="stackFor(robot.id).detail">
                  <StatusBadge
                    :tone="stackFor(robot.id).tone"
                    :label="stackLabel(stackFor(robot.id))"
                  />
                </span>
                <span
                  class="text-caption"
                  :class="robot.activeMapId ? 'text-muted' : 'text-status-warn'"
                >
                  {{ mapName(robot.activeMapId) }}
                </span>
              </div>

              <p class="mt-xs flex min-w-0 items-center gap-xs text-body-sm text-body">
                <component
                  :is="missions.runForRobot(robot.id) ? Play : CheckCircle2"
                  :size="13"
                  :class="
                    missions.runForRobot(robot.id) ? 'shrink-0 text-status-run' : 'shrink-0 text-muted-soft'
                  "
                />
                <span class="truncate">{{ runLabel(missions.runForRobot(robot.id)) }}</span>
              </p>

              <div class="mt-sm flex gap-xs">
                <Button
                  v-if="robot.desiredMode !== 'map'"
                  variant="outline"
                  size="sm"
                  class="flex-1"
                  :disabled="modePending === robot.id"
                  @click="toggleParked(robot.id, robot.desiredMode)"
                >
                  {{ robot.desiredMode === 'idle' ? 'Release' : 'Park' }}
                </Button>
                <Button size="sm" class="flex-1" as-child>
                  <RouterLink :to="`/robot/${robot.id}/nav`">Navigation</RouterLink>
                </Button>
              </div>
            </li>
          </ul>
        </template>
      </CardContent>
    </Card>
  </div>
</template>
