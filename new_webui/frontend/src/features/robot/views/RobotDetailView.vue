<script setup lang="ts">
/**
 * One robot, in detail.
 *
 * A page rather than a modal. A modal is for a short interaction with a way
 * out; this is a place an operator stays while watching a machine, and it needs
 * a URL so it can be bookmarked, reloaded, and sent to whoever is standing next
 * to the robot.
 *
 * This page intentionally stays focused on fleet telemetry and bridge health.
 * The live map and pose-changing controls belong to RobotNavigationView.
 */
import { computed, onBeforeUnmount, onMounted, watch } from 'vue'
import { RouterLink, useRoute } from 'vue-router'
import {
  ArrowLeft,
  Bell,
  BellOff,
  Bot,
  Radio,
  TriangleAlert,
} from 'lucide-vue-next'
import { useFleetStore } from '@/stores/fleet'
import { useLinkStore } from '@/stores/links'
import { activityStatus, dockingStatus } from '@/domain/ros/status'
import { Button } from '@/shared/ui/button'
import { Card, CardContent } from '@/shared/ui/card'
import PanelToolbar from '@/shared/components/PanelToolbar.vue'
import SectionLabel from '@/shared/components/SectionLabel.vue'
import StatusBadge from '@/shared/components/StatusBadge.vue'
import LinkIndicator from '@/shared/components/LinkIndicator.vue'
import MetricTile from '@/shared/components/MetricTile.vue'
import EmptyState from '@/shared/components/EmptyState.vue'
import TopicHealthTable from '../components/TopicHealthTable.vue'
import { formatNumber, formatPercent } from '@/shared/lib/utils'

const route = useRoute()
const fleet = useFleetStore()
const links = useLinkStore()

const robotId = computed(() => String(route.params.robotId))
const robot = computed(() => fleet.byId(robotId.value))
const link = computed(() => links.linkFor(robotId.value))
const vitals = computed(() => links.vitalsFor(robotId.value))
const muted = computed(() => links.isMuted(robotId.value))

onMounted(async () => {
  if (!fleet.loaded) await fleet.load()
  links.sync(fleet.robots)
  links.focus(robotId.value)
})

// Following the URL rather than a click keeps the focused robot and the address
// bar in agreement, including on a back-button navigation.
watch(robotId, (id) => links.focus(id))

onBeforeUnmount(() => links.focus(null))

const activity = computed(() =>
  vitals.value.activity === null ? null : activityStatus(vitals.value.activity),
)
const docking = computed(() =>
  vitals.value.docking === null ? null : dockingStatus(vitals.value.docking),
)

const staleTopics = computed(() => link.value.topics.filter((t) => t.state === 'stale'))
</script>

<template>
  <div class="space-y-base p-lg">
    <EmptyState
      v-if="!robot"
      title="Robot not found"
      description="It may have been removed from the registry."
    >
      <template #action>
        <Button size="sm" variant="secondary" as-child>
          <RouterLink to="/robot">Back to robots</RouterLink>
        </Button>
      </template>
    </EmptyState>

    <template v-else>
      <!-- Identity bar. The accent stripe and the name are the loudest things
           on the page: with a fleet, knowing which machine this is matters more
           than any single number on it. -->
      <Card>
        <PanelToolbar :title="robot.name" :subtitle="robot.bridgeUrl">
          <template #icon>
            <span
              class="flex h-7 w-7 shrink-0 items-center justify-center rounded-full text-white"
              :style="{ backgroundColor: `rgb(var(--robot-accent-${robot.accent}))` }"
            >
              <Bot :size="14" />
            </span>
          </template>
          <template #actions>
            <LinkIndicator :state="link.state" :attempt="link.attempt" />
            <Button
              variant="outline"
              size="sm"
              :title="muted ? 'Resume monitoring' : 'Stop monitoring this robot'"
              @click="links.setMuted(robotId, !muted)"
            >
              <component :is="muted ? BellOff : Bell" :size="14" />
              {{ muted ? 'Muted' : 'Monitoring' }}
            </Button>
            <Button variant="ghost" size="sm" as-child>
              <RouterLink to="/robot"><ArrowLeft :size="14" /> Back</RouterLink>
            </Button>
          </template>
        </PanelToolbar>

        <CardContent class="flex flex-wrap items-center justify-between gap-sm">
          <div>
            <div class="text-label uppercase text-muted">Technical details</div>
            <p class="mt-xxs text-body-sm text-body">
              Telemetry, diagnostics and bridge health for this robot.
            </p>
          </div>
          <Button variant="secondary" size="sm" as-child>
            <RouterLink :to="`/robot/${robotId}/nav`">Open navigation</RouterLink>
          </Button>
        </CardContent>
      </Card>

      <Card>
        <CardContent class="grid gap-sm sm:grid-cols-2 lg:grid-cols-4">
          <MetricTile
            label="Battery"
            :value="formatPercent(vitals.battery.percent)"
            :unit="vitals.battery.charging ? 'charging' : undefined"
            size="lg"
          />
          <MetricTile
            label="Voltage"
            :value="formatNumber(vitals.battery.voltage, 1)"
            unit="V"
            size="lg"
          />
          <div class="rounded-control bg-surface-soft px-sm py-xs">
            <div class="text-label uppercase text-muted">Activity</div>
            <div class="mt-xxs">
              <StatusBadge v-if="activity" :tone="activity.tone" :label="activity.label" />
              <!-- Not "Idle". /robot_status has no timer, so a parked robot
                   sends nothing — and guessing would be inventing a fact. -->
              <span v-else class="text-body-sm text-muted-soft">Not reported yet</span>
            </div>
          </div>
          <div class="rounded-control bg-surface-soft px-sm py-xs">
            <div class="text-label uppercase text-muted">Docking</div>
            <div class="mt-xxs">
              <StatusBadge v-if="docking" :tone="docking.tone" :label="docking.label" />
              <span v-else class="text-body-sm text-muted-soft">Not reported yet</span>
            </div>
          </div>
        </CardContent>
      </Card>

      <!-- What is actually wrong, when something is. -->
      <Card v-if="staleTopics.length || link.lastError">
        <CardContent class="space-y-xs">
          <SectionLabel>
            <template #icon><TriangleAlert :size="12" class="text-status-warn" /></template>
            Attention
          </SectionLabel>
          <p v-if="link.lastError" class="text-body-sm text-status-fault">
            {{ link.lastError }}
          </p>
          <p v-if="staleTopics.length" class="text-body-sm text-body">
            {{ staleTopics.length }} periodic
            {{ staleTopics.length === 1 ? 'topic has' : 'topics have' }} gone silent:
            <span class="text-ink">{{ staleTopics.map((t) => t.label).join(', ') }}</span
            >. The bridge is answering, so the process publishing them is the likely cause.
          </p>
        </CardContent>
      </Card>

      <Card>
        <PanelToolbar
          title="Topics"
          :subtitle="`${link.topics.filter((t) => t.state === 'ok').length} of ${link.topics.length} healthy`"
        >
          <template #icon><Radio :size="14" class="shrink-0 text-muted" /></template>
        </PanelToolbar>
        <TopicHealthTable :topics="link.topics" />
      </Card>
    </template>
  </div>
</template>
