<script setup lang="ts">
/**
 * The AMR Control mark (docs/brand/amr-control/concept-b-route.svg).
 *
 * An A drawn as a route: two legs between stations, the apex is the
 * destination, the dashed bar the path Nav2 plans. Inline rather than an <img>
 * so it takes the theme's primary (slightly lifted in dark mode) and needs no
 * request. Decorative: the product name always sits next to it.
 */
withDefaults(defineProps<{ size?: number }>(), { size: 32 })
</script>

<template>
  <svg
    :width="size"
    :height="size"
    viewBox="0 0 128 128"
    aria-hidden="true"
    focusable="false"
    class="shrink-0"
  >
    <rect width="128" height="128" rx="28" style="fill: rgb(var(--primary))" />
    <path
      d="M33 99L64 31L95 99"
      fill="none"
      stroke="#fff"
      stroke-width="10"
      stroke-linecap="round"
      stroke-linejoin="round"
    />
    <path
      d="M46 77H82"
      fill="none"
      stroke="#fff"
      stroke-width="7"
      stroke-linecap="round"
      stroke-dasharray="1 12"
      opacity="0.85"
    />
    <circle cx="33" cy="99" r="9" fill="#fff" />
    <circle cx="95" cy="99" r="9" fill="#fff" />
    <circle cx="64" cy="31" r="12" stroke="#fff" stroke-width="6" style="fill: rgb(var(--primary))" />
  </svg>
</template>
