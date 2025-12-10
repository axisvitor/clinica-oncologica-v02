# Frontend Dockerfile - React/Vite
FROM node:18-alpine AS builder
WORKDIR /app

# Copy shared packages first
COPY packages/shared-types ./packages/shared-types

# Copy frontend files
COPY frontend-hormonia ./frontend-hormonia

# Install and build
WORKDIR /app/frontend-hormonia
RUN npm install
RUN npm run build

# Production stage
FROM nginx:alpine
RUN apk add --no-cache python3

# Copy build output
COPY --from=builder /app/frontend-hormonia/dist /usr/share/nginx/html

# Copy nginx config and entrypoint
COPY frontend-hormonia/nginx.conf /etc/nginx/nginx.conf.template
COPY frontend-hormonia/docker-entrypoint.sh /docker-entrypoint.sh
RUN chmod +x /docker-entrypoint.sh

ENV PORT=3000
EXPOSE 3000

ENTRYPOINT ["/docker-entrypoint.sh"]
CMD ["nginx", "-g", "daemon off;"]
