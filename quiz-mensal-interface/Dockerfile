# Quiz Mensal Interface - Next.js 14 (Dockerfile)
# Multi-stage build for Railway deployment

# =============================================================================
# STAGE 1: Builder - Install dependencies and build the application
# =============================================================================
FROM node:20-alpine@sha256:2d07db07a2df6830718ae2a47db6fedce6745f5bcd174c398f2acdda90a11c03 AS builder

# Install pnpm globally
ENV PNPM_HOME="/pnpm"
ENV PATH="$PNPM_HOME:$PATH"
RUN npm install -g pnpm@9.15.2

# Set workdir
WORKDIR /app

# Copy package files first for better layer caching
COPY quiz-mensal-interface/package.json quiz-mensal-interface/pnpm-lock.yaml ./quiz-mensal-interface/

# Install dependencies
WORKDIR /app/quiz-mensal-interface
RUN pnpm install --frozen-lockfile

# Copy source code
WORKDIR /app
COPY quiz-mensal-interface/ ./quiz-mensal-interface/

# Build the application
WORKDIR /app/quiz-mensal-interface
ENV NODE_ENV=production
ENV NEXT_TELEMETRY_DISABLED=1
RUN pnpm build

# =============================================================================
# STAGE 2: Runner - Production image
# =============================================================================
FROM node:20-alpine@sha256:2d07db07a2df6830718ae2a47db6fedce6745f5bcd174c398f2acdda90a11c03 AS runner

# System dependencies (curl for healthcheck)
RUN apk add --no-cache curl

# Install pnpm globally
ENV NODE_ENV=production \
  NEXT_TELEMETRY_DISABLED=1 \
  PNPM_HOME="/pnpm" \
  PATH="$PNPM_HOME:$PATH"
RUN npm install -g pnpm@9.15.2

# Set workdir
WORKDIR /app

# Copy built application from the builder stage
COPY --from=builder /app/quiz-mensal-interface/.next ./.next
COPY --from=builder /app/quiz-mensal-interface/public ./public
COPY --from=builder /app/quiz-mensal-interface/node_modules ./node_modules
COPY --from=builder /app/quiz-mensal-interface/package.json ./package.json
COPY --from=builder /app/quiz-mensal-interface/pnpm-lock.yaml ./pnpm-lock.yaml
COPY --from=builder /app/quiz-mensal-interface/next.config.mjs ./next.config.mjs

# Runtime env
ENV PORT=3000 \
  HOST=0.0.0.0

# Expose port (Railway overrides PORT)
EXPOSE 3000

# Healthcheck via Next route
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
  CMD curl -f http://localhost:${PORT:-3000}/api/health || exit 1

# Create non-root user for security
RUN addgroup --system --gid 1001 nodejs && \
    adduser --system --uid 1001 nextjs && \
    chown -R nextjs:nodejs /app
USER nextjs

# Start Next in production, binding to 0.0.0.0 and PORT
CMD ["sh", "-c", "pnpm exec next start -p ${PORT:-3000} -H 0.0.0.0"]
