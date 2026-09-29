<script setup lang="ts" generic="T extends string">
/**
 * A chooser that matches the rest of the interface.
 *
 * A native <select> was the only unstyled control in the application: it takes
 * the operating system's font, height and focus ring, so it reads as a hole in
 * the page rather than as a control. It also cannot show anything but text,
 * while the things chosen here — a map version, a robot, a station type — are
 * clearer with a badge or a colour beside them.
 */
import {
  SelectContent,
  SelectItem,
  SelectItemText,
  SelectPortal,
  SelectRoot,
  SelectTrigger,
  SelectValue,
  SelectViewport,
} from 'reka-ui'
import { ChevronDown } from 'lucide-vue-next'
import { cn } from '@/shared/lib/utils'

export interface SelectOption<V extends string> {
  value: V
  label: string
  /** Secondary text, shown in the list but not in the trigger. */
  hint?: string
  disabled?: boolean
}

const props = defineProps<{
  modelValue: T | null
  options: readonly SelectOption<T>[]
  placeholder?: string
  disabled?: boolean
  /** Names the control for screen readers, since there is no visible <label>. */
  label: string
  class?: string
}>()

const emit = defineEmits<{ 'update:modelValue': [value: T] }>()
</script>

<template>
  <SelectRoot
    :model-value="props.modelValue ?? undefined"
    :disabled="props.disabled"
    @update:model-value="emit('update:modelValue', $event as T)"
  >
    <SelectTrigger
      :aria-label="props.label"
      :class="
        cn(
          'flex h-control-sm items-center gap-xs rounded-control border border-hairline bg-surface px-sm text-body-sm text-ink transition-colors',
          'hover:border-primary focus:outline-none focus-visible:ring-2 focus-visible:ring-primary/40',
          'disabled:cursor-not-allowed disabled:text-muted-soft disabled:opacity-60',
          props.class,
        )
      "
    >
      <SelectValue :placeholder="props.placeholder ?? 'Choose…'" class="truncate" />
      <ChevronDown :size="13" class="ml-auto shrink-0 text-muted" />
    </SelectTrigger>

    <SelectPortal>
      <SelectContent
        position="popper"
        :side-offset="4"
        class="z-50 max-h-[18rem] min-w-[var(--reka-select-trigger-width)] overflow-hidden rounded-surface border border-hairline bg-surface p-xxs shadow-soft"
      >
        <SelectViewport>
          <SelectItem
            v-for="option in props.options"
            :key="option.value"
            :value="option.value"
            :disabled="option.disabled"
            class="flex cursor-pointer flex-col rounded-control px-sm py-xs text-body-sm text-body outline-none transition-colors data-[highlighted]:bg-surface-strong data-[state=checked]:text-ink data-[disabled]:cursor-not-allowed data-[disabled]:opacity-40"
          >
            <SelectItemText>{{ option.label }}</SelectItemText>
            <span v-if="option.hint" class="text-caption text-muted-soft">{{ option.hint }}</span>
          </SelectItem>
        </SelectViewport>
      </SelectContent>
    </SelectPortal>
  </SelectRoot>
</template>
