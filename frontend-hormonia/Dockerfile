# Frontend Dockerfile - React/Vite com build otimizado
FROM node:20-slim AS builder

# Definir diretório de trabalho
WORKDIR /app

# Copiar arquivos de dependências
COPY package*.json ./

# Instalar dependências
RUN npm ci --prefer-offline --no-audit

# Copiar código fonte
COPY . .

# Build da aplicação
RUN npm run build:runtime

# Stage de produção com Nginx
FROM nginx:alpine

# Copiar build do stage anterior
COPY --from=builder /app/dist /usr/share/nginx/html

# Copiar configuração do server block (apenas bloco server, sem diretivas globais)
COPY nginx.server.conf /etc/nginx/conf.d/default.conf

# Expor porta
EXPOSE 80

# Health check
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD wget --quiet --tries=1 --spider http://localhost/ || exit 1

# Comando de inicialização
CMD ["nginx", "-g", "daemon off;"]
