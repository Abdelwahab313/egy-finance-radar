# EGY Finance frontend — Next.js 15, the only externally-exposed service.
# Listens on 5040 and proxies /api/* to the backend (see next.config.mjs).

FROM node:22-alpine AS build
WORKDIR /app
# Empty base => the app fetches relative "/api/*", which Next proxies to the
# backend. Baked at build time (NEXT_PUBLIC_* are inlined by `next build`).
ENV NEXT_PUBLIC_API_BASE=""
# Next bakes rewrites() into the build, so the proxy target must be set HERE,
# not at runtime. Override via compose build args to point elsewhere.
ARG BACKEND_ORIGIN="http://backend:8000"
ENV BACKEND_ORIGIN=$BACKEND_ORIGIN
COPY package.json package-lock.json ./
RUN npm ci
COPY . .
RUN npm run build

FROM node:22-alpine AS run
WORKDIR /app
ENV NODE_ENV=production
COPY --from=build /app/.next ./.next
COPY --from=build /app/node_modules ./node_modules
COPY --from=build /app/package.json ./package.json
COPY --from=build /app/next.config.mjs ./next.config.mjs
EXPOSE 5040
# BACKEND_ORIGIN is provided at runtime by compose so rewrites hit the backend.
CMD ["npx", "next", "start", "-p", "5040"]
