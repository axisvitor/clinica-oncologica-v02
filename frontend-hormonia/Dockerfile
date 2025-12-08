# Frontend Dockerfile - React/Vite com build otimizado
FROM node:18-alpine AS builder

# Definir diretório de trabalho
WORKDIR /app

# Copy shared packages
COPY packages/shared-types ./packages/shared-types

# Copy frontend package
COPY frontend-hormonia/package.json ./frontend-hormonia/
COPY frontend-hormonia/tsconfig.json ./frontend-hormonia/
COPY frontend-hormonia/vite.config.ts ./frontend-hormonia/
COPY frontend-hormonia/index.html ./frontend-hormonia/
COPY frontend-hormonia/public ./frontend-hormonia/public
COPY frontend-hormonia/src ./frontend-hormonia/src

# Install dependencies and build
WORKDIR /app/frontend-hormonia
RUN npm install
RUN npm run build --prefer-offline --no-audit

# Copiar código fonte
COPY . .

# Declarar ARGs para variáveis de ambiente
# API Configuration
ARG VITE_API_BASE_URL
ARG VITE_API_URL
ARG VITE_WS_URL

# Firebase Configuration
ARG VITE_FIREBASE_API_KEY
ARG VITE_FIREBASE_AUTH_DOMAIN
ARG VITE_FIREBASE_PROJECT_ID
ARG VITE_FIREBASE_STORAGE_BUCKET
ARG VITE_FIREBASE_MESSAGING_SENDER_ID
ARG VITE_FIREBASE_APP_ID
ARG VITE_FIREBASE_MEASUREMENT_ID

# Feature Flags
ARG VITE_ENABLE_ANALYTICS
ARG VITE_ENABLE_SENTRY
ARG VITE_DEV_MODE

# Converter ARGs em ENVs para o build do Vite
# API Configuration
ENV VITE_API_BASE_URL=$VITE_API_BASE_URL
ENV VITE_API_URL=$VITE_API_URL
ENV VITE_WS_URL=$VITE_WS_URL

# Firebase Configuration
ENV VITE_FIREBASE_API_KEY=$VITE_FIREBASE_API_KEY
ENV VITE_FIREBASE_AUTH_DOMAIN=$VITE_FIREBASE_AUTH_DOMAIN
ENV VITE_FIREBASE_PROJECT_ID=$VITE_FIREBASE_PROJECT_ID
ENV VITE_FIREBASE_STORAGE_BUCKET=$VITE_FIREBASE_STORAGE_BUCKET
ENV VITE_FIREBASE_MESSAGING_SENDER_ID=$VITE_FIREBASE_MESSAGING_SENDER_ID
ENV VITE_FIREBASE_APP_ID=$VITE_FIREBASE_APP_ID
ENV VITE_FIREBASE_MEASUREMENT_ID=$VITE_FIREBASE_MEASUREMENT_ID

# Feature Flags
ENV VITE_ENABLE_ANALYTICS=$VITE_ENABLE_ANALYTICS
ENV VITE_ENABLE_SENTRY=$VITE_ENABLE_SENTRY
ENV VITE_DEV_MODE=$VITE_DEV_MODE

# Build da aplicação
RUN npm run build:runtime

# Stage de produção com Nginx
FROM nginx:alpine

# Instalar Python3 para sanitização de URLs no entrypoint
RUN apk add --no-cache python3

# Copiar build do stage anterior
COPY --from=builder /app/dist /usr/share/nginx/html

# Copiar configuração do Nginx com proxy para backend
# Use path relative to build context (project root when building via Railway)
COPY frontend-hormonia/nginx.conf /etc/nginx/nginx.conf.template

# Copiar entrypoint para processar variáveis de ambiente
# Use path relative to build context (project root when building via Railway)
COPY frontend-hormonia/docker-entrypoint.sh /docker-entrypoint.sh
RUN chmod +x /docker-entrypoint.sh

# Definir porta padrão
ENV PORT=3000

# Expor porta
EXPOSE 3000

# Health check
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD wget --quiet --tries=1 --spider http://localhost/ || exit 1

# Usar entrypoint para processar variáveis antes do nginx
ENTRYPOINT ["/docker-entrypoint.sh"]
CMD ["nginx", "-g", "daemon off;"]
