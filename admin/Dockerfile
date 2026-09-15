# ---------------------------------------------------------------------------
# NeoStore admin console. Build the SPA, then serve the files with nginx.
#
# There is no runtime configuration to inject: `src/lib/api.ts` calls `/api/v1`
# on the same origin, and Caddy (or Vite's dev proxy) owns that prefix. That is
# what keeps one build artefact valid in every environment.
# ---------------------------------------------------------------------------

FROM node:22-alpine AS builder
WORKDIR /app
COPY package.json package-lock.json* ./
RUN npm ci --no-audit --no-fund
COPY . .
RUN npm run build

FROM nginx:1.27-alpine AS runner
COPY nginx.conf /etc/nginx/conf.d/default.conf
# The build emits `/admin/...` asset paths, so the files live under `/admin/`
# and nginx's root stays where it is.
COPY --from=builder /app/dist /usr/share/nginx/html/admin
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
