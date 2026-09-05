# syntax=docker/dockerfile:1
#
# Built with bun, which is what the lockfile in this repository is for. The runtime image is
# nginx serving static files: there is no Node process in production, because the client is
# entirely static once the API base URL is baked in.

FROM oven/bun:1.3.5-alpine AS builder

WORKDIR /app

COPY package.json bun.lock ./
RUN bun install --frozen-lockfile

COPY tsconfig.json vite.config.ts index.html ./
COPY src ./src

# Vite inlines VITE_* variables at build time, so the API base URL is a build argument rather
# than a runtime one. Empty by default: the nginx config below proxies /api to the api service,
# so the bundle can use same-origin relative URLs and needs no CORS at all.
ARG VITE_API_BASE_URL=""
ENV VITE_API_BASE_URL=$VITE_API_BASE_URL

RUN bun run build


FROM nginx:1.29-alpine AS runtime

COPY --from=builder /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80

HEALTHCHECK --interval=15s --timeout=3s --start-period=5s --retries=3 \
    CMD wget --quiet --spider http://localhost/ || exit 1
