<script setup lang="ts">
/**
 * Loading state for the robot table.
 *
 * Mirrors the real row geometry — same heights, same column widths — so the
 * table does not jump when the data arrives.
 */
import { Skeleton } from '@/shared/ui/skeleton'
import { TableBody, TableCell, TableRow } from '@/shared/ui/table'

withDefaults(defineProps<{ rows?: number }>(), { rows: 3 })
</script>

<template>
  <TableBody>
    <TableRow v-for="row in rows" :key="row">
      <TableCell>
        <div class="flex items-center gap-sm">
          <Skeleton class="h-8 w-8 rounded-full" />
          <Skeleton class="h-4 w-28" />
        </div>
      </TableCell>
      <TableCell><Skeleton class="h-3.5 w-44" /></TableCell>
      <TableCell class="hidden lg:table-cell"><Skeleton class="h-3.5 w-10" /></TableCell>
      <TableCell><Skeleton class="h-5 w-24 rounded-chip" /></TableCell>
      <TableCell><Skeleton class="h-3.5 w-16" /></TableCell>
      <TableCell align="right">
        <div class="flex justify-end gap-xs">
          <Skeleton class="h-7 w-7 rounded-full" />
          <Skeleton class="h-7 w-7 rounded-full" />
        </div>
      </TableCell>
    </TableRow>
  </TableBody>
</template>
