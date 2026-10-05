<script setup lang="ts">
/**
 * A card whose body can be folded away, with its state summed up in the header.
 *
 * For settings and reference material that a phone should not spend a screen
 * on: closed by default on a phone, open on wider screens, and the header says
 * enough ("Monitoring: On") that most visits never need to open it.
 */
import { computed, ref, useId } from 'vue'
import { ChevronRight } from 'lucide-vue-next'
import { useUiStore } from '@/stores/ui'
import { cn } from '@/shared/lib/utils'

const props = withDefaults(
  defineProps<{
    title: string
    /** Shown beside the title, mostly while folded. */
    summary?: string
    /**
     * Overrides the phone-closed, wider-open default. Null means "use that
     * default": a plain optional boolean prop would be cast to false when
     * left out, and every section would start folded on every screen.
     */
    defaultOpen?: boolean | null
    class?: string
  }>(),
  { defaultOpen: null },
)

const ui = useUiStore()
/** Follows the screen (phone closed, wider open) until someone chooses. */
const chosen = ref<boolean | null>(null)
const open = computed(() => chosen.value ?? props.defaultOpen ?? ui.screen !== 'phone')
const bodyId = useId()
</script>

<template>
  <section :class="cn('rounded-surface border border-hairline bg-surface', props.class)">
    <div class="flex items-center gap-xs pr-base">
      <button
        type="button"
        :aria-expanded="open"
        :aria-controls="bodyId"
        class="flex min-w-0 flex-1 items-center gap-xs py-base pl-base text-left touch:min-h-[52px]"
        @click="chosen = !open"
      >
        <ChevronRight
          :size="14"
          :class="cn('shrink-0 text-muted transition-transform', open && 'rotate-90')"
        />
        <h2 class="text-label uppercase text-muted">{{ props.title }}</h2>
        <span v-if="props.summary" class="min-w-0 truncate text-body-sm text-body">
          {{ props.summary }}
        </span>
      </button>
      <slot name="actions" />
    </div>
    <div v-show="open" :id="bodyId" class="px-base pb-base">
      <slot />
    </div>
  </section>
</template>
