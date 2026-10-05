<script setup lang="ts">
/**
 * Table pagination bar.
 *
 * Always shows the range, even on a single page: "1–3 of 3" answers "is this
 * everything?", which is the question an operator actually has when they are
 * looking for a robot that should be in the list.
 *
 * Page-size control is a segmented group rather than a dropdown. Three fixed
 * options do not justify a portal, a focus trap and the listbox machinery that
 * comes with a real select.
 */
import { computed } from 'vue'
import { ChevronLeft, ChevronRight } from 'lucide-vue-next'
import { pageCount, pageRange, PAGE_SIZES } from '@/domain/pagination'
import { cn } from '@/shared/lib/utils'

const props = withDefaults(
  defineProps<{
    page: number
    pageSize: number
    total: number
    /** What an empty list reads as. */
    emptyLabel?: string
  }>(),
  { emptyLabel: 'No robots' },
)

const emit = defineEmits<{
  'update:page': [value: number]
  'update:pageSize': [value: number]
}>()

const pages = computed(() => pageCount(props.total, props.pageSize))
const range = computed(() => pageRange(props.page, props.pageSize, props.total))
const canPrev = computed(() => props.page > 1)
const canNext = computed(() => props.page < pages.value)

const summary = computed(() =>
  range.value.total === 0
    ? props.emptyLabel
    : `${range.value.from}–${range.value.to} of ${range.value.total}`,
)
</script>

<template>
  <div
    class="flex flex-wrap items-center justify-between gap-sm border-t border-hairline px-base py-sm"
  >
    <p class="font-data text-caption text-muted">{{ summary }}</p>

    <div class="flex items-center gap-base">
      <!-- Hidden below the smallest page size: choosing between 10, 25 and 50
           is meaningless when there are fewer than 10 rows. -->
      <div
        v-if="props.total > PAGE_SIZES[0]"
        class="hidden items-center gap-[2px] rounded-control bg-surface-strong p-[3px] sm:flex"
        role="radiogroup"
        aria-label="Rows per page"
      >
        <button
          v-for="size in PAGE_SIZES"
          :key="size"
          type="button"
          role="radio"
          :aria-checked="props.pageSize === size"
          :class="
            cn(
              'h-6 min-w-[28px] rounded-[6px] px-xs font-data text-caption transition-colors duration-150 ease-out',
              props.pageSize === size ? 'bg-surface text-ink' : 'text-muted hover:text-ink',
            )
          "
          @click="emit('update:pageSize', size)"
        >
          {{ size }}
        </button>
      </div>

      <div class="flex items-center gap-xs">
        <button
          type="button"
          aria-label="Previous page"
          :disabled="!canPrev"
          class="flex h-7 w-7 items-center justify-center rounded-control border border-hairline text-body transition-colors duration-150 ease-out hover:border-primary hover:text-primary disabled:cursor-not-allowed disabled:border-hairline disabled:text-muted-soft disabled:hover:text-muted-soft"
          @click="emit('update:page', props.page - 1)"
        >
          <ChevronLeft :size="14" />
        </button>

        <span class="min-w-[74px] text-center font-data text-caption text-body">
          Page {{ props.page }} of {{ pages }}
        </span>

        <button
          type="button"
          aria-label="Next page"
          :disabled="!canNext"
          class="flex h-7 w-7 items-center justify-center rounded-control border border-hairline text-body transition-colors duration-150 ease-out hover:border-primary hover:text-primary disabled:cursor-not-allowed disabled:border-hairline disabled:text-muted-soft disabled:hover:text-muted-soft"
          @click="emit('update:page', props.page + 1)"
        >
          <ChevronRight :size="14" />
        </button>
      </div>
    </div>
  </div>
</template>
