<script setup lang="ts">
/**
 * Who changed what, and when. Super admins only.
 *
 * Answers the questions that come after an incident: who sent that robot, who
 * deleted the station, who tried to sign in as the supervisor at 3 a.m.
 *
 * Paged on the server, because a year of a busy floor is far more than a
 * browser should hold. Filters run there too, so "41–60 of 1,284" counts what
 * the filter matches rather than what happens to be loaded. The reading is
 * pinned when the log opens: records written while someone pages do not push
 * page 2's rows onto page 3. Reload starts a fresh reading.
 *
 * Every filter, the page and the page size live in the URL, so a refresh keeps
 * the view and a link to "Dina's refused sign-ins last week" can be sent on.
 */
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter, type LocationQuery } from 'vue-router'
import { watchDebounced } from '@vueuse/core'
import { Download, History, RefreshCw, Search, X } from 'lucide-vue-next'
import {
  auditApi,
  usersApi,
  type AuditEntry,
  type AuditKind,
  type AuditQuery,
  type UserAccount,
} from '@/shared/api/auth'
import { ROLE_LABEL } from '@/domain/auth'
import { PAGE_SIZES, pageCount } from '@/domain/pagination'
import { Button } from '@/shared/ui/button'
import { Card } from '@/shared/ui/card'
import { Select, type SelectOption } from '@/shared/ui/select'
import { Pagination } from '@/shared/ui/pagination'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/shared/ui/table'
import { Skeleton } from '@/shared/ui/skeleton'
import PanelToolbar from '@/shared/components/PanelToolbar.vue'
import StatusBadge from '@/shared/components/StatusBadge.vue'
import EmptyState from '@/shared/components/EmptyState.vue'
import type { StatusTone } from '@/domain/types'
import { alarmAge } from '@/features/alarm/alarmTime'
import { auditDate, auditLabel, auditOutcome, type AuditOutcome } from '../auditLabel'

const route = useRoute()
const router = useRouter()

// ── Filters, from and to the URL ───────────────────────────────────────────────

type Range = '24h' | '7d' | '30d' | 'all'
const RANGE_HOURS: Record<Exclude<Range, 'all'>, number> = { '24h': 24, '7d': 168, '30d': 720 }

const KINDS: SelectOption<AuditKind>[] = [
  { value: 'all', label: 'Everything' },
  { value: 'changes', label: 'Changes' },
  { value: 'sign-ins', label: 'Sign-ins' },
  { value: 'refused', label: 'Refused and failed' },
]
const RANGES: SelectOption<Range>[] = [
  { value: '24h', label: 'Last 24 hours' },
  { value: '7d', label: 'Last 7 days' },
  { value: '30d', label: 'Last 30 days' },
  { value: 'all', label: 'All time' },
]
const ANYONE = '__anyone'

function one(query: LocationQuery, key: string): string {
  const value = query[key]
  return typeof value === 'string' ? value : ''
}

function pick<T extends string>(value: string, allowed: readonly { value: T }[], fallback: T): T {
  return allowed.some((option) => option.value === value) ? (value as T) : fallback
}

const kind = ref<AuditKind>(pick(one(route.query, 'kind'), KINDS, 'all'))
const range = ref<Range>(pick(one(route.query, 'range'), RANGES, '7d'))
const person = ref<string>(one(route.query, 'user') || ANYONE)
const search = ref(one(route.query, 'q'))
const page = ref(Math.max(1, Number(one(route.query, 'page')) || 1))
const pageSize = ref<number>(
  PAGE_SIZES.find((size) => size === Number(one(route.query, 'size'))) ?? PAGE_SIZES[1],
)

const filtered = computed(
  () => kind.value !== 'all' || range.value !== '7d' || person.value !== ANYONE || !!search.value,
)

function clearFilters(): void {
  kind.value = 'all'
  range.value = '7d'
  person.value = ANYONE
  search.value = ''
}

function query(): AuditQuery {
  const hours = range.value === 'all' ? null : RANGE_HOURS[range.value]
  return {
    kind: kind.value,
    userId: person.value === ANYONE ? null : person.value,
    since: hours ? new Date(Date.now() - hours * 3_600_000).toISOString() : null,
    search: search.value,
  }
}

function syncUrl(): void {
  const next: Record<string, string> = {}
  if (kind.value !== 'all') next.kind = kind.value
  if (range.value !== '7d') next.range = range.value
  if (person.value !== ANYONE) next.user = person.value
  if (search.value.trim()) next.q = search.value.trim()
  if (page.value > 1) next.page = String(page.value)
  if (pageSize.value !== PAGE_SIZES[1]) next.size = String(pageSize.value)
  void router.replace({ query: next })
}

// ── People, for the filter ─────────────────────────────────────────────────────

const people = ref<UserAccount[]>([])
const personOptions = computed<SelectOption<string>[]>(() => [
  { value: ANYONE, label: 'Anyone' },
  ...people.value.map((user) => ({
    value: user.id,
    label: user.displayName || user.username,
    hint: ROLE_LABEL[user.role],
  })),
])

// ── Loading ────────────────────────────────────────────────────────────────────

const entries = ref<AuditEntry[]>([])
const total = ref(0)
const uptoId = ref<number | null>(null)
const loading = ref(false)
const loaded = ref(false)
const error = ref<string | null>(null)
let request = 0

async function load(options: { fresh?: boolean } = {}): Promise<void> {
  if (options.fresh) uptoId.value = null
  const mine = ++request
  loading.value = true
  error.value = null
  try {
    const result = await auditApi.page(query(), {
      limit: pageSize.value,
      offset: (page.value - 1) * pageSize.value,
      uptoId: uptoId.value,
    })
    // A slower answer to an older filter must not overwrite a newer one.
    if (mine !== request) return
    entries.value = result.items
    total.value = result.total
    uptoId.value = result.uptoId
    // Past the end, e.g. a link to page 9 of a filter that now has 3 pages.
    const last = pageCount(result.total, pageSize.value)
    if (page.value > last) {
      page.value = last
      return
    }
  } catch (cause) {
    if (mine !== request) return
    error.value = cause instanceof Error ? cause.message : 'Could not load the activity log.'
  } finally {
    if (mine === request) {
      loading.value = false
      loaded.value = true
    }
  }
}

/** A new filter is a new reading, from page 1. */
function refilter(): void {
  page.value = 1
  syncUrl()
  void load({ fresh: true })
}

watch([kind, range, person], refilter)
watchDebounced(search, refilter, { debounce: 300 })
watch(page, () => {
  syncUrl()
  void load()
})

function onPageSize(size: number): void {
  // Keep the first visible row on screen.
  const first = (page.value - 1) * pageSize.value
  pageSize.value = size
  page.value = Math.floor(first / size) + 1
  syncUrl()
  void load()
}

onMounted(() => {
  void load({ fresh: true })
  usersApi
    .list()
    .then((list) => (people.value = list))
    .catch(() => {
      // The filter simply offers "Anyone"; the log itself still loads.
    })
})

// ── Rows ───────────────────────────────────────────────────────────────────────

const OUTCOME: Record<AuditOutcome, { tone: StatusTone; label: string }> = {
  ok: { tone: 'success', label: 'Done' },
  refused: { tone: 'warning', label: 'Refused' },
  failed: { tone: 'fault', label: 'Failed' },
}

function when(entry: AuditEntry): string {
  return auditDate(entry.at).toLocaleString([], { dateStyle: 'medium', timeStyle: 'medium' })
}

function age(entry: AuditEntry): string {
  return alarmAge(auditDate(entry.at).getTime())
}

function who(entry: AuditEntry): string {
  if (entry.username === 'agent' && !entry.userId) return 'Robot agent'
  return entry.username ?? 'Unknown'
}

const exportHref = computed(() => auditApi.exportUrl(query()))
const showSkeleton = computed(() => loading.value && !loaded.value)
</script>

<template>
  <div class="p-sm sm:p-base md:p-lg">
    <Card>
      <PanelToolbar title="Activity" subtitle="Changes made through the app, and every sign-in">
        <template #icon><History :size="14" class="shrink-0 text-muted" /></template>
        <template #actions>
          <Button
            variant="outline"
            size="icon"
            title="Reload, including anything new"
            :disabled="loading"
            @click="load({ fresh: true })"
          >
            <RefreshCw :size="15" :class="loading && 'animate-spin'" />
          </Button>
          <Button variant="outline" as-child>
            <a :href="exportHref" download title="Download what this filter matches, as CSV">
              <Download :size="15" />
              <span>Export CSV</span>
            </a>
          </Button>
        </template>
      </PanelToolbar>

      <!-- Filters. Wrap on narrow screens; search takes what width is left. -->
      <div class="flex flex-wrap items-center gap-xs border-b border-hairline px-base py-sm">
        <label class="relative w-full min-w-[12rem] flex-1 sm:w-auto">
          <span class="sr-only">Search</span>
          <Search
            :size="14"
            class="pointer-events-none absolute left-sm top-1/2 -translate-y-1/2 text-muted"
          />
          <input
            v-model="search"
            type="search"
            placeholder="Search names, pages, addresses…"
            class="h-control-sm w-full rounded-control border border-hairline bg-surface pl-[30px] pr-sm text-body-sm text-ink outline-none transition-colors placeholder:text-muted-soft hover:border-primary focus:border-primary"
          />
        </label>
        <Select v-model="kind" :options="KINDS" label="What" class="w-full sm:w-[11rem]" />
        <Select v-model="person" :options="personOptions" label="Who" class="w-full sm:w-[11rem]" />
        <Select v-model="range" :options="RANGES" label="When" class="w-full sm:w-[10rem]" />
        <Button v-if="filtered" variant="ghost" size="sm" @click="clearFilters">
          <X :size="13" /> Clear
        </Button>
      </div>

      <div v-if="error" class="p-base">
        <EmptyState title="Could not load the activity log" :description="error">
          <template #action>
            <Button size="sm" variant="secondary" @click="load()">Try again</Button>
          </template>
        </EmptyState>
      </div>

      <template v-else>
        <!-- Phone: one stacked row per record; the five columns do not fit. -->
        <ul
          class="divide-y divide-hairline md:hidden"
          :class="loading && loaded ? 'opacity-60 transition-opacity' : undefined"
        >
          <li v-for="entry in entries" :key="entry.id" class="px-base py-sm">
            <div class="flex items-start justify-between gap-sm">
              <p class="min-w-0 text-body-sm font-medium text-ink">{{ auditLabel(entry) }}</p>
              <StatusBadge
                class="shrink-0"
                :tone="OUTCOME[auditOutcome(entry.status)].tone"
                :label="OUTCOME[auditOutcome(entry.status)].label"
              />
            </div>
            <p class="mt-[2px] text-caption text-muted">
              {{ who(entry)
              }}<template v-if="entry.role"> · {{ ROLE_LABEL[entry.role] }}</template> ·
              <span :title="when(entry)">{{ age(entry) }}</span>
            </p>
          </li>
          <li v-if="showSkeleton" class="space-y-sm p-base">
            <Skeleton v-for="row in 5" :key="row" class="h-[36px] w-full" />
          </li>
          <li v-else-if="!loading && entries.length === 0" class="p-base">
            <EmptyState
              :title="filtered ? 'Nothing matches these filters' : 'No activity in the last 7 days'"
              description="Try a longer time range, or clear the filters."
            />
          </li>
        </ul>

        <div class="hidden md:block">
          <Table :class="loading && loaded ? 'opacity-60 transition-opacity' : undefined">
            <TableHeader>
              <TableRow>
                <TableHead class="whitespace-nowrap">When</TableHead>
                <TableHead class="whitespace-nowrap">Who</TableHead>
                <TableHead class="w-full">What</TableHead>
                <TableHead class="whitespace-nowrap">Result</TableHead>
                <TableHead class="hidden whitespace-nowrap lg:table-cell">From</TableHead>
              </TableRow>
            </TableHeader>

            <TableBody v-if="showSkeleton">
              <TableRow v-for="row in 6" :key="row">
                <TableCell colspan="5"><Skeleton class="h-[18px] w-full" /></TableCell>
              </TableRow>
            </TableBody>

            <TableBody v-else>
              <TableRow v-for="entry in entries" :key="entry.id">
                <TableCell class="whitespace-nowrap">
                  <p class="font-data text-body-sm text-body">{{ when(entry) }}</p>
                  <p class="text-caption text-muted">{{ age(entry) }}</p>
                </TableCell>
                <TableCell class="whitespace-nowrap">
                  <p class="text-body-sm text-ink">{{ who(entry) }}</p>
                  <p v-if="entry.role" class="text-caption text-muted">
                    {{ ROLE_LABEL[entry.role] }}
                  </p>
                </TableCell>
                <TableCell class="w-full max-w-0">
                  <p class="truncate text-body-sm text-ink">{{ auditLabel(entry) }}</p>
                  <p
                    v-if="entry.path"
                    class="truncate font-ident text-caption text-muted"
                    :title="`${entry.method ?? ''} ${entry.path}`"
                  >
                    {{ entry.method }} {{ entry.path }}
                  </p>
                </TableCell>
                <TableCell class="whitespace-nowrap">
                  <StatusBadge
                    :tone="OUTCOME[auditOutcome(entry.status)].tone"
                    :label="OUTCOME[auditOutcome(entry.status)].label"
                    :title="entry.status ? `HTTP ${entry.status}` : undefined"
                  />
                </TableCell>
                <TableCell class="hidden whitespace-nowrap lg:table-cell">
                  <span class="font-ident text-caption text-muted">{{ entry.ip ?? '—' }}</span>
                </TableCell>
              </TableRow>

              <TableRow v-if="!loading && entries.length === 0">
                <TableCell colspan="5" class="h-auto p-base">
                  <EmptyState
                    :title="
                      filtered ? 'Nothing matches these filters' : 'No activity in the last 7 days'
                    "
                    :description="
                      filtered
                        ? 'Try a longer time range, or clear the filters.'
                        : 'Every change made through this app, and every sign-in attempt, is recorded here.'
                    "
                  >
                    <template #icon><History :size="20" class="text-muted" /></template>
                    <template v-if="filtered" #action>
                      <Button size="sm" variant="secondary" @click="clearFilters">
                        Clear filters
                      </Button>
                    </template>
                  </EmptyState>
                </TableCell>
              </TableRow>
            </TableBody>
          </Table>
        </div>

        <Pagination
          v-if="loaded && total > 0"
          :page="page"
          :page-size="pageSize"
          :total="total"
          empty-label="No records"
          @update:page="page = $event"
          @update:page-size="onPageSize"
        />
      </template>
    </Card>
  </div>
</template>
