<script setup lang="ts">
/**
 * Per-topic health for one robot.
 *
 * The point of this table is to make "what exactly is broken" answerable. A
 * single Offline badge tells an operator to call someone; this tells them
 * whether the bridge is down, whether SLAM stopped, or whether the robot is
 * simply parked and quiet.
 *
 * The cadence column is what stops it lying: an event topic that has said
 * nothing all morning is healthy, and the table says so rather than painting
 * it amber.
 */
import { computed } from 'vue'
import type { Cadence, TopicHealth, TopicState } from '@/domain/ros/health'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/shared/ui/table'
import StatusBadge from '@/shared/components/StatusBadge.vue'
import EmptyState from '@/shared/components/EmptyState.vue'
import type { StatusTone } from '@/domain/types'

const props = defineProps<{ topics: TopicHealth[] }>()

const STATE_TONE: Record<TopicState, StatusTone> = {
  ok: 'success',
  waiting: 'neutral',
  stale: 'warning',
  idle: 'neutral',
}

const STATE_LABEL: Record<TopicState, string> = {
  ok: 'OK',
  waiting: 'Waiting',
  stale: 'Stale',
  idle: 'Not subscribed',
}

const CADENCE_HINT: Record<Cadence, string> = {
  periodic: 'Published on a timer. Silence past its budget is a fault.',
  event: 'Published only when something changes. Silence is normal.',
  latched: 'Delivered once on subscribe. Silence afterwards is normal.',
}

/** Full-tier topics first when they are active, so the interesting rows lead. */
const ordered = computed(() =>
  [...props.topics].sort((a, b) => {
    const rank = (t: TopicHealth) => (t.state === 'stale' ? 0 : t.state === 'waiting' ? 1 : 2)
    return rank(a) - rank(b) || a.label.localeCompare(b.label)
  }),
)

function lastSeen(topic: TopicHealth): string {
  if (topic.lastMessageAt === null) return '—'
  const seconds = Math.round((Date.now() - topic.lastMessageAt) / 1000)
  if (seconds < 1) return 'now'
  if (seconds < 60) return `${seconds}s ago`
  return `${Math.round(seconds / 60)}m ago`
}
</script>

<template>
  <EmptyState
    v-if="ordered.length === 0"
    title="No subscriptions"
    description="Nothing is subscribed for this robot. It is either muted or the connection has not opened yet."
    class="m-base"
  />

  <template v-else>
    <!--
    Phone: one row per topic — what it is, whether it is healthy, and the two
    numbers that say why. Cadence and the message count are for the table.
  -->
    <ul class="divide-y divide-hairline border-t border-hairline md:hidden">
      <li v-for="topic in ordered" :key="topic.key" class="px-base py-sm">
        <div class="flex items-center justify-between gap-sm">
          <span class="min-w-0 truncate text-body-md text-ink">
            {{ topic.label }}
            <span v-if="topic.tier === 'full'" class="ml-xxs text-label uppercase text-muted-soft">
              full
            </span>
          </span>
          <StatusBadge
            class="shrink-0"
            :tone="STATE_TONE[topic.state]"
            :label="STATE_LABEL[topic.state]"
          />
        </div>
        <p class="mt-[2px] font-data text-caption text-muted">
          {{ topic.rateHz === null ? '—' : `${topic.rateHz} Hz` }} · {{ lastSeen(topic) }}
        </p>
      </li>
    </ul>

    <div class="hidden md:block">
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Topic</TableHead>
            <TableHead>Cadence</TableHead>
            <TableHead align="right" class="hidden lg:table-cell">Messages</TableHead>
            <TableHead align="right">Rate</TableHead>
            <TableHead align="right">Last seen</TableHead>
            <TableHead>State</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          <TableRow v-for="topic in ordered" :key="topic.key">
            <TableCell>
              <span class="text-body-md text-ink">{{ topic.label }}</span>
              <span v-if="topic.tier === 'full'" class="ml-xs text-label uppercase text-muted-soft">
                full
              </span>
            </TableCell>
            <TableCell>
              <span class="text-body-sm text-muted" :title="CADENCE_HINT[topic.cadence]">
                {{ topic.cadence }}
              </span>
            </TableCell>
            <TableCell align="right" class="hidden lg:table-cell">
              <span class="font-data text-number-sm text-body">{{ topic.messages }}</span>
            </TableCell>
            <TableCell align="right">
              <span class="font-data text-number-sm text-body">
                {{ topic.rateHz === null ? '—' : `${topic.rateHz} Hz` }}
              </span>
            </TableCell>
            <TableCell align="right">
              <span class="font-data text-number-sm text-body">{{ lastSeen(topic) }}</span>
            </TableCell>
            <TableCell>
              <StatusBadge :tone="STATE_TONE[topic.state]" :label="STATE_LABEL[topic.state]" />
            </TableCell>
          </TableRow>
        </TableBody>
      </Table>
    </div>
  </template>
</template>
