/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_API_BASE_URL?: string
  readonly VITE_API_STATIC_URL?: string
  readonly VITE_DEFAULT_ROS_URL?: string
  readonly VITE_DEFAULT_CAMERA_PORT?: string
  readonly VITE_DEV_LATENCY_MS?: string
}

interface ImportMeta {
  readonly env: ImportMetaEnv
}

declare module '*.vue' {
  import type { DefineComponent } from 'vue'
  const component: DefineComponent<Record<string, unknown>, Record<string, unknown>, unknown>
  export default component
}

// roslib's ambient types live in src/types/roslib.d.ts.
