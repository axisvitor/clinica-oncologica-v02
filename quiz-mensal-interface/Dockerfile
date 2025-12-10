# Quiz Mensal Interface - Next.js 14 (Dockerfile)
# Multi-stage build for Railway deployment

# =============================================================================
# STAGE 1: Builder - Install dependencies and build the application
# =============================================================================
FROM node:20-alpine AS builder

# Set workdir
WORKDIR /app

# Copy package files first for better layer caching
COPY quiz-mensal-interface/package.json ./quiz-mensal-interface/

# Install dependencies
WORKDIR /app/quiz-mensal-interface
RUN npm install

# Copy source code
WORKDIR /app
COPY quiz-mensal-interface/ ./quiz-mensal-interface/

# Build the application
WORKDIR /app/quiz-mensal-interface
ENV NODE_ENV=production
ENV NEXT_TELEMETRY_DISABLED=1
RUN npm run build

# =============================================================================
# STAGE 2: Runner - Production image
# =============================================================================
FROM node:20-alpine AS runner

# System dependencies (curl for healthcheck)
RUN apk add --no-cache curl

# Set workdir
WORKDIR /app

# Set environment variables
ENV NODE_ENV=production \
    NEXT_TELEMETRY_DISABLED=1 \
    PORT=3000 \
    HOST=0.0.0.0

# Copy built application from the builder stage
COPY --from=builder /app/quiz-mensal-interface/.next ./.next
COPY --from=builder /app/quiz-mensal-interface/public ./public
COPY --from=builder /app/quiz-mensal-interface/node_modules ./node_modules
COPY --from=builder /app/quiz-mensal-interface/package.json ./package.json
COPY --from=builder /app/quiz-mensal-interface/next.config.mjs ./next.config.mjs

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

# Start Next.js in production mode
CMD ["sh", "-c", "npx next start -p ${PORT:-3000} -H 0.0.0.0"]
