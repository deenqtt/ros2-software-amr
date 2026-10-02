<script setup lang="ts">
/**
 * Map registry.
 *
 * The backend owns maps; robots keep a cache and pull when told to. A map is
 * born on a robot — slam_toolbox writes it to that robot's own disk, so a
 * survey survives the server being unreachable — and is published here
 * afterwards.
 *
 * Maps are immutable and versioned. Re-surveying a site adds a version rather
 * than replacing one, because stations store coordinates in a specific map
 * frame: overwriting a map silently invalidates every station attached to it,
 * on every robot still running the old one.
 */
import { computed, onMounted, ref, watch } from 'vue'
import {
  Brush,
  ChevronDown,
  ChevronRight,
  CornerDownRight,
  Download,
  Map as MapIcon,
  Pencil,
  ScanLine,
  Trash2,
  Upload,
  RefreshCw,
} from 'lucide-vue-next'
import { toast } from 'vue-sonner'
import { useRouter } from 'vue-router'
import { useMapStore } from '@/stores/maps'
import { useFleetStore } from '@/stores/fleet'
import { useLinkStore } from '@/stores/links'
import { mapsApi, MapInUseError } from '@/shared/api/maps'
import { robotsApi } from '@/shared/api/robots'
import { mapExtentMetres, type MapRecord } from '@/domain/types'
import { clampPage, pageAfterResize, pageSlice, PAGE_SIZES } from '@/domain/pagination'
import { Button } from '@/shared/ui/button'
import { RowActions, RowActionItem, RowActionSeparator } from '@/shared/ui/menu'
import { Card } from '@/shared/ui/card'
import { Pagination } from '@/shared/ui/pagination'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/shared/ui/table'
import { Badge } from '@/shared/ui/badge'
import PanelToolbar from '@/shared/components/PanelToolbar.vue'
import EmptyState from '@/shared/components/EmptyState.vue'
import ConfirmDialog from '@/shared/components/ConfirmDialog.vue'
import MapUploadDialog from '../components/MapUploadDialog.vue'
import AssignMapDialog from '../components/AssignMapDialog.vue'
import MapTableSkeleton from '../components/MapTableSkeleton.vue'
import StartSurveyDialog from '../components/StartSurveyDialog.vue'
import RenameMapDialog from '../components/RenameMapDialog.vue'
import { formatNumber } from '@/shared/lib/utils'

const maps = useMapStore()
const fleet = useFleetStore()
const links = useLinkStore()
const router = useRouter()

const surveyOpen = ref(false)

const uploadOpen = ref(false)
const uploading = ref(false)
const uploadError = ref<string | null>(null)

const assigning = ref<MapRecord | null>(null)
const assignPending = ref(false)
const assignError = ref<string | null>(null)

const renaming = ref<MapRecord | null>(null)
const renamePending = ref(false)
const renameError = ref<string | null>(null)

const pendingRemoval = ref<MapRecord | null>(null)
const removing = ref(false)
const removalBlockedBy = ref<string[]>([])

onMounted(async () => {
  await Promise.all([maps.load(), fleet.load()])
  // The survey picker needs live link state to say which robots can be asked.
  links.sync(fleet.robots)
})

function startSurvey(robotId: string) {
  surveyOpen.value = false
  void router.push(`/maps/survey/${robotId}`)
}

const showSkeleton = computed(() => maps.loading && !maps.loaded)

// ── Grouping ─────────────────────────────────────────────────────────────────
//
// One row per map, not per version. Editing a map three times used to put three
// peer rows in the table, which reads as three maps — and made the version model
// look like clutter rather than a safety net. Older versions are still here, and
// still assignable, one click away.

interface MapGroup {
  key: string
  latest: MapRecord
  /** Older versions, newest first. */
  older: MapRecord[]
}

const groups = computed<MapGroup[]>(() => {
  const byName = new Map<string, MapGroup>()
  // The server orders by name then version descending, so the first row of each
  // name is its newest and the rest arrive in the order they should be listed.
  for (const map of maps.maps) {
    const key = map.name.toLocaleLowerCase()
    const existing = byName.get(key)
    if (!existing) byName.set(key, { key, latest: map, older: [] })
    else existing.older.push(map)
  }
  return [...byName.values()]
})

const expanded = ref(new Set<string>())

function toggleGroup(key: string) {
  const next = new Set(expanded.value)
  if (!next.delete(key)) next.add(key)
  expanded.value = next
}

// ── Pagination ───────────────────────────────────────────────────────────────
const page = ref(1)
const pageSize = ref<number>(PAGE_SIZES[0])
/** Pages over maps, not versions, or an expanded group could straddle a page. */
const visible = computed(() => pageSlice(groups.value, page.value, pageSize.value))

/** Flattened for one v-for: a group's latest, then its older versions if open. */
const rendered = computed(() =>
  visible.value.flatMap((group) => [
    { map: group.latest, group, child: false },
    ...(expanded.value.has(group.key)
      ? group.older.map((map) => ({ map, group, child: true }))
      : []),
  ]),
)

watch(
  () => groups.value.length,
  (total) => {
    page.value = clampPage(page.value, total, pageSize.value)
  },
)

function onPageSize(next: number) {
  page.value = pageAfterResize(page.value, pageSize.value, next, groups.value.length)
  pageSize.value = next
}

const subtitle = computed(() => {
  if (maps.loading && !maps.loaded) return 'Loading…'
  const names = new Set(maps.maps.map((m) => m.name.toLocaleLowerCase())).size
  return `${maps.count} version${maps.count === 1 ? '' : 's'} across ${names} map${names === 1 ? '' : 's'}`
})

// ── Robots on a map ──────────────────────────────────────────────────────────
/** Robot names listed in a row before the rest collapse into "+N". */
const ROBOTS_SHOWN = 2

function robotsOn(mapId: string) {
  return fleet.robots.filter((robot) => robot.activeMapId === mapId)
}

function extentLabel(map: MapRecord): string {
  const extent = mapExtentMetres(map)
  if (!extent) return '—'
  return `${formatNumber(extent.width, 1)} × ${formatNumber(extent.height, 1)} m`
}

function gridLabel(map: MapRecord): string {
  if (map.width === null || map.height === null) return '—'
  return `${map.width}×${map.height} px @ ${formatNumber(map.resolution, 3)} m`
}

function sizeLabel(bytes: number): string {
  return bytes < 1024 * 1024
    ? `${Math.round(bytes / 1024)} KB`
    : `${formatNumber(bytes / (1024 * 1024), 1)} MB`
}

function robotName(robotId: string | null): string {
  if (!robotId) return '—'
  return fleet.byId(robotId)?.name ?? 'retired robot'
}

// ── Actions ──────────────────────────────────────────────────────────────────
async function onUpload(payload: {
  name: string
  yamlFile: File
  imageFile: File
  note: string | null
}) {
  uploading.value = true
  uploadError.value = null
  try {
    const created = await maps.upload(payload)
    toast.success(`Uploaded ${created.name} v${created.version}`)
    uploadOpen.value = false
  } catch (error) {
    uploadError.value = maps.describeError(error)
  } finally {
    uploading.value = false
  }
}

async function onAssign(robotIds: string[]) {
  const map = assigning.value
  if (!map) return
  assignPending.value = true
  assignError.value = null

  const wanted = new Set(robotIds)
  const changes = fleet.robots.filter(
    (robot) => (robot.activeMapId === map.id) !== wanted.has(robot.id),
  )

  try {
    // Sequential, not parallel: a partial failure has to leave a state the
    // operator can reason about, and the list is a handful of robots.
    for (const robot of changes) {
      const target = wanted.has(robot.id) ? map.id : null
      await robotsApi.assignMap(robot.id, target)
    }
    await fleet.load()
    toast.success(`Updated ${changes.length} robot${changes.length === 1 ? '' : 's'}`)
    assigning.value = null
  } catch (error) {
    await fleet.load()
    assignError.value = maps.describeError(error)
  } finally {
    assignPending.value = false
  }
}

async function onRename(name: string) {
  const map = renaming.value
  if (!map) return
  renamePending.value = true
  renameError.value = null
  try {
    const renamed = await maps.rename(map.id, name)
    toast.success(`Renamed to ${renamed.name}`)
    renaming.value = null
  } catch (error) {
    renameError.value = maps.describeError(error)
  } finally {
    renamePending.value = false
  }
}

function closeRename(open: boolean) {
  if (open || renamePending.value) return
  renaming.value = null
  renameError.value = null
}

function askRemove(map: MapRecord) {
  removalBlockedBy.value = robotsOn(map.id).map((r) => r.name)
  pendingRemoval.value = map
}

/**
 * Leave the delete and go fix the reason it is refused.
 *
 * The blocking robots are the operator's next action, so this hands them the
 * assignment dialog for the same map rather than closing and leaving them to
 * find the row again.
 */
function reassignInsteadOfRemoving() {
  const map = pendingRemoval.value
  pendingRemoval.value = null
  removalBlockedBy.value = []
  assigning.value = map
}

async function confirmRemoval() {
  const map = pendingRemoval.value
  if (!map) return
  removing.value = true
  try {
    await maps.remove(map.id)
    toast.success(`Removed ${map.name} v${map.version}`)
    pendingRemoval.value = null
  } catch (error) {
    if (error instanceof MapInUseError) {
      removalBlockedBy.value = error.robots
      toast.error('Still in use', { description: error.message })
    } else {
      toast.error(`Could not remove ${map.name}`, { description: maps.describeError(error) })
    }
  } finally {
    removing.value = false
  }
}
</script>

<template>
  <div class="p-lg">
    <Card>
      <PanelToolbar title="Maps" :subtitle="subtitle">
        <template #icon><MapIcon :size="14" class="shrink-0 text-muted" /></template>
        <template #actions>
          <Button
            variant="outline"
            size="icon"
            title="Reload registry"
            :disabled="maps.loading"
            @click="maps.load()"
          >
            <RefreshCw :size="15" :class="maps.loading && 'animate-spin'" />
          </Button>
          <Button variant="outline" @click="surveyOpen = true">
            <ScanLine :size="15" />
            <span>Create map</span>
          </Button>
          <Button @click="uploadOpen = true">
            <Upload :size="15" />
            <span>Upload map</span>
          </Button>
        </template>
      </PanelToolbar>

      <div v-if="maps.error" class="p-base">
        <EmptyState title="Could not load the registry" :description="maps.error">
          <template #action>
            <Button size="sm" variant="secondary" @click="maps.load()">Try again</Button>
          </template>
        </EmptyState>
      </div>

      <Table v-else>
        <TableHeader>
          <TableRow>
            <!--
              w-full + max-w-0 on the name column: a table cell sizes to its
              content, so a long note used to widen the table and put the whole
              thing behind a horizontal scrollbar. This makes the column take
              whatever is left and lets its text truncate against that.

              min-w keeps the name itself: on a narrow screen the column that
              gives way has to be one of the others, not the map's identity.
              They go in order of how rarely they decide anything — size, who
              surveyed it, then extent (the subtitle still carries the grid).
            -->
            <TableHead class="w-full min-w-[12rem] max-w-0">Map</TableHead>
            <TableHead class="hidden whitespace-nowrap lg:table-cell">Extent</TableHead>
            <TableHead class="hidden whitespace-nowrap xl:table-cell">Size</TableHead>
            <TableHead class="whitespace-nowrap">Robots</TableHead>
            <TableHead class="hidden whitespace-nowrap xl:table-cell">Surveyed by</TableHead>
            <TableHead align="right">Actions</TableHead>
          </TableRow>
        </TableHeader>

        <MapTableSkeleton v-if="showSkeleton" />

        <TableBody v-else-if="maps.count > 0">
          <TableRow v-for="row in rendered" :key="row.map.id" interactive>
            <TableCell class="w-full min-w-[12rem] max-w-0">
              <div class="flex items-center gap-sm" :class="row.child ? 'pl-lg' : ''">
                <!--
                  The expander replaces the icon on a map with history, so the
                  row does not grow a control it usually has no use for.
                -->
                <button
                  v-if="!row.child && row.group.older.length"
                  type="button"
                  :aria-expanded="expanded.has(row.group.key)"
                  :aria-label="`${expanded.has(row.group.key) ? 'Hide' : 'Show'} older versions of ${row.map.name}`"
                  :title="`${expanded.has(row.group.key) ? 'Hide' : 'Show'} the ${row.group.older.length} older version${row.group.older.length === 1 ? '' : 's'} of ${row.map.name}`"
                  class="flex h-8 w-8 shrink-0 items-center justify-center rounded-control bg-surface-strong text-muted transition-colors hover:text-ink"
                  @click="toggleGroup(row.group.key)"
                >
                  <component
                    :is="expanded.has(row.group.key) ? ChevronDown : ChevronRight"
                    :size="15"
                  />
                </button>
                <span
                  v-else
                  class="flex h-8 w-8 shrink-0 items-center justify-center rounded-control text-muted"
                  :class="row.child ? '' : 'bg-surface-strong'"
                >
                  <MapIcon v-if="!row.child" :size="15" />
                  <CornerDownRight v-else :size="13" class="text-muted-soft" />
                </span>
                <div class="min-w-0">
                  <div class="flex items-center gap-xs">
                    <span
                      class="truncate text-ink"
                      :class="row.child ? 'text-body-sm' : 'text-title-sm'"
                    >
                      {{ row.child ? `v${row.map.version}` : row.map.name }}
                    </span>
                    <Badge v-if="!row.child" class="bg-surface-strong text-body">
                      v{{ row.map.version }}
                    </Badge>
                    <!-- Older versions stay listed: they are what robots still
                         running them are running. -->
                    <button
                      v-if="!row.child && row.group.older.length"
                      type="button"
                      class="rounded-chip bg-surface-strong px-xxs text-caption text-muted transition-colors hover:text-ink"
                      @click="toggleGroup(row.group.key)"
                    >
                      +{{ row.group.older.length }} older
                    </button>
                  </div>
                  <!-- Truncated with the full text on hover: a note describing
                       why a version exists can be a sentence, and it must not
                       decide how wide the table is. -->
                  <p
                    class="truncate font-data text-caption text-muted"
                    :title="row.child ? (row.map.note ?? undefined) : undefined"
                  >
                    {{ row.child ? (row.map.note || gridLabel(row.map)) : gridLabel(row.map) }}
                  </p>
                </div>
              </div>
            </TableCell>

            <TableCell class="hidden lg:table-cell">
              <span class="whitespace-nowrap font-data text-body-sm text-body">
                {{ extentLabel(row.map) }}
              </span>
            </TableCell>

            <TableCell class="hidden xl:table-cell">
              <span class="whitespace-nowrap font-data text-body-sm text-body">
                {{ sizeLabel(row.map.imageBytes) }}
              </span>
            </TableCell>

            <TableCell>
              <!--
                Names, not bare dots: which robot runs which map is the question
                this column exists to answer, and a hover tooltip answers it for
                nobody on a touch screen. Two names, then a count.
              -->
              <div
                v-if="robotsOn(row.map.id).length"
                class="flex items-center gap-xs whitespace-nowrap"
                :title="robotsOn(row.map.id).map((r) => r.name).join(', ')"
              >
                <span
                  v-for="robot in robotsOn(row.map.id).slice(0, ROBOTS_SHOWN)"
                  :key="robot.id"
                  class="flex items-center gap-xxs text-body-sm text-body"
                >
                  <span
                    class="h-2 w-2 shrink-0 rounded-full"
                    :style="{ backgroundColor: `rgb(var(--robot-accent-${robot.accent}))` }"
                  />
                  {{ robot.name }}
                </span>
                <span
                  v-if="robotsOn(row.map.id).length > ROBOTS_SHOWN"
                  class="rounded-chip bg-surface-strong px-xxs text-caption text-muted"
                >
                  +{{ robotsOn(row.map.id).length - ROBOTS_SHOWN }}
                </span>
              </div>
              <span v-else class="text-body-sm text-muted-soft">—</span>
            </TableCell>

            <TableCell class="hidden xl:table-cell">
              <span class="whitespace-nowrap text-body-sm text-body">
                {{ robotName(row.map.createdByRobotId) }}
              </span>
            </TableCell>

            <TableCell align="right">
              <div class="flex justify-end gap-xxs">
                <!--
                  Assign stays outside the menu: it is the only action that
                  changes what a robot does, and it sits next to the column that
                  shows the current assignment. The rest are occasional.
                -->
                <Button
                  variant="ghost"
                  size="sm"
                  :title="`Assign ${row.map.name} v${row.map.version} to robots`"
                  @click="assigning = row.map"
                >
                  Assign
                </Button>
                <RowActions :label="`More actions for ${row.map.name} v${row.map.version}`">
                  <RowActionItem :icon="Pencil" @select="renaming = row.map">Rename</RowActionItem>
                  <RowActionItem :icon="Brush" :to="`/maps/edit/${row.map.id}`">
                    Edit cells
                  </RowActionItem>
                  <RowActionItem :icon="Download" :href="mapsApi.archiveUrl(row.map.id)" download>
                    Download
                  </RowActionItem>
                  <RowActionSeparator class="my-xxs h-px bg-hairline" />
                  <RowActionItem :icon="Trash2" destructive @select="askRemove(row.map)">
                    Remove
                  </RowActionItem>
                </RowActions>
              </div>
            </TableCell>
          </TableRow>
        </TableBody>

        <TableBody v-else>
          <TableRow>
            <TableCell colspan="6" class="h-auto p-base">
              <EmptyState
                title="No maps yet"
                description="Upload a .yaml and its image, or let a robot publish one after a mapping run."
              >
                <template #icon><MapIcon :size="20" class="text-muted" /></template>
                <template #action>
                  <div class="flex gap-xs">
                    <Button size="sm" @click="surveyOpen = true">
                      <ScanLine :size="14" /> Create map
                    </Button>
                    <Button size="sm" variant="secondary" @click="uploadOpen = true">
                      <Upload :size="14" /> Upload
                    </Button>
                  </div>
                </template>
              </EmptyState>
            </TableCell>
          </TableRow>
        </TableBody>
      </Table>

      <!-- "Page 1 of 1" says nothing; the pager appears once there is a second page. -->
      <Pagination
        v-if="!maps.error && !showSkeleton && groups.length > PAGE_SIZES[0]"
        :page="page"
        :page-size="pageSize"
        :total="groups.length"
        @update:page="page = $event"
        @update:page-size="onPageSize"
      />
    </Card>

    <StartSurveyDialog
      v-model:open="surveyOpen"
      :robots="fleet.robots"
      :link-for="links.stateFor"
      @select="startSurvey"
    />

    <MapUploadDialog
      v-model:open="uploadOpen"
      :pending="uploading"
      :server-error="uploadError"
      :existing-names="maps.maps.map((m) => m.name)"
      @submit="onUpload"
    />

    <RenameMapDialog
      :map="renaming"
      :maps="maps.maps"
      :busy="renamePending"
      :error="renameError"
      @update:open="closeRename"
      @submit="onRename"
    />

    <AssignMapDialog
      :open="assigning !== null"
      :map="assigning"
      :robots="fleet.robots"
      :pending="assignPending"
      :server-error="assignError"
      @update:open="(value: boolean) => !value && !assignPending && (assigning = null)"
      @submit="onAssign"
    />

    <ConfirmDialog
      :open="pendingRemoval !== null"
      destructive
      :pending="removing"
      :title="`Remove ${pendingRemoval?.name ?? ''} v${pendingRemoval?.version ?? ''}?`"
      :description="
        removalBlockedBy.length
          ? `This map is still assigned to ${removalBlockedBy.join(', ')}. Move those robots to another map first — the server will refuse while they are on it.`
          : 'This deletes the map and its files. Robots already running it keep running it until they are given another.'
      "
      :blocked="removalBlockedBy.length > 0"
      confirm-label="Remove"
      @update:open="(value: boolean) => !value && !removing && (pendingRemoval = null)"
      @cancel="pendingRemoval = null"
      @confirm="confirmRemoval"
    >
      <!--
        The way out of the refusal. Naming the robots without offering the fix
        leaves the operator to find the Assign button themselves, on a row they
        have already navigated away from.
      -->
      <template v-if="removalBlockedBy.length" #actions>
        <Button size="sm" variant="secondary" @click="reassignInsteadOfRemoving">
          Reassign robots
        </Button>
      </template>
    </ConfirmDialog>
  </div>
</template>
