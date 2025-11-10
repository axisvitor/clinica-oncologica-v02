# Guia de Monitoramento - Sistema Hormonia

**Versão**: 2.0  
**Data**: Janeiro 2025  
**Status**: ✅ Implementado

---

## 📋 Índice

1. [Visão Geral](#visão-geral)
2. [Configuração](#configuração)
3. [Sentry Integration](#sentry-integration)
4. [Métricas e Alertas](#métricas-e-alertas)
5. [Error Tracking](#error-tracking)
6. [Performance Monitoring](#performance-monitoring)
7. [Best Practices](#best-practices)
8. [Troubleshooting](#troubleshooting)

---

## 🎯 Visão Geral

O Sistema Hormonia utiliza **Sentry** para monitoramento de erros, performance tracking e observabilidade em tempo real.

### Features Implementadas

- ✅ **Error Tracking**: Captura automática de exceções
- ✅ **Performance Monitoring**: Traces de requisições e queries
- ✅ **Breadcrumbs**: Rastreamento de eventos
- ✅ **User Context**: Identificação de usuários afetados
- ✅ **Release Tracking**: Versionamento de deploys
- ✅ **Environment Tagging**: Separação dev/staging/prod
- ✅ **PII Filtering**: Remoção automática de dados sensíveis

---

## 🔧 Configuração

### Passo 1: Instalar Dependências

```bash
# Instalar Sentry SDK
pip install sentry-sdk[fastapi]

# Ou adicionar ao requirements.txt
echo "sentry-sdk[fastapi]>=1.40.0" >> requirements.txt
pip install -r requirements.txt
```

### Passo 2: Configurar Variáveis de Ambiente

```bash
# .env ou secrets do Railway/AWS
SENTRY_DSN=https://your-sentry-dsn@sentry.io/project-id
ENVIRONMENT=production
APP_VERSION=2.0.0
```

**Obter DSN do Sentry**:
1. Criar conta em [sentry.io](https://sentry.io)
2. Criar novo projeto (Python/FastAPI)
3. Copiar DSN fornecido

### Passo 3: Inicializar no Startup

A inicialização já está configurada automaticamente no `app/main.py`:

```python
from app.core.startup_monitoring import initialize_monitoring

# No startup da aplicação
initialize_monitoring(app)
```

---

## 🚨 Sentry Integration

### Configuração por Ambiente

O monitoramento é configurado automaticamente baseado no ambiente:

| Ambiente | Sample Rate | Traces Sample Rate | Profiling |
|----------|-------------|-------------------|-----------|
| Development | 100% | 100% | ❌ |
| Staging | 100% | 50% | ✅ |
| Production | 100% | 10% | ✅ |

### Captura Automática

**Erros HTTP 5xx**:
```python
# Capturado automaticamente
raise HTTPException(status_code=500, detail="Internal error")
```

**Exceções Não Tratadas**:
```python
# Capturado automaticamente
raise ValueError("Something went wrong")
```

### Captura Manual

**Capturar Exceção**:
```python
from app.core.monitoring_config import capture_exception

try:
    # Código que pode falhar
    result = process_payment()
except PaymentError as e:
    capture_exception(
        e,
        context={
            "user_id": user.id,
            "amount": payment.amount,
            "payment_method": payment.method,
        },
        level="error"
    )
```

**Capturar Mensagem**:
```python
from app.core.monitoring_config import capture_message

capture_message(
    "Payment processing started",
    level="info",
    context={
        "user_id": user.id,
        "amount": amount,
    }
)
```

### Breadcrumbs

Breadcrumbs são capturados automaticamente para cada requisição. Você também pode adicionar manualmente:

```python
from app.core.monitoring_config import add_breadcrumb

add_breadcrumb(
    message="User logged in successfully",
    category="auth",
    level="info",
    data={
        "user_id": user.id,
        "method": "firebase",
    }
)
```

### User Context

Definir contexto do usuário para rastreamento:

```python
from app.core.monitoring_config import set_user_context

set_user_context(
    user_id=str(user.id),
    email=user.email,
    username=user.name,
    extra={
        "role": user.role,
        "subscription": user.subscription_tier,
    }
)
```

### Tags

Adicionar tags customizadas aos eventos:

```python
from app.core.monitoring_config import set_tag

set_tag("payment_provider", "stripe")
set_tag("feature_flag", "new_checkout")
```

---

## 📊 Métricas e Alertas

### Health Check

Verificar status do monitoramento:

```bash
curl https://api.hormonia.com/health/monitoring
```

**Resposta Esperada**:
```json
{
  "monitoring": "enabled",
  "sentry": "operational",
  "config": {
    "enabled": true,
    "environment": "production",
    "release": "2.0.0",
    "sample_rate": 1.0,
    "traces_sample_rate": 0.1
  }
}
```

### Métricas Chave

**No Dashboard do Sentry**:
- **Error Rate**: Meta < 1%
- **Response Time (p95)**: Meta < 500ms
- **Apdex Score**: Meta > 0.95
- **User Impact**: Usuários afetados por erros

### Configurar Alertas

**No Sentry Dashboard**:

1. **Alert Rules** → **Create Alert Rule**

2. **High Error Rate**:
   - Condição: `error count > 100 in 1 hour`
   - Action: Enviar email/Slack

3. **Performance Degradation**:
   - Condição: `p95 response time > 1000ms for 5 minutes`
   - Action: Enviar alerta

4. **New Release Issues**:
   - Condição: `new issue in release`
   - Action: Notificar time de dev

---

## 🐛 Error Tracking

### Filtro de Dados Sensíveis

Dados sensíveis são **automaticamente filtrados** antes de enviar ao Sentry:

**Campos Filtrados**:
- `password`, `senha`
- `token`, `api_key`, `secret`
- `authorization`, `cookie`, `session`
- `cpf`, `ssn`, `credit_card`

**Exemplo**:
```json
{
  "email": "user@example.com",
  "password": "[FILTERED]",
  "cpf": "[FILTERED]"
}
```

### Níveis de Severidade

| Nível | Uso | Enviado ao Sentry |
|-------|-----|-------------------|
| `debug` | Debugging detalhado | ❌ |
| `info` | Informações gerais | ❌ |
| `warning` | Avisos não críticos | ✅ (se configurado) |
| `error` | Erros que impedem operação | ✅ |
| `critical` | Erros críticos do sistema | ✅ |

### Exemplo de Erro Capturado

**No Código**:
```python
try:
    patient = await create_patient(data)
except ValidationError as e:
    capture_exception(
        e,
        context={
            "patient_data": data.dict(),
            "user_id": current_user.id,
        },
        level="error"
    )
    raise
```

**No Sentry**:
- Stacktrace completo
- Contexto: `patient_data`, `user_id`
- Breadcrumbs: requisições anteriores
- Environment: `production`
- Release: `2.0.0`

---

## ⚡ Performance Monitoring

### Distributed Tracing

Traces são capturados automaticamente para:
- Requisições HTTP
- Queries de banco de dados
- Chamadas Redis
- Tasks Celery

**Exemplo de Trace**:
```
POST /api/v2/patients (250ms)
  ├─ Query: INSERT INTO patients (100ms)
  ├─ Redis: SET cache:patient:123 (5ms)
  ├─ HTTP: POST firebase.com/auth (120ms)
  └─ Task: send_welcome_message (25ms)
```

### Custom Transactions

Adicionar transações customizadas:

```python
import sentry_sdk

with sentry_sdk.start_transaction(op="task", name="process_quiz_responses"):
    # Processar respostas
    responses = process_responses(quiz_id)
    
    with sentry_sdk.start_span(op="db", description="Save responses"):
        save_responses(responses)
```

### Slow Query Monitoring

Queries lentas são automaticamente marcadas:
- Queries > 1s: `warning`
- Queries > 5s: `error`

---

## ✅ Best Practices

### 1. Sempre Adicionar Contexto

**❌ Ruim**:
```python
capture_exception(error)
```

**✅ Bom**:
```python
capture_exception(
    error,
    context={
        "user_id": user.id,
        "operation": "create_patient",
        "patient_id": patient.id,
    }
)
```

### 2. Usar Breadcrumbs para Fluxo

```python
add_breadcrumb("Iniciando cadastro de paciente")
patient = create_patient(data)

add_breadcrumb("Criando usuário Firebase")
user = create_firebase_user(patient)

add_breadcrumb("Enviando mensagem de boas-vindas")
send_welcome_message(patient)
```

### 3. Definir User Context em Login

```python
@router.post("/login")
async def login(credentials: LoginCredentials):
    user = authenticate(credentials)
    
    # Definir contexto para todos os eventos subsequentes
    set_user_context(
        user_id=str(user.id),
        email=user.email,
        username=user.name,
    )
    
    return {"token": generate_token(user)}
```

### 4. Usar Tags para Filtrar

```python
# Adicionar tags relevantes
set_tag("feature", "quiz_mensal")
set_tag("ab_test", "variant_b")
set_tag("payment_provider", "stripe")

# Depois no Sentry: filtrar por `feature:quiz_mensal`
```

### 5. Não Enviar PII Desnecessário

**❌ Ruim**:
```python
capture_message(f"User {user.cpf} logged in")
```

**✅ Bom**:
```python
capture_message(
    "User logged in",
    context={"user_id": user.id}
)
```

---

## 🔍 Troubleshooting

### Monitoramento Não Está Funcionando

**1. Verificar DSN configurado**:
```bash
echo $SENTRY_DSN
# Deve retornar: https://...@sentry.io/...
```

**2. Verificar health check**:
```bash
curl http://localhost:8000/health/monitoring
```

**3. Verificar logs de startup**:
```bash
railway logs | grep "Sentry"
# Deve mostrar: ✓ Sentry inicializado com sucesso
```

### Erros Não Aparecem no Sentry

**Possíveis Causas**:

1. **Sample rate muito baixo**: Ajustar em `monitoring_config.py`
2. **Erro sendo capturado em try/catch**: Capturar manualmente
3. **Erro < 500**: Apenas 5xx são capturados automaticamente

### Performance Traces Não Aparecem

**Verificar**:
```python
# Verificar traces_sample_rate
config = get_monitoring_instance()
print(config.traces_sample_rate)
# Deve ser > 0
```

**Aumentar sample rate** (temporariamente):
```bash
# Em .env
TRACES_SAMPLE_RATE=1.0
```

### Muitos Eventos no Sentry

**Problema**: Quota sendo excedida rapidamente.

**Solução**:

1. **Reduzir sample rate**:
```python
# Em monitoring_config.py
sample_rate=0.5  # Captura 50% dos erros
traces_sample_rate=0.05  # Captura 5% das traces
```

2. **Filtrar erros conhecidos**:
```python
def before_send_filter(event, hint):
    # Ignorar erros específicos
    if 'ConnectionResetError' in str(hint.get('exc_info')):
        return None
    return event
```

3. **Aumentar quota**: Upgrade do plano Sentry

---

## 📚 Recursos Adicionais

### Documentação Oficial

- [Sentry Python SDK](https://docs.sentry.io/platforms/python/)
- [Sentry FastAPI Integration](https://docs.sentry.io/platforms/python/guides/fastapi/)
- [Performance Monitoring](https://docs.sentry.io/product/performance/)

### Arquivos do Projeto

- `app/core/monitoring_config.py` - Configuração
- `app/core/startup_monitoring.py` - Inicialização
- `docs/MONITORING.md` - Este documento

### Comandos Úteis

```bash
# Ver eventos no Sentry CLI
sentry-cli events list

# Testar integração
python -c "from app.core.monitoring_config import capture_message; capture_message('Test')"

# Ver releases
sentry-cli releases list
```

---

## 🚀 Próximos Passos

### Após Configuração

1. [ ] Deploy em staging
2. [ ] Validar eventos chegando no Sentry
3. [ ] Configurar alertas
4. [ ] Treinar equipe
5. [ ] Deploy em produção

### Melhorias Futuras

- [ ] Integração com Slack para alertas
- [ ] Dashboard customizado de métricas
- [ ] Alertas de anomalias com ML
- [ ] Integração com PagerDuty

---

**Elaborado por**: Equipe de DevOps Hormonia  
**Data**: Janeiro 2025  
**Versão**: 1.0