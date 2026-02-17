# syntax=docker/dockerfile:1

# Stage 1: Dependencies
FROM node:20-alpine AS deps
# Check https://github.com/nodejs/docker-node/tree/b4117f9333da4138b03a546ec926ef50a31506c3#nodealpine to understand why libc6-compat might be needed.
RUN apk add --no-cache libc6-compat
WORKDIR /app

# Copy lockfiles for a 'clean install' (npm ci)
# This makes builds faster and more predictable than standard 'npm install'
COPY package.json package-lock.json* ./

# OPTIMIZATION: Use npm cache mounting to speed up repeated installs
RUN --mount=type=cache,target=/root/.npm \
    npm ci


# Stage 2: Builder
FROM node:20-alpine AS builder
WORKDIR /app
COPY --from=deps /app/node_modules ./node_modules
COPY . .

# NEXT_PUBLIC_* values used by client components are inlined at build time.
ARG NEXT_PUBLIC_API_URL=http://localhost:8000
ARG NEXT_PUBLIC_API_AUTH_KEY=
ARG NEXT_PUBLIC_FEATURE_TRENDS_DASHBOARD=false
ENV NEXT_PUBLIC_API_URL=${NEXT_PUBLIC_API_URL}
ENV NEXT_PUBLIC_API_AUTH_KEY=${NEXT_PUBLIC_API_AUTH_KEY}
ENV NEXT_PUBLIC_FEATURE_TRENDS_DASHBOARD=${NEXT_PUBLIC_FEATURE_TRENDS_DASHBOARD}

# Next.js collects completely anonymous telemetry data about general usage.
# Learn more here: https://nextjs.org/telemetry
ENV NEXT_TELEMETRY_DISABLED 1

RUN npm run build


# Stage 3: Runner
# Final minimal production image using Next.js standalone mode.
FROM node:20-alpine AS runner
WORKDIR /app

ENV NODE_ENV production
ENV NEXT_TELEMETRY_DISABLED 1

# Security: Run as a restricted user
RUN addgroup --system --gid 1001 nodejs && \
    adduser --system --uid 1001 nextjs

# Copy only what is needed for the production server
COPY --from=builder /app/public ./public

# Set the correct permission for prerender cache
RUN mkdir .next && chown nextjs:nodejs .next

# Automatically leverage output traces to reduce image size
# https://nextjs.org/docs/advanced-features/output-file-tracing
COPY --from=builder --chown=nextjs:nodejs /app/.next/standalone ./
COPY --from=builder --chown=nextjs:nodejs /app/.next/static ./.next/static

USER nextjs

EXPOSE 3000

ENV PORT 3000
ENV HOSTNAME "0.0.0.0"

# SECURITY: Health check for the web server
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
  CMD wget --no-verbose --tries=1 --spider http://localhost:3000/ || exit 1

CMD ["node", "server.js"]
