<script setup lang="ts">
/**
 * Robot registry.
 *
 * A table rather than cards: the job here is comparing rows — which bridge,
 * which domain, which is online — and a table is what comparison wants.
 *
 * This screen replaces the old build-time VITE_ROS_URL. Being able to name and
 * address more than one robot is the first thing multi-robot support needs.
 */
import { computed, onMounted, ref, watch } from 'vue'
import { Bot, ChevronRight, Plus, RefreshCw, SquareArrowOutUpRight } from 'lucide-vue-next'
import { toast } from 'vue-sonner'
import { RouterLink } from 'vue-router'
import { useFleetStore } from '@/stores/fleet'
import { useLinkStore } from '@/stores/links'
import { Button } from '@/shared/ui/button'
import { Skeleton } from '@/shared/ui/skeleton'
import { Card } from '@/shared/ui/card'
import { Pagination } from '@/shared/ui/pagination'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/shared/ui/table'
import PanelToolbar from '@/shared/components/PanelToolbar.vue'
import StatusBadge from '@/shared/components/StatusBadge.vue'
import LinkIndicator from '@/shared/components/LinkIndicator.vue'
import ConfirmDialog from '@/shared/components/ConfirmDialog.vue'
import EmptyState from '@/shared/components/EmptyState.vue'
import BlockedTip from '@/shared/components/BlockedTip.vue'
import { usePermission } from '@/shared/composables/usePermission'
import RobotFormDialog from '../components/RobotFormDialog.vue'
import RobotTableSkeleton from '../components/RobotTableSkeleton.vue'
import RobotRowActions from '../components/RobotRowActions.vue'
import { clampPage, pageAfterResize, pageSlice, PAGE_SIZES } from '@/domain/pagination'
import { activityStatus } from '@/domain/ros/status'
import { RobotConflictError } from '@/shared/api/robots'
import type { RobotConfig } from '@/domain/types'
import type { toRobotPatch } from '@/domain/robot-form'

const fleet = useFleetStore()
const links = useLinkStore()
const { canEdit, editBlocker } = usePermission()

const formOpen = ref(false)
const editing = ref<RobotConfig | null>(null)
const saving = ref(false)
const pendingRemoval = ref<RobotConfig | null>(null)

onMounted(async () => {
  await fleet.load()
  // The pool reconciles against the registry, so this is safe to repeat.
  links.sync(fleet.robots)
})

// Keep the pool in step as robots are added, edited or removed.
watch(
  () => fleet.robots,
  (robots) => links.sync(robots),
  { deep: true },
)

const showSkeleton = computed(() => fleet.loading && !fleet.loaded)

function activityTone(robotId: string) {
  const activity = links.vitalsFor(robotId).activity
  return activity ? activityStatus(activity).tone : 'neutral'
}

function activityLabel(robotId: string): string {
  const activity = links.vitalsFor(robotId).activity
  return activity ? activityStatus(activity).label : '—'
}

// ── Pagination ───────────────────────────────────────────────────────────────
const page = ref(1)
const pageSize = ref<number>(PAGE_SIZES[0])

const visibleRobots = computed(() => pageSlice(fleet.robots, page.value, pageSize.value))

/**
 * Follow the data.
 *
 * Deleting the last row on the last page leaves the page index past the end,
 * and the table would render empty while still claiming to hold robots.
 */
watch(
  () => fleet.count,
  (total) => {
    page.value = clampPage(page.value, total, pageSize.value)
  },
)

function onPageSize(next: number) {
  page.value = pageAfterResize(page.value, pageSize.value, next, fleet.count)
  pageSize.value = next
}

const subtitle = computed(() => {
  if (fleet.loading && !fleet.loaded) return 'Loading\u2026'
  return `${fleet.count} registered`
})

function openAdd() {
  if (!canEdit.value) return
  editing.value = null
  formError.value = null
  formOpen.value = true
}

function openEdit(robot: RobotConfig) {
  if (!canEdit.value) return
  editing.value = robot
  formError.value = null
  formOpen.value = true
}

/**
 * Server-side conflict, routed back to the field that caused it.
 *
 * The form already checks uniqueness against the rows it can see, but it only
 * sees this page and this browser. The database is the authority, so its 409
 * has to reach the input rather than a toast that vanishes in three seconds.
 */
const formError = ref<{ field: 'name' | 'bridgeUrl' | null; message: string } | null>(null)

async function onSubmit(values: ReturnType<typeof toRobotPatch>) {
  saving.value = true
  formError.value = null
  try {
    if (editing.value) {
      const updated = await fleet.update(editing.value.id, values)
      toast.success(`Saved ${updated.name}`)
    } else {
      const created = await fleet.add(values)
      toast.success(`Added ${created.name}`)
    }
    formOpen.value = false
    editing.value = null
  } catch (error) {
    if (error instanceof RobotConflictError) {
      formError.value = { field: error.formField, message: error.message }
    } else {
      // The dialog stays open with the operator's input intact — retyping a
      // form because the backend was briefly down is its own small insult.
      formError.value = { field: null, message: fleet.describeError(error) }
    }
  } finally {
    saving.value = false
  }
}

const removing = ref(false)

async function confirmRemoval() {
  const robot = pendingRemoval.value
  if (!robot || !canEdit.value) return
  removing.value = true
  try {
    await fleet.remove(robot.id)
    toast.success(`Removed ${robot.name}`)
    pendingRemoval.value = null
  } catch (error) {
    toast.error(`Could not remove ${robot.name}`, { description: fleet.describeError(error) })
  } finally {
    removing.value = false
  }
}
</script>

<template>
  <div class="p-sm sm:p-base md:p-lg">
    <Card>
      <PanelToolbar title="Robots" :subtitle="subtitle">
        <template #icon><Bot :size="14" class="shrink-0 text-muted" /></template>
        <template #actions>
          <Button
            variant="outline"
            size="icon"
            title="Reload registry"
            :disabled="fleet.loading"
            @click="fleet.load()"
          >
            <RefreshCw :size="15" :class="fleet.loading && 'animate-spin'" />
          </Button>
          <BlockedTip :reason="editBlocker">
            <Button :disabled="!canEdit" @click="openAdd">
              <Plus :size="15" />
              <span>Add robot</span>
            </Button>
          </BlockedTip>
        </template>
      </PanelToolbar>

      <!-- Error takes precedence over everything: a stale table shown next to
           a failed reload is worse than no table. -->
      <div v-if="fleet.error" class="p-base">
        <EmptyState title="Could not load the registry" :description="fleet.error">
          <template #action>
            <Button size="sm" variant="secondary" @click="fleet.load()">Try again</Button>
          </template>
        </EmptyState>
      </div>

      <template v-else>
        <!--
        Phone: a list, not a table. The bridge address and domain are
        configuration, on the details page; here each row is the robot, how its
        link is, and what it is doing. The row opens its details.
      -->
        <ul v-if="showSkeleton" class="divide-y divide-hairline md:hidden">
          <li v-for="row in 3" :key="row" class="flex items-center gap-sm px-base py-sm">
            <Skeleton class="h-9 w-9 rounded-full" />
            <div class="flex-1 space-y-xs">
              <Skeleton class="h-4 w-28" />
              <Skeleton class="h-3 w-40" />
            </div>
          </li>
        </ul>
        <ul v-else-if="fleet.count > 0" class="divide-y divide-hairline md:hidden">
          <li v-for="robot in visibleRobots" :key="robot.id" class="flex items-center pr-xs">
            <RouterLink
              :to="`/robot/${robot.id}/detail`"
              class="flex min-h-[64px] min-w-0 flex-1 items-center gap-sm py-sm pl-base pr-xs transition-colors active:bg-surface-strong"
            >
              <span
                class="flex h-9 w-9 shrink-0 items-center justify-center rounded-full text-white"
                :style="{ backgroundColor: `rgb(var(--robot-accent-${robot.accent}))` }"
              >
                <Bot :size="16" />
              </span>
              <span class="min-w-0 flex-1">
                <span class="block truncate text-body-md font-medium text-ink">{{
                  robot.name
                }}</span>
                <span class="mt-[2px] flex items-center gap-xs text-body-sm text-body">
                  <LinkIndicator
                    :state="links.stateFor(robot.id)"
                    :attempt="links.linkFor(robot.id).attempt"
                  />
                  <template v-if="links.vitalsFor(robot.id).activity">
                    <span class="text-muted-soft" aria-hidden="true">·</span>
                    <span class="truncate">{{ activityLabel(robot.id) }}</span>
                  </template>
                </span>
              </span>
              <ChevronRight :size="16" class="shrink-0 text-muted-soft" />
            </RouterLink>
            <RobotRowActions
              :robot="robot"
              @edit="openEdit(robot)"
              @remove="pendingRemoval = robot"
            />
          </li>
        </ul>
        <div v-else-if="fleet.loaded" class="p-base md:hidden">
          <EmptyState
            title="No robots registered"
            description="Add one to start monitoring. A robot needs a name and a rosbridge WebSocket address."
          >
            <template #icon><Bot :size="20" class="text-muted" /></template>
          </EmptyState>
        </div>

        <div class="hidden md:block">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead class="whitespace-nowrap">Robot</TableHead>
                <!--
              Bridge absorbs the leftover width and truncates. A table cell
              sizes to its content, so a long ws:// URL would otherwise widen
              the table and hide the rest behind a horizontal scrollbar.
            -->
                <TableHead class="w-full max-w-0">Bridge</TableHead>
                <!-- Rarely set and on the details page: the first column to go. -->
                <TableHead class="hidden whitespace-nowrap lg:table-cell">Domain</TableHead>
                <TableHead class="whitespace-nowrap">Activity</TableHead>
                <TableHead class="whitespace-nowrap">Link</TableHead>
                <TableHead align="right">Actions</TableHead>
              </TableRow>
            </TableHeader>

            <RobotTableSkeleton v-if="showSkeleton" />

            <TableBody v-else-if="fleet.count > 0">
              <TableRow v-for="robot in visibleRobots" :key="robot.id" interactive>
                <TableCell>
                  <div class="flex items-center gap-sm whitespace-nowrap">
                    <span
                      class="flex h-8 w-8 shrink-0 items-center justify-center rounded-full text-white"
                      :style="{ backgroundColor: `rgb(var(--robot-accent-${robot.accent}))` }"
                    >
                      <Bot :size="15" />
                    </span>
                    <span class="text-title-sm text-ink">{{ robot.name }}</span>
                  </div>
                </TableCell>

                <TableCell class="w-full max-w-0">
                  <span
                    class="block truncate font-ident text-body-sm text-body"
                    :title="robot.bridgeUrl"
                  >
                    {{ robot.bridgeUrl }}
                  </span>
                </TableCell>

                <TableCell class="hidden lg:table-cell">
                  <span v-if="robot.rosDomainId !== null" class="font-data text-body-sm text-body">
                    {{ robot.rosDomainId }}
                  </span>
                  <!-- An unset optional field is a dash, not a zero. Zero is a
                   valid ROS domain. -->
                  <span v-else class="text-body-sm text-muted-soft" title="Not set">—</span>
                </TableCell>

                <TableCell>
                  <StatusBadge
                    v-if="links.vitalsFor(robot.id).activity"
                    :tone="activityTone(robot.id)"
                    :label="activityLabel(robot.id)"
                  />
                  <!-- /robot_status has no timer: a parked robot reports nothing,
                   and printing "Idle" would be inventing a fact. -->
                  <span
                    v-else
                    class="text-body-sm text-muted-soft"
                    title="No /robot_status received yet"
                  >
                    —
                  </span>
                </TableCell>

                <TableCell>
                  <LinkIndicator
                    :state="links.stateFor(robot.id)"
                    :attempt="links.linkFor(robot.id).attempt"
                  />
                </TableCell>

                <TableCell align="right">
                  <div class="flex justify-end gap-xxs">
                    <!--
                  Technical detail stays outside the menu: it is the primary
                  destination from the robot registry. The Dashboard owns the
                  operational navigation shortcut; the rest are occasional or
                  destructive actions.
                -->
                    <Button
                      variant="ghost"
                      size="sm"
                      :title="`Open details for ${robot.name}`"
                      as-child
                    >
                      <RouterLink :to="`/robot/${robot.id}/detail`">
                        <SquareArrowOutUpRight :size="13" /> Details
                      </RouterLink>
                    </Button>
                    <RobotRowActions
                      :robot="robot"
                      @edit="openEdit(robot)"
                      @remove="pendingRemoval = robot"
                    />
                  </div>
                </TableCell>
              </TableRow>
            </TableBody>

            <TableBody v-else>
              <TableRow>
                <TableCell colspan="6" class="h-auto p-base">
                  <EmptyState
                    title="No robots registered"
                    description="Add one to start monitoring. A robot needs a name and a rosbridge WebSocket address; the ROS domain is optional."
                  >
                    <template #icon><Bot :size="20" class="text-muted" /></template>
                    <template #action>
                      <BlockedTip :reason="editBlocker">
                        <Button size="sm" :disabled="!canEdit" @click="openAdd">
                          <Plus :size="14" /> Add robot
                        </Button>
                      </BlockedTip>
                    </template>
                  </EmptyState>
                </TableCell>
              </TableRow>
            </TableBody>
          </Table>
        </div>
      </template>

      <Pagination
        v-if="!fleet.error && !showSkeleton"
        :page="page"
        :page-size="pageSize"
        :total="fleet.count"
        @update:page="page = $event"
        @update:page-size="onPageSize"
      />
    </Card>

    <RobotFormDialog
      v-model:open="formOpen"
      :robot="editing"
      :existing="fleet.robots"
      :pending="saving"
      :server-error="formError"
      @submit="onSubmit"
    />

    <ConfirmDialog
      :open="pendingRemoval !== null"
      destructive
      :title="`Remove ${pendingRemoval?.name ?? ''}?`"
      :description="`This removes ${pendingRemoval?.name ?? 'the robot'} from the registry on this machine. Missions, maps and stations stored in the backend are not affected.`"
      confirm-label="Remove"
      :pending="removing"
      @update:open="(value: boolean) => !value && !removing && (pendingRemoval = null)"
      @cancel="pendingRemoval = null"
      @confirm="confirmRemoval"
    />
  </div>
</template>
