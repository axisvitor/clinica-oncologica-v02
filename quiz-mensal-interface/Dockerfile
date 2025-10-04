# Quiz Mensal Interface - Next.js 14 (Dockerfile)
# Single-stage build for simplicity on Railway

FROM node:20-alpine@sha256:2d07db07a2df6830718ae2a47db6fedce6745f5bcd174c398f2acdda90a11c03

# System dependencies (curl for healthcheck)
RUN apk add --no-cache curl

# Enable pnpm via corepack
ENV NODE_ENV=production \
    NEXT_TELEMETRY_DISABLED=1
RUN corepack enable && corepack prepare pnpm@9 --activate

# Set workdir
WORKDIR /app

# Install dependencies
COPY package.json pnpm-lock.yaml ./
RUN pnpm install --frozen-lockfile --prod=false

# Copy source
COPY . .

# Build
RUN pnpm build

# Runtime env
ENV PORT=3000 \
    HOST=0.0.0.0

# Expose port (Railway overrides PORT)
EXPOSE 3000

# Healthcheck via Next route
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
  CMD curl -f http://localhost:${PORT:-3000}/api/health || exit 1

# Start Next in production, binding to 0.0.0.0 and PORT
# Use pnpm exec to avoid arg forwarding issues
USER node
CMD ["sh", "-c", "pnpm exec next start -p ${PORT:-3000} -H 0.0.0.0"]
