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
# AMR_HTTPS_PORT: the public HTTPS port, for the HTTP→HTTPS redirect (TLS only).
ENV AMR_BACKEND_URL=http://backend:3002 \
    AMR_HTTPS_PORT=443

# Mounted per site for extra locations (robots). Exists empty so the include
# in the template matches nothing rather than failing.
USER root
RUN mkdir -p /etc/nginx/amr.d
USER nginx

# Two sets of templates, both rendered into /etc/nginx/conf.d at start-up:
#   /etc/nginx/templates      plain HTTP on 8080 (the default)
#   /etc/nginx/templates-tls  HTTPS on 8443, 8080 redirects to it; chosen with
#                             NGINX_ENVSUBST_TEMPLATE_DIR (deploy/docker-compose.tls.yml)
# Both share locations.inc.template, and the security headers.
COPY nginx/default.conf.template nginx/locations.inc.template /etc/nginx/templates/
COPY nginx/tls.conf.template /etc/nginx/templates-tls/default.conf.template
COPY nginx/locations.inc.template /etc/nginx/templates-tls/
COPY nginx/security-headers.conf /etc/nginx/amr/security-headers.conf
# Error pages: static HTML/CSS/JS plus JSON bodies for /backend/. Outside the
# app's root so a release of the app can never shadow or remove them.
COPY nginx/errors/ /usr/share/nginx/amr-errors/
COPY --from=build /src/dist /usr/share/nginx/html

EXPOSE 8080

HEALTHCHECK --interval=15s --timeout=3s --start-period=5s --retries=3 \
    CMD wget -qO- http://127.0.0.1:8080/healthz >/dev/null || exit 1
