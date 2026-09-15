# ---------------------------------------------------------------------------
# NeoStore storefront. Three stages: install, build, run.
#
# The `NEXT_PUBLIC_*` values are baked in at build time — Next inlines them into
# the client bundle — so they are build args, not runtime env. Anything that
# holds a secret must NOT be passed this way.
# ---------------------------------------------------------------------------

FROM node:22-alpine AS deps
WORKDIR /app
# Defaults to the canonical registry; a build behind a slow or blocked route to
# it can point this at a mirror without touching the file (see backend/Dockerfile).
# `replace-registry-host=always` is what makes that override stick: `npm ci`
# fetches tarballs from the `resolved` URLs recorded in the lockfile, so without
# it a `--registry` flag is ignored for every download.
ARG NPM_REGISTRY=https://registry.npmjs.org
COPY package.json package-lock.json* ./
RUN npm ci --registry "${NPM_REGISTRY}" --replace-registry-host=always --no-audit --no-fund

FROM node:22-alpine AS builder
WORKDIR /app
COPY --from=deps /app/node_modules ./node_modules
COPY . .

ARG NEXT_PUBLIC_API_BASE_URL=http://localhost:8000
ARG NEXT_PUBLIC_SITE_URL=http://localhost:3000
ARG NEXT_PUBLIC_LOCALES=zh-CN,en,ja
ARG NEXT_PUBLIC_DEFAULT_LOCALE=zh-CN
# Server components render during the build as well, and the API container is
# not up yet. Point them at a name that will not resolve: a failed connection
# arrives as an ordinary NETWORK_ERROR, which `tolerantDuringBuild` degrades to
# a fallback. Without it the server-side base falls through to the public URL —
# a relative path in production — and the same situation becomes a URL that
# will not parse, which is not tolerated and kills the prerender.
ARG API_BASE_URL=http://api:8000
ENV NEXT_PUBLIC_API_BASE_URL=$NEXT_PUBLIC_API_BASE_URL \
    NEXT_PUBLIC_SITE_URL=$NEXT_PUBLIC_SITE_URL \
    NEXT_PUBLIC_LOCALES=$NEXT_PUBLIC_LOCALES \
    NEXT_PUBLIC_DEFAULT_LOCALE=$NEXT_PUBLIC_DEFAULT_LOCALE \
    API_BASE_URL=$API_BASE_URL \
    NEXT_TELEMETRY_DISABLED=1

RUN npm run build

FROM node:22-alpine AS runner
WORKDIR /app

ENV NODE_ENV=production \
    NEXT_TELEMETRY_DISABLED=1 \
    PORT=3000 \
    HOSTNAME=0.0.0.0

RUN addgroup -g 1001 -S nodejs && adduser -S nextjs -u 1001

# `output: "standalone"` already bundles the server and its traced deps.
COPY --from=builder /app/public ./public
COPY --from=builder --chown=nextjs:nodejs /app/.next/standalone ./
COPY --from=builder --chown=nextjs:nodejs /app/.next/static ./.next/static

USER nextjs
EXPOSE 3000

CMD ["node", "server.js"]
