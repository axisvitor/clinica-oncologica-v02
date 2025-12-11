# =============================================================================
# Quiz Mensal Interface - Next.js 14 (Railway Compatible)
# Build context: quiz-mensal-interface/
# =============================================================================
# Uses standalone output for minimal image size
# =============================================================================

# =============================================================================
# STAGE 1: Dependencies - Install only production dependencies
# =============================================================================
FROM node:20-alpine AS deps

# Add libc6-compat for Alpine compatibility
RUN apk add --no-cache libc6-compat

WORKDIR /app

# Copy package files
COPY package.json package-lock.json* ./

# Install ALL dependencies (needed for build)
RUN npm ci

# =============================================================================
# STAGE 2: Builder - Build the application
# =============================================================================
FROM node:20-alpine AS builder

WORKDIR /app

# Copy dependencies from deps stage
COPY --from=deps /app/node_modules ./node_modules
COPY . .

# Set environment for build
ENV NODE_ENV=production
ENV NEXT_TELEMETRY_DISABLED=1
# Skip env validation during build (will validate at runtime)
ENV NEXT_PHASE=phase-production-build

# Build the application (uses standalone output from next.config.mjs)
RUN npm run build

# =============================================================================
# STAGE 3: Runner - Production image with standalone output
# =============================================================================
FROM node:20-alpine AS runner

# Install curl for healthcheck and other runtime needs
RUN apk add --no-cache curl

WORKDIR /app

# Set runtime environment variables
ENV NODE_ENV=production \
    NEXT_TELEMETRY_DISABLED=1 \
    PORT=3000 \
    HOST=0.0.0.0

# Create non-root user for security (before copying files)
RUN addgroup --system --gid 1001 nodejs && \
    adduser --system --uid 1001 nextjs

# Copy standalone output (this includes all necessary node_modules)
COPY --from=builder /app/.next/standalone ./

# Copy static files (not included in standalone)
COPY --from=builder /app/.next/static ./.next/static

# Copy public folder
COPY --from=builder /app/public ./public

# Set ownership to non-root user
RUN chown -R nextjs:nodejs /app

# Switch to non-root user
USER nextjs

# Expose port (Railway will override via PORT env var)
EXPOSE 3000

# Health check
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD curl -f http://localhost:${PORT:-3000}/api/health || exit 1

# Start the standalone server
# Note: standalone server respects PORT environment variable automatically
CMD ["node", "server.js"]
