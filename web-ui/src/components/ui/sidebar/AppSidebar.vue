<template>
  <aside
    :class="[
      'flex flex-col h-full border-r border-border bg-sidebar shrink-0 overflow-hidden',
      collapsed ? 'w-[60px]' : 'w-[220px]'
    ]"
    style="transition: width 200ms cubic-bezier(0.23, 1, 0.32, 1);"
  >
    <!-- Nav items -->
    <nav class="flex-1 p-2 pt-3 space-y-0.5 overflow-hidden">
      <!-- Section label -->
      <div
        v-if="!collapsed"
        class="px-2.5 pb-1.5 text-[9px] font-bold tracking-widest text-sidebar-foreground/30 uppercase"
      >
        Navigation
      </div>

      <button
        v-for="item in items"
        :key="item.id"
        @click="$emit('select', item.id)"
        :title="item.label"
        :class="[
          'w-full flex items-center gap-3 px-2.5 py-2 rounded-md text-sm',
          'transition-[background-color,color,transform] duration-150 active:scale-[0.97]',
          active === item.id
            ? 'bg-sidebar-accent text-sidebar-foreground font-medium'
            : 'text-sidebar-foreground/50 hover:text-sidebar-foreground hover:bg-sidebar-accent/60',
          collapsed && 'justify-center px-0'
        ]"
      >
        <component :is="item.icon" :size="16" class="shrink-0" />
        <span v-if="!collapsed" class="truncate text-xs">{{ item.label }}</span>
      </button>
    </nav>

    <!-- Footer: connection status -->
    <div class="p-2 border-t border-border/60">
      <div
        :class="[
          'flex items-center gap-2.5 px-2.5 py-2 rounded-md',
          collapsed && 'justify-center px-0'
        ]"
      >
        <span
          :class="[
            'w-2 h-2 rounded-full shrink-0 transition-colors duration-300',
            connected ? 'bg-amr-ok animate-glow-ok' : 'bg-muted-foreground/40'
          ]"
        />
        <span v-if="!collapsed" class="text-[11px] text-muted-foreground/60 font-medium">
          {{ connected ? 'Connected' : 'Offline' }}
        </span>
      </div>
    </div>
  </aside>
</template>

<script setup>
defineProps({
  items:     { type: Array,   required: true },
  active:    { type: String,  default: '' },
  collapsed: { type: Boolean, default: false },
  connected: { type: Boolean, default: false },
})

defineEmits(['select'])
</script>
