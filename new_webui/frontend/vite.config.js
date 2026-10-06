import { fileURLToPath, URL } from 'node:url';
// vitest/config re-exports Vite's defineConfig with the `test` block typed.
import { defineConfig } from 'vitest/config';
import { loadEnv } from 'vite';
import vue from '@vitejs/plugin-vue';
// Where the dev server forwards /backend. Same layout as production behind
// nginx, so the session cookie is same-origin in development too, and the UI
// opened from another laptop (http://<this-ip>:3100) still reaches the API.
const devBackend = loadEnv(process.env.NODE_ENV ?? 'development', process.cwd(), 'VITE_').VITE_DEV_BACKEND ||
    'http://localhost:3002';
// roslib opens with `var ROSLIB = this.ROSLIB || {…}`. Bundled as CommonJS for
// production, that `this` becomes the module's exports before they exist, so a
// production build crashed the moment a robot connection was made ("Cannot
// read properties of undefined (reading 'ROSLIB')"). The dev server's prebundle
// does not, which is how it went unnoticed. The global object is what roslib
// means there.
const roslibGlobalThis = {
    name: 'roslib-global-this',
    enforce: 'pre',
    transform(code, id) {
        if (!id.replaceAll('\\', '/').endsWith('/node_modules/roslib/src/RosLib.js'))
            return null;
        return code.replace('this.ROSLIB', 'globalThis.ROSLIB');
    },
};
export default defineConfig({
    plugins: [vue(), roslibGlobalThis],
    resolve: {
        alias: { '@': fileURLToPath(new URL('./src', import.meta.url)) },
    },
    server: {
        // 3100 so this can run alongside the existing web-ui on 3000
        port: 3100,
        host: '0.0.0.0',
        proxy: {
            '/backend': {
                target: devBackend,
                rewrite: (path) => path.replace(/^\/backend/, ''),
            },
        },
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
});
