<script setup lang="ts">
/**
 * One robot, in detail.
 *
 * The diagnostic view of the machine Navigation shows operationally: the same
 * robot bar on top, with a tab between the two. What lives here is what an
 * operator needs when something is wrong — can the browser reach it, can its
 * agent reach the server, what it is configured as, and which topics have gone
 * quiet. The live map and pose-changing controls stay on RobotNavigationView,
 * so opening diagnostics can never arm a navigation tool.
 */
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { RouterLink, useRoute } from 'vue-router'
import {
  AlertCircle,
  CheckCircle2,
  CircleSlash,
  KeyRound,
  Pencil,
  Radio,
  TriangleAlert,
} from 'lucide-vue-next'
import { toast } from 'vue-sonner'
import { useFleetStore } from '@/stores/fleet'
import { useLinkStore } from '@/stores/links'
import { useMapStore } from '@/stores/maps'
import { useUiStore } from '@/stores/ui'
import { useRobotTelemetry } from '@/features/mapping/useRobotTelemetry'
import { RobotConflictError } from '@/shared/api/robots'
import type { toRobotPatch } from '@/domain/robot-form'
import { Button } from '@/shared/ui/button'
import EmptyState from '@/shared/components/EmptyState.vue'
import CollapsibleSection from '@/shared/components/CollapsibleSection.vue'
import BlockedTip from '@/shared/components/BlockedTip.vue'
import { usePermission } from '@/shared/composables/usePermission'
import TopicHealthTable from '../components/TopicHealthTable.vue'
import RobotBar from '../components/RobotBar.vue'
import RobotFormDialog from '../components/RobotFormDialog.vue'
import AgentTokenDialog from '../components/AgentTokenDialog.vue'
import ConfirmDialog from '@/shared/components/ConfirmDialog.vue'
import { robotsApi } from '@/shared/api/robots'
import { useRobotStop } from '../useRobotStop'
import { backendLabel, connectionHelp } from '../connectionHelp'
import { problemTopics, robotHealth, type HealthTone } from '../robotHealth'
import { cn } from '@/shared/lib/utils'

const route = useRoute()
const fleet = useFleetStore()
const links = useLinkStore()
const maps = useMapStore()
const ui = useUiStore()
const { canEdit, editBlocker } = usePermission()

const robotId = computed(() => String(route.params.robotId))
const robot = computed(() => fleet.byId(robotId.value))
const link = computed(() => links.linkFor(robotId.value))
const muted = computed(() => links.isMuted(robotId.value))
const telemetry = useRobotTelemetry(() => robotId.value)
const { stopAndPark, stopPending } = useRobotStop(robotId)

// Same room-making as Navigation: the rail folds while a robot page is open.
onMounted(() => ui.foldNav(true))
onBeforeUnmount(() => ui.foldNav(false))

onMounted(async () => {
  if (!maps.loaded) void maps.load()
  if (!fleet.loaded) await fleet.load()
  links.sync(fleet.robots)
  links.focus(robotId.value)
})

// Following the URL rather than a click keeps the focused robot and the address
// bar in agreement, including on a back-button navigation.
watch(robotId, (id) => links.focus(id))
onBeforeUnmount(() => links.focus(null))

const online = computed(() => link.value.state === 'online' || link.value.state === 'stale')

const connection = computed(() =>
  robot.value ? connectionHelp(link.value.state, robot.value.bridgeUrl, link.value.attempt) : null,
)

const CONNECTION_TONE: Record<string, string> = {
  ok: 'text-status-ok',
  warn: 'text-status-warn',
  fault: 'text-status-fault',
  muted: 'text-muted',
}

const staleTopics = computed(() => link.value.topics.filter((t) => t.state === 'stale'))

// ── The verdict, first thing on the page ─────────────────────────────────────

const host = computed(() => {
  try {
    return new URL(robot.value?.bridgeUrl ?? '').host
  } catch {
    return robot.value?.bridgeUrl ?? ''
  }
})

const health = computed(() =>
  robotHealth({
    link: link.value.state,
    host: host.value,
    agent: online.value ? telemetry.agent.value : null,
    topics: link.value.topics,
  }),
)

const HEALTH_STYLE: Record<HealthTone, { icon: typeof Radio; card: string; text: string }> = {
  ok: {
    icon: CheckCircle2,
    card: 'border-status-ok/30 bg-status-ok/[0.05]',
    text: 'text-status-ok',
  },
  warn: {
    icon: TriangleAlert,
    card: 'border-status-warn/40 bg-status-warn/[0.07]',
    text: 'text-status-warn',
  },
  fault: {
    icon: AlertCircle,
    card: 'border-status-fault/30 bg-status-fault/[0.05]',
    text: 'text-status-fault',
  },
  muted: { icon: CircleSlash, card: 'border-hairline bg-surface', text: 'text-muted' },
}

// ── Topics: on a phone, the ones that need looking at, then the rest on ask ──

const showAllTopics = ref(false)
const problems = computed(() => problemTopics(link.value.topics))
const shownTopics = computed(() =>
  ui.screen === 'phone' && !showAllTopics.value ? problems.value : link.value.topics,
)
const hiddenTopicCount = computed(() => link.value.topics.length - shownTopics.value.length)

// ── Robot agent ──────────────────────────────────────────────────────────────

const agent = computed(() => (online.value ? telemetry.agent.value : null))

const stackLine = computed(() => {
  const status = agent.value
  if (!status) return { text: '—', tone: 'text-muted' }
  const name = status.mode === 'nav' ? 'Nav2' : status.mode === 'map' ? 'SLAM' : null
  if (!name) return { text: 'Stopped', tone: 'text-muted' }
  const tone =
    status.state === 'running'
      ? 'text-status-ok'
      : status.state === 'failed'
        ? 'text-status-fault'
        : 'text-status-warn'
  return { text: `${name} ${status.state}`, tone }
})

const server = computed(() =>
  agent.value ? backendLabel(agent.value.backend) : { text: '—', tone: 'text-muted' },
)

// ── Configuration ────────────────────────────────────────────────────────────

const mapLabel = computed(() => {
  const id = robot.value?.activeMapId
  if (!id) return null
  const map = maps.byId(id)
  return map ? `${map.name} v${map.version}` : 'Unknown map'
})

const formOpen = ref(false)
const saving = ref(false)
const formError = ref<{ field: 'name' | 'bridgeUrl' | null; message: string } | null>(null)

async function onSubmit(values: ReturnType<typeof toRobotPatch>) {
  if (!robot.value || !canEdit.value) return
  saving.value = true
  formError.value = null
  try {
    const updated = await fleet.update(robot.value.id, values)
    toast.success(`Saved ${updated.name}`)
    formOpen.value = false
    // A new bridge URL means a new connection.
    links.sync(fleet.robots)
  } catch (error) {
    formError.value =
      error instanceof RobotConflictError
        ? { field: error.formField, message: error.message }
        : { field: null, message: fleet.describeError(error) }
  } finally {
    saving.value = false
  }
}

// ── Agent token ──────────────────────────────────────────────────────────────

const tokenStatus = computed(() => {
  const r = robot.value
  if (!r?.agentTokenSet) return 'Not set'
  const date = r.agentTokenCreatedAt ? new Date(r.agentTokenCreatedAt) : null
  return date && !Number.isNaN(date.getTime())
    ? `Set on ${date.toLocaleDateString()}`
    : 'Set'
})

/** Which confirmation is open. Rotating and revoking both cut the agent off. */
const tokenConfirm = ref<'rotate' | 'revoke' | null>(null)
const tokenPending = ref(false)
/** The plaintext, held only while its dialog is open. */
const issuedToken = ref('')
const tokenDialogOpen = ref(false)

watch(tokenDialogOpen, (open) => {
  if (!open) issuedToken.value = ''
})

async function generateToken() {
  if (!robot.value || !canEdit.value) return
  tokenPending.value = true
  try {
    const issued = await robotsApi.createAgentToken(robot.value.id)
    issuedToken.value = issued.token
    tokenDialogOpen.value = true
    tokenConfirm.value = null
    await fleet.load()
  } catch (error) {
    toast.error(fleet.describeError(error))
  } finally {
    tokenPending.value = false
  }
}

async function revokeToken() {
  if (!robot.value || !canEdit.value) return
  tokenPending.value = true
  try {
    await robotsApi.revokeAgentToken(robot.value.id)
    toast.success('Agent token revoked')
    tokenConfirm.value = null
    await fleet.load()
  } catch (error) {
    toast.error(fleet.describeError(error))
  } finally {
    tokenPending.value = false
  }
}

function onGenerateClick() {
  if (robot.value?.agentTokenSet) tokenConfirm.value = 'rotate'
  else void generateToken()
}
</script>

<template>
  <div v-if="!robot" class="p-lg">
    <EmptyState title="Robot not found" description="It may have been removed from the registry.">
      <template #action>
        <Button size="sm" variant="secondary" as-child>
          <RouterLink to="/robot">Back to robots</RouterLink>
        </Button>
      </template>
    </EmptyState>
  </div>

  <div v-else class="flex h-full min-h-0 flex-col">
    <RobotBar
      :robot="robot"
      :link-state="link.state"
      :attempt="link.attempt"
      :stop-pending="stopPending"
      @stop="stopAndPark"
    />

    <div class="min-h-0 flex-1 overflow-y-auto scrollbar-thin">
      <div class="mx-auto grid max-w-[64rem] gap-base p-base lg:grid-cols-2 lg:p-lg">
        <!-- The verdict: healthy or not, and the one thing to know. Everything
             below is the evidence for it. -->
        <section
          :class="
            cn(
              'flex items-start gap-sm rounded-surface border p-base lg:col-span-2',
              HEALTH_STYLE[health.tone].card,
            )
          "
          role="status"
        >
          <component
            :is="HEALTH_STYLE[health.tone].icon"
            :size="20"
            :class="cn('mt-[2px] shrink-0', HEALTH_STYLE[health.tone].text)"
          />
          <div class="min-w-0">
            <p :class="cn('text-title-sm', HEALTH_STYLE[health.tone].text)">{{ health.title }}</p>
            <p class="mt-[2px] text-body-sm text-body">{{ health.line }}</p>
          </div>
        </section>

        <!-- Connection: can this browser reach the robot, and if not, why. -->
        <section class="rounded-surface border border-hairline bg-surface p-base">
          <h2 class="text-label uppercase text-muted">Connection</h2>
          <!-- When the link is the problem, the verdict above already says so in
               the same words; this card then only adds what to do about it. -->
          <template v-if="connection && online">
            <p class="mt-xs text-body-md font-medium" :class="CONNECTION_TONE[connection.tone]">
              {{ connection.title }}
            </p>
            <p v-if="connection.detail" class="mt-xxs text-body-sm text-body">
              {{ connection.detail }}
            </p>
          </template>
          <p v-else-if="connection && muted" class="mt-xs text-body-sm text-muted">
            {{ connection.detail }}
          </p>
          <!-- Open on wide screens; a tap away on a phone. -->
          <details
            v-if="connection?.checks.length"
            class="group mt-xs rounded-control border border-hairline"
            :open="ui.screen !== 'phone'"
          >
            <summary
              class="flex cursor-pointer list-none items-center gap-xs px-sm py-xs text-body-sm text-ink touch:min-h-[44px]"
            >
              <span class="text-muted transition-transform group-open:rotate-90">›</span>
              What to check ({{ connection.checks.length }})
            </summary>
            <ol class="list-decimal space-y-xxs px-sm pb-sm pl-[2.25rem] text-body-sm text-body">
              <li v-for="check in connection.checks" :key="check">{{ check }}</li>
            </ol>
          </details>
          <details v-if="link.lastError && !online" class="group mt-xs">
            <summary
              class="flex cursor-pointer list-none items-center gap-xs text-caption text-muted touch:min-h-[44px]"
            >
              <span class="transition-transform group-open:rotate-90">›</span>
              Technical detail
            </summary>
            <p class="mt-xxs font-data text-caption text-muted">
              Browser reported: {{ link.lastError }}
            </p>
          </details>
        </section>

        <!-- Robot agent: whether the robot's own process can reach the server.
             "Missions do not arrive" is usually this, not the browser. -->
        <section class="rounded-surface border border-hairline bg-surface p-base">
          <h2 class="text-label uppercase text-muted">Robot agent</h2>
          <dl class="mt-xs space-y-xs text-body-sm">
            <div class="flex items-baseline justify-between gap-sm">
              <dt class="text-muted">Stack</dt>
              <dd class="font-medium" :class="stackLine.tone">{{ stackLine.text }}</dd>
            </div>
            <div class="flex items-baseline justify-between gap-sm">
              <dt class="shrink-0 text-muted">Server</dt>
              <dd class="text-right font-medium" :class="server.tone">{{ server.text }}</dd>
            </div>
            <div v-if="agent?.teleop" class="flex items-baseline justify-between gap-sm">
              <dt class="text-muted">Driving</dt>
              <dd class="font-medium text-status-warn">Manual (teleop)</dd>
            </div>
            <div v-if="agent?.detail" class="flex items-baseline justify-between gap-sm">
              <dt class="shrink-0 text-muted">Last note</dt>
              <dd class="text-right text-body">{{ agent.detail }}</dd>
            </div>
          </dl>
          <p v-if="!online" class="mt-sm text-caption text-muted">
            Reported by the robot, so known once it is connected.
          </p>
          <p v-else-if="!telemetry.agent.value" class="mt-sm text-caption text-status-warn">
            Connected, but the agent has not reported. Is <span class="font-data">robot_agent</span>
            running?
          </p>
        </section>

        <!-- Topics: the bridge's view, per topic. Only worth a table when
             there is a connection to have topics on. -->
        <section
          class="overflow-hidden rounded-surface border border-hairline bg-surface lg:col-span-2"
        >
          <div class="flex items-center gap-xs px-base pt-base">
            <Radio :size="14" class="shrink-0 text-muted" />
            <h2 class="text-label uppercase text-muted">Topics</h2>
            <span v-if="link.topics.length" class="ml-auto text-caption text-muted">
              {{ link.topics.filter((t) => t.state === 'ok').length }} of
              {{ link.topics.length }} healthy
            </span>
          </div>

          <p
            v-if="staleTopics.length"
            :class="
              cn(
                'mx-base mt-sm flex items-start gap-xs rounded-control border border-status-warn/40 bg-status-warn/10 p-sm text-body-sm text-body',
              )
            "
          >
            <TriangleAlert :size="14" class="mt-[2px] shrink-0 text-status-warn" />
            <span>
              {{ staleTopics.length }} periodic
              {{ staleTopics.length === 1 ? 'topic has' : 'topics have' }} gone silent:
              <span class="text-ink">{{ staleTopics.map((t) => t.label).join(', ') }}</span
              >.
            </span>
          </p>

          <div v-if="online || link.topics.length" class="mt-sm">
            <TopicHealthTable v-if="shownTopics.length" :topics="shownTopics" />
            <p v-else class="px-base pb-xs text-body-sm text-status-ok">
              All {{ link.topics.length }} topics are fine.
            </p>
            <button
              v-if="hiddenTopicCount > 0 || (showAllTopics && ui.screen === 'phone')"
              type="button"
              class="w-full border-t border-hairline px-base py-sm text-left text-body-sm font-medium text-primary touch:min-h-[44px] md:hidden"
              @click="showAllTopics = !showAllTopics"
            >
              {{ showAllTopics ? 'Show only problems' : `Show all ${link.topics.length} topics` }}
            </button>
          </div>
          <p v-else class="px-base pb-base pt-xs text-body-sm text-muted">
            {{
              muted
                ? 'Monitoring is off, so nothing is subscribed.'
                : 'Topics appear once the robot is connected.'
            }}
          </p>
        </section>

        <!-- Configuration: what the registry says this robot is. Reference
             material: folded on a phone, the map named in the header. -->
        <CollapsibleSection
          title="Configuration"
          :summary="mapLabel ?? 'No map'"
          class="lg:col-span-2"
        >
          <template #actions>
            <BlockedTip :reason="editBlocker">
              <Button variant="outline" size="sm" :disabled="!canEdit" @click="formOpen = true">
                <Pencil :size="13" /> Edit
              </Button>
            </BlockedTip>
          </template>
          <dl class="grid gap-x-lg gap-y-xs text-body-sm sm:grid-cols-2">
            <div class="flex items-baseline justify-between gap-sm">
              <dt class="shrink-0 text-muted">rosbridge</dt>
              <dd class="truncate font-data text-ink">{{ robot.bridgeUrl }}</dd>
            </div>
            <div class="flex items-baseline justify-between gap-sm">
              <dt class="shrink-0 text-muted">Active map</dt>
              <dd class="truncate">
                <RouterLink
                  v-if="mapLabel"
                  to="/maps"
                  class="text-ink hover:text-primary hover:underline"
                >
                  {{ mapLabel }}
                </RouterLink>
                <span v-else class="text-status-warn">Not assigned</span>
              </dd>
            </div>
            <div class="flex items-baseline justify-between gap-sm">
              <dt class="shrink-0 text-muted">Namespace</dt>
              <dd class="truncate font-data" :class="robot.namespace ? 'text-ink' : 'text-muted'">
                {{ robot.namespace || 'none' }}
              </dd>
            </div>
            <div class="flex items-baseline justify-between gap-sm">
              <dt class="shrink-0 text-muted">ROS domain</dt>
              <dd class="font-data" :class="robot.rosDomainId !== null ? 'text-ink' : 'text-muted'">
                {{ robot.rosDomainId ?? 'not set' }}
              </dd>
            </div>
            <div class="flex items-baseline justify-between gap-sm">
              <dt class="shrink-0 text-muted">Serial</dt>
              <dd class="truncate font-data" :class="robot.serial ? 'text-ink' : 'text-muted'">
                {{ robot.serial || '—' }}
              </dd>
            </div>
            <div class="flex items-baseline justify-between gap-sm">
              <dt class="shrink-0 text-muted">Camera</dt>
              <dd class="truncate font-data" :class="robot.cameraUrl ? 'text-ink' : 'text-muted'">
                {{ robot.cameraUrl || '—' }}
              </dd>
            </div>
            <div class="flex flex-wrap items-center justify-between gap-sm sm:col-span-2">
              <dt class="flex shrink-0 items-center gap-xs text-muted">
                <KeyRound :size="13" /> Agent token
              </dt>
              <dd class="flex flex-wrap items-center gap-xs">
                <span
                  data-testid="agent-token-status"
                  :class="robot.agentTokenSet ? 'text-ink' : 'text-muted'"
                  >{{ tokenStatus }}</span
                >
                <BlockedTip :reason="editBlocker">
                  <Button
                    variant="outline"
                    size="sm"
                    data-testid="agent-token-generate"
                    :disabled="!canEdit || tokenPending"
                    @click="onGenerateClick"
                  >
                    {{ robot.agentTokenSet ? 'Rotate token' : 'Generate token' }}
                  </Button>
                </BlockedTip>
                <BlockedTip v-if="robot.agentTokenSet" :reason="editBlocker">
                  <Button
                    variant="outline"
                    size="sm"
                    data-testid="agent-token-revoke"
                    :disabled="!canEdit || tokenPending"
                    @click="tokenConfirm = 'revoke'"
                  >
                    Revoke
                  </Button>
                </BlockedTip>
              </dd>
            </div>
          </dl>
        </CollapsibleSection>

        <!-- Monitoring: a setting, rarely changed, so folded on a phone; the
             header still says whether it is on. -->
        <CollapsibleSection
          title="Monitoring"
          :summary="muted ? 'Off' : 'On'"
          class="lg:col-span-2"
        >
          <div class="flex items-start gap-sm">
            <p class="min-w-0 flex-1 text-caption text-muted">
              <span class="md:hidden"
                >Alarm when the link drops. Turn off for a robot in the workshop.</span
              >
              <span class="hidden md:inline">
                Connects to this robot, raises an alarm when its link drops, and counts it on the
                dashboard. Turn off for a robot in the workshop.
              </span>
            </p>
            <button
              type="button"
              role="switch"
              :aria-checked="!muted"
              aria-label="Monitoring"
              class="relative mt-[2px] flex h-5 w-9 shrink-0 items-center rounded-full p-[2px] transition-colors before:absolute before:-inset-[12px] before:content-['']"
              :class="!muted ? 'bg-primary' : 'bg-hairline'"
              @click="links.setMuted(robotId, !muted)"
            >
              <span
                class="h-4 w-4 rounded-full bg-white shadow-soft transition-transform"
                :class="!muted ? 'translate-x-4' : 'translate-x-0'"
              />
            </button>
          </div>
        </CollapsibleSection>
      </div>
    </div>

    <RobotFormDialog
      v-model:open="formOpen"
      :robot="robot"
      :existing="fleet.robots"
      :pending="saving"
      :server-error="formError"
      @submit="onSubmit"
    />

    <ConfirmDialog
      :open="tokenConfirm !== null"
      destructive
      :pending="tokenPending"
      :title="tokenConfirm === 'revoke' ? `Revoke ${robot.name}'s token?` : `Rotate ${robot.name}'s token?`"
      :description="
        tokenConfirm === 'revoke'
          ? 'The robot agent stops authenticating with the server right away and stays cut off until a new token is generated, put in /etc/amr/robot.env as AMR_AGENT_TOKEN, and amr-agent is restarted.'
          : 'The current token stops working at once, so the robot agent stops authenticating until the new token is put in /etc/amr/robot.env as AMR_AGENT_TOKEN and amr-agent is restarted.'
      "
      :confirm-label="tokenConfirm === 'revoke' ? 'Revoke' : 'Rotate'"
      @update:open="(open: boolean) => !open && !tokenPending && (tokenConfirm = null)"
      @cancel="tokenConfirm = null"
      @confirm="tokenConfirm === 'revoke' ? revokeToken() : generateToken()"
    />

    <AgentTokenDialog v-model:open="tokenDialogOpen" :token="issuedToken" :robot-name="robot.name" />
  </div>
</template>
