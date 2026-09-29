import { fileURLToPath, URL } from 'node:url'
// vitest/config re-exports Vite's defineConfig with the `test` block typed.
import { defineConfig } from 'vitest/config'
import vue from '@vitejs/plugin-vue'

export default defineConfig({
  plugins: [vue()],
  resolve: {
    alias: { '@': fileURLToPath(new URL('./src', import.meta.url)) },
  },
  server: {
    // 3100 so this can run alongside the existing web-ui on 3000
    port: 3100,
    host: '0.0.0.0',
  },
  // Routes are lazy-imported, so Rollup already splits per screen. Explicit
  // manualChunks for leaflet / roslib / uplot go back in once the map and ROS
  // layers actually import them — right now they would only emit empty chunks.
  test: {
    environment: 'jsdom',
    include: ['src/**/*.spec.ts'],
    // Tests must not inherit the local .env dev aids. VITE_DEV_LATENCY_MS is a
    // deliberate delay for eyeballing loading states; leaving it on here would
    // make every mounted component start in its skeleton state.
    env: { VITE_DEV_LATENCY_MS: '0' },
  },
})
