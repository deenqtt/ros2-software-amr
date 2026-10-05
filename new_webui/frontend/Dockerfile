# The web UI: built once, served by nginx, which also proxies /backend/ to the
# backend container. One origin for the browser, so the sign-in cookie works
# and CORS never applies. See new_webui/deploy/docker-compose.yml.

# ── Build ─────────────────────────────────────────────────────────────────────
# The output is plain files, so it is built on the runner's own platform even
# when the final image is for another one.
FROM --platform=$BUILDPLATFORM node:22-alpine AS build
WORKDIR /src

COPY package.json package-lock.json ./
RUN npm ci --no-audit --no-fund

COPY . .
# Relative URLs only: the same image works under any host name or IP. Set
# here rather than read from an .env file, which is not in the repository.
ENV VITE_API_BASE_URL=/backend/api \
    VITE_API_STATIC_URL=/backend \
    VITE_DEFAULT_ROS_URL=ws://192.168.10.21:9090 \
    VITE_DEFAULT_CAMERA_PORT=8080 \
    VITE_DEV_LATENCY_MS=0
RUN npm run build

# ── Serve ─────────────────────────────────────────────────────────────────────
# Unprivileged nginx: listens on 8080 and runs as a non-root user.
FROM nginxinc/nginx-unprivileged:1.27-alpine

# Where /backend/ is proxied to. The compose service name by default.
ENV AMR_BACKEND_URL=http://backend:3002

# Mounted per site for extra locations (robots). Exists empty so the include
# in the template matches nothing rather than failing.
USER root
RUN mkdir -p /etc/nginx/amr.d
USER nginx

COPY nginx/default.conf.template /etc/nginx/templates/default.conf.template
COPY --from=build /src/dist /usr/share/nginx/html

EXPOSE 8080

HEALTHCHECK --interval=15s --timeout=3s --start-period=5s --retries=3 \
    CMD wget -qO- http://127.0.0.1:8080/healthz >/dev/null || exit 1
