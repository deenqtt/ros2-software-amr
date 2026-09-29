<script setup lang="ts">
/** Mirrors the real row geometry so the table does not jump when data lands. */
import { Skeleton } from '@/shared/ui/skeleton'
import { TableBody, TableCell, TableRow } from '@/shared/ui/table'

withDefaults(defineProps<{ rows?: number }>(), { rows: 3 })
</script>

<template>
  <TableBody>
    <TableRow v-for="row in rows" :key="row">
      <TableCell>
        <div class="flex items-center gap-sm">
          <Skeleton class="h-8 w-8" />
          <Skeleton class="h-4 w-32" />
        </div>
      </TableCell>
      <TableCell><Skeleton class="h-3.5 w-24" /></TableCell>
      <TableCell><Skeleton class="h-3.5 w-16" /></TableCell>
      <TableCell><Skeleton class="h-5 w-20" /></TableCell>
      <TableCell><Skeleton class="h-3.5 w-20" /></TableCell>
      <TableCell align="right">
        <div class="flex justify-end gap-xs">
          <Skeleton class="h-7 w-7" />
          <Skeleton class="h-7 w-7" />
        </div>
      </TableCell>
    </TableRow>
  </TableBody>
</template>
