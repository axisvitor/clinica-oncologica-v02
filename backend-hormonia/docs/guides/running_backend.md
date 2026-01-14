# Guia de Execução do Backend Hormonia

Este guia detalha os processos necessários para executar o backend do Sistema Hormonia em ambiente de desenvolvimento e produção.

Para o funcionamento completo do sistema, **três processos distintos** devem estar em execução simultânea.

## Visão Geral dos Processos

| Processo | Comando (Dev) | Função Principal |
|----------|---------------|------------------|
| **1. API Server** | `uvicorn app.main:app` | Recebe e responde a requisições HTTP (Frontend, Webhooks). |
| **2. Celery Worker** | `celery worker` | Processa tarefas assíncronas (Envio de WhatsApp, Jobs pesados). |
| **3. Celery Beat** | `celery beat` | Agendador de tarefas (Cron jobs, tarefas periódicas). |

---

## 1. API Server (Uvicorn)

O servidor de API é a porta de entrada da aplicação. Ele lida com todas as requisições HTTP vindas do frontend ou de webhooks externos (como a Evolution API).

**Comando:**
```bash
# Na pasta backend-hormonia
venv\Scripts\python.exe -m uvicorn app.main:app --reload --port 8000
```
*(No Linux/Mac: `source .venv/bin/activate && uvicorn app.main:app --reload --port 8000`)*

**O que deixa de funcionar se parar?**
- O Frontend não carrega dados.
- Webhooks do WhatsApp não são recebidos.
- Login e autenticação falham.

---

## 2. Celery Worker

O Worker é o "operário" do sistema. Ele pega tarefas da fila (Redis) e as executa. O envio de mensagens WhatsApp é feito aqui para não travar a API.

**Comando:**
```bash
# Na pasta backend-hormonia
venv\Scripts\celery.exe -A app.celery_app worker --loglevel=INFO --pool=solo
```
*(Nota: `--pool=solo` é recomendado para Windows. No Linux, pode ser omitido ou usado `prefork`)*

**O que deixa de funcionar se parar?**
- Mensagens de WhatsApp ficam com status `PENDING` e nunca são enviadas.
- Fluxos de conversa não avançam.
- Relatórios pesados não são gerados.

---

## 3. Celery Beat (Scheduler)

O Beat é o "relógio" do sistema. Ele não executa tarefas, apenas as coloca na fila nos horários programados.

**Comando:**
```bash
# Na pasta backend-hormonia
venv\Scripts\celery.exe -A app.celery_app beat --loglevel=INFO
```

**Principais Tarefas Agendadas:**
- `process-scheduled-messages` (30s): Envia mensagens agendadas.
- `retry-failed-messages` (5min): Tenta re-enviar falhas.
- `send-daily-reminders` (08:30): Envia lembretes diários aos pacientes.
- `check-patient-alerts`: Verifica sinais vitais e gera alertas.

**O que deixa de funcionar se parar?**
- Nada acontece automaticamente.
- Mensagens agendadas não são disparadas.
- Lembretes diários não são enviados.
- Limpezas de banco de dados não rodam.

---

## Resumo para Desenvolvimento (Windows)

Para desenvolver com o sistema completo, abra **3 terminais** na pasta `backend-hormonia` e rode:

**Terminal 1 (API):**
```powershell
venv\Scripts\python.exe -m uvicorn app.main:app --reload --port 8000
```

**Terminal 2 (Worker):**
```powershell
venv\Scripts\celery.exe -A app.celery_app worker --loglevel=INFO --pool=solo
```

**Terminal 3 (Beat):**
```powershell
venv\Scripts\celery.exe -A app.celery_app beat --loglevel=INFO
```

---

## Produção (Railway)

Em produção, estes processos são definidos no arquivo `railway.toml` e rodam em containers separados, escalando independentemente.

```toml
[web]
command = "uvicorn app.main:app --host 0.0.0.0 --port $PORT"

[worker]
command = "celery -A app.celery_app worker --loglevel=INFO"

[beat]
command = "celery -A app.celery_app beat --loglevel=INFO"
```
