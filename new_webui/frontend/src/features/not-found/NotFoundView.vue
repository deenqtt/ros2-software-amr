<script setup lang="ts">
/**
 * Not found.
 *
 * Outside the app shell on purpose: a sidebar around a dead end suggests the
 * page is a place in the app, and its highlighted item points at nothing. One
 * clear way home, a way back, and the main destinations one click away.
 *
 * The wording follows the usual error-message rules (Nielsen's ninth
 * heuristic): plain language, says exactly what was not found, does not blame
 * whoever typed it, and offers the next step.
 */
import { computed } from 'vue'
import { RouterLink, useRoute, useRouter } from 'vue-router'
import { ArrowLeft, LayoutDashboard } from 'lucide-vue-next'
import BrandMark from '@/shared/components/BrandMark.vue'
import { NAV_GROUPS } from '@/app/navigation'
import { Button } from '@/shared/ui/button'

const route = useRoute()
const router = useRouter()

/** The address that was asked for, as typed. */
const requested = computed(() => route.fullPath)

/** Only offer "back" when there is a page of this app to go back to. */
const canGoBack = computed(() => {
  const state = window.history.state as { back?: string | null } | null
  return Boolean(state?.back)
})

/** Every destination except the dashboard, which already has its own button. */
const shortcuts = NAV_GROUPS.flatMap((group) => group.items).filter(
  (item) => item.to !== '/dashboard' && !item.role,
)
</script>

<template>
  <div class="flex min-h-full flex-col bg-canvas">
    <header class="flex items-center px-base py-sm sm:px-lg">
      <RouterLink to="/dashboard" class="flex items-center gap-sm text-title-sm text-ink">
        <BrandMark :size="32" />
        AMR Control
      </RouterLink>
    </header>

    <main class="flex flex-1 items-center justify-center px-base pb-xl pt-base sm:px-lg">
      <div class="w-full max-w-[40rem] text-center">
        <!--
          A robot off its map: a short planned path that runs out at a cell
          nobody has surveyed. Drawn with the same marks the map screens use —
          a filled dot with a heading tick, a dashed route — so it reads as this
          app's map rather than stock art.
        -->
        <svg
          viewBox="0 0 360 200"
          class="mx-auto mb-lg w-full max-w-[22rem]"
          role="img"
          aria-label="A robot whose route runs off the edge of its map"
        >
          <defs>
            <pattern id="nf-grid" width="20" height="20" patternUnits="userSpaceOnUse">
              <path d="M20 0H0V20" fill="none" style="stroke: rgb(var(--hairline-soft))" />
            </pattern>
          </defs>

          <rect
            x="1"
            y="1"
            width="358"
            height="198"
            rx="16"
            fill="url(#nf-grid)"
            style="stroke: rgb(var(--hairline))"
          />

          <!-- Walls of the part of the floor that is mapped. -->
          <g fill="none" stroke-width="4" stroke-linecap="round" style="stroke: rgb(var(--ink))">
            <path d="M40 30V170H150" />
            <path d="M40 30H210" />
            <path d="M110 30V95" />
          </g>

          <!-- Unknown territory: where the map simply stops. -->
          <rect
            x="230"
            y="20"
            width="120"
            height="160"
            rx="10"
            style="fill: rgb(var(--surface-strong))"
          />

          <!-- The planned route, running out into it. -->
          <path
            class="nf-route"
            d="M80 130 C 130 130, 150 75, 205 85 S 252 104, 268 101"
            fill="none"
            stroke-width="3"
            stroke-linecap="round"
            stroke-dasharray="2 9"
            style="stroke: rgb(var(--primary))"
          />

          <!-- Where it was meant to go. -->
          <circle
            cx="290"
            cy="100"
            r="20"
            fill="none"
            stroke-width="2"
            stroke-dasharray="4 5"
            style="stroke: rgb(var(--muted))"
          />
          <text
            x="290"
            y="108"
            text-anchor="middle"
            font-size="22"
            font-weight="600"
            style="fill: rgb(var(--muted))"
          >
            ?
          </text>

          <!-- The robot, with its heading. -->
          <circle class="nf-pulse" cx="80" cy="130" r="16" style="fill: rgb(var(--primary) / 0.15)" />
          <circle cx="80" cy="130" r="9" style="fill: rgb(var(--primary))" />
          <path
            d="M80 130H97"
            stroke-width="3"
            stroke-linecap="round"
            style="stroke: rgb(var(--primary))"
          />
        </svg>

        <p class="text-label uppercase text-muted">Error 404</p>
        <h1 class="mt-xs text-display-sm text-ink">This page isn't on the map</h1>
        <p class="mx-auto mt-sm max-w-[28rem] text-body-md text-body">
          Nothing lives at
          <code
            class="break-all rounded-[4px] bg-surface-strong px-[6px] py-[1px] font-data text-body-sm text-ink"
            >{{ requested }}</code
          >. The link may be out of date, or the address mistyped.
        </p>

        <div class="mt-lg flex flex-wrap items-center justify-center gap-xs">
          <Button as-child>
            <RouterLink to="/dashboard">
              <LayoutDashboard :size="15" />
              Go to dashboard
            </RouterLink>
          </Button>
          <Button v-if="canGoBack" variant="outline" @click="router.back()">
            <ArrowLeft :size="15" />
            Go back
          </Button>
        </div>

        <!-- The usual next stops, since there is no sidebar here to offer them. -->
        <nav aria-label="Main destinations" class="mt-xl">
          <p class="text-caption text-muted">Or jump to</p>
          <ul class="mt-sm flex flex-wrap justify-center gap-xs">
            <li v-for="item in shortcuts" :key="item.to">
              <RouterLink
                :to="item.to"
                class="flex items-center gap-xs rounded-control border border-hairline px-sm py-xs text-body-sm text-body transition-colors hover:border-primary hover:text-ink"
              >
                <component :is="item.icon" :size="14" class="text-muted" />
                {{ item.label }}
              </RouterLink>
            </li>
          </ul>
        </nav>
      </div>
    </main>
  </div>
</template>

<style scoped>
/* Motion only for those who have not asked the system for less. */
@media (prefers-reduced-motion: no-preference) {
  .nf-route {
    animation: nf-march 1.6s linear infinite;
  }
  .nf-pulse {
    transform-origin: 80px 130px;
    animation: nf-pulse 2.4s ease-out infinite;
  }
}

@keyframes nf-march {
  to {
    stroke-dashoffset: -22;
  }
}

@keyframes nf-pulse {
  0% {
    transform: scale(0.7);
    opacity: 1;
  }
  100% {
    transform: scale(1.6);
    opacity: 0;
  }
}
</style>
