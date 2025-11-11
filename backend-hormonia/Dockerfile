# Backend Dockerfile - FastAPI com Python 3.13
FROM python:3.13-slim

# Permite build a partir da raiz do repositório (padrão) ou diretamente do diretório backend
ARG APP_SRC=backend-hormonia

# Definir diretório de trabalho
WORKDIR /app

# Instalar dependências do sistema
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Copiar arquivo de dependências
COPY ${APP_SRC}/requirements.txt ./requirements.txt

# Atualizar pip, setuptools e wheel para versões mais recentes
# Isso resolve problemas de resolução de dependências e acelera o build
RUN pip install --no-cache-dir --upgrade pip setuptools wheel

# Instalar dependências Python
RUN pip install --no-cache-dir -r requirements.txt

# Copiar código da aplicação
COPY ${APP_SRC}/ .

# Criar usuário não-root
RUN useradd -m -u 1000 appuser && chown -R appuser:appuser /app
USER appuser

# Expor porta (Railway injeta via $PORT)
EXPOSE 8000

# Variáveis de ambiente padrão
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# Health check (usa $PORT injetado pelo Railway)
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:${PORT:-8000}/health || exit 1

# Comando de inicialização: Apenas Uvicorn (SEM MIGRAÇÕES)
# Schema já está correto, não precisamos executar migrações
CMD uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --log-level info
