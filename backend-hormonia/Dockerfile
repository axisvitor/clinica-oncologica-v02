# Backend Dockerfile - Python com Supabase
FROM python:3.13-slim

# Definir diretório de trabalho
WORKDIR /app

# Instalar dependências do sistema
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copiar arquivos de dependências
COPY package.json ./

# Instalar dependências Node.js se necessário
RUN if [ -f package.json ]; then \
    curl -fsSL https://deb.nodesource.com/setup_20.x | bash - && \
    apt-get install -y nodejs && \
    npm install --production; \
    fi

# Copiar código da aplicação
COPY . .

# Expor porta
EXPOSE 8000

# Variáveis de ambiente padrão
ENV PYTHONUNBUFFERED=1
ENV NODE_ENV=production

# Comando de inicialização
CMD ["node", "index.js"]
