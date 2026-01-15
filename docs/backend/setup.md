# Guia de Configuração e Instalação do Backend

Este guia fornece instruções detalhadas para configurar, instalar e executar o backend do Sistema Hormonia.

## 📋 Pré-requisitos

Antes de iniciar, certifique-se de ter instalado:
- **Python 3.13+**
- **PostgreSQL 15+**
- **Redis 7+** (usado como broker para o Celery e para cache)
- **Node.js 20+** (para ferramentas auxiliares, se necessário)

---

## 🚀 Instalação Rápida

1. **Navegue até o diretório do backend:**
   ```bash
   cd backend-hormonia
   ```

2. **Crie e ative um ambiente virtual:**
   ```bash
   # Windows
   python -m venv .venv
   .venv\Scripts\activate

   # Linux/Mac
   python3.13 -m venv .venv
   source .venv/bin/activate
   ```

3. **Instale as dependências:**
   ```bash
   pip install -r requirements.txt
   ```

4. **Configure as variáveis de ambiente:**
   ```bash
   cp .env.example .env
   # Edite o arquivo .env com suas credenciais locais
   ```

5. **Execute as migrações do banco de dados:**
   ```bash
   alembic upgrade head
   ```

---

## ⚙️ Configuração do Ambiente (.env)

As seguintes variáveis são essenciais para o funcionamento básico:

| Variável | Descrição |
|----------|-----------|
| `DATABASE_URL` | String de conexão com o PostgreSQL |
| `REDIS_URL` | String de conexão com o Redis |
| `SECRET_KEY` | Chave para geração de tokens JWT |
| `ENCRYPTION_KEY` | Chave de 32 caracteres para criptografia AES (Fernet) |
| `EVOLUTION_API_URL` | URL da Evolution API (WhatsApp) |
| `EVOLUTION_API_KEY` | Chave de API da Evolution API |

---

## 🏃 Execução do Sistema

Para o funcionamento completo, **três processos distintos** devem estar em execução simultânea.

### 1. API Server (FastAPI)
Responsável por receber e responder às requisições HTTP do frontend e webhooks.

**Comando:**
```bash
uvicorn app.main:app --reload --port 8000
```
- **Acesse em:** `http://localhost:8000`
- **Documentação:** `http://localhost:8000/docs` (Swagger UI)

### 2. Celery Worker
Processa tarefas assíncronas (como envio de mensagens WhatsApp e processamento de dados pesados).

**Comando:**
```bash
# Windows
celery -A app.celery_app worker --loglevel=INFO --pool=solo

# Linux/Mac
celery -A app.celery_app worker --loglevel=INFO
```

### 3. Celery Beat (Scheduler)
Agendador que coloca tarefas na fila nos horários programados (Cron jobs).

**Comando:**
```bash
celery -A app.celery_app beat --loglevel=INFO
```

---

## 🛠️ Scripts Utilitários

O projeto inclui scripts para facilitar tarefas comuns:

| Script | Função |
|--------|--------|
| `scripts/init_database.py` | Inicializa o banco de dados com estrutura básica |
| `scripts/populate_test_data.py` | Popula o banco com dados de teste realistas |
| `scripts/test_db_connection.py` | Verifica a conexão com o PostgreSQL e Redis |

---

## 🧪 Testes

Para executar a suíte de testes completa:
```bash
pytest
```

Para ver o relatório de cobertura:
```bash
pytest --cov=app --cov-report=term-missing
```

---

## ☁️ Produção (Railway)

Em produção, os processos são configurados via `railway.toml`. Certifique-se de que todas as variáveis de ambiente obrigatórias estejam configuradas no painel da Railway.
