<script setup lang="ts">
/**
 * Loading state for the mission table.
 *
 * Same columns and row height as the real rows — a name over a route line —
 * so nothing jumps when the list arrives.
 */
import { Skeleton } from '@/shared/ui/skeleton'
import { TableBody, TableCell, TableRow } from '@/shared/ui/table'

withDefaults(defineProps<{ rows?: number }>(), { rows: 3 })

/** Varied, so three placeholder rows do not read as three identical routes. */
const NAME_WIDTHS = ['w-32', 'w-24', 'w-40']
const ROUTE_WIDTHS = ['w-56', 'w-40', 'w-48']
</script>

<template>
  <TableBody>
    <TableRow v-for="row in rows" :key="row">
      <TableCell class="w-full max-w-0">
        <div class="space-y-xs py-xxs">
          <Skeleton :class="`h-4 ${NAME_WIDTHS[(row - 1) % 3]}`" />
          <div class="flex items-center gap-xs">
            <Skeleton class="h-2.5 w-2.5 rounded-full" />
            <Skeleton :class="`h-3 ${ROUTE_WIDTHS[(row - 1) % 3]}`" />
          </div>
        </div>
      </TableCell>
      <TableCell><Skeleton class="h-5 w-16 rounded-chip" /></TableCell>
      <TableCell><Skeleton class="h-3.5 w-24" /></TableCell>
      <TableCell align="right">
        <div class="flex justify-end gap-xs">
          <Skeleton class="h-7 w-14" />
          <Skeleton class="h-7 w-14" />
          <Skeleton class="h-7 w-7" />
        </div>
      </TableCell>
    </TableRow>
  </TableBody>
</template>
