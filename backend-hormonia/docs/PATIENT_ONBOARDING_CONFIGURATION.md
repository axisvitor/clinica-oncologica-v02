# Configuração do Sistema de Onboarding de Pacientes

## ✅ Status Atual: CONFIGURADO CORRETAMENTE

O sistema está configurado para enviar mensagens de boas-vindas automaticamente quando um paciente é criado.

## 📋 Fluxo Completo de Criação de Paciente

### 1. Endpoint da API
**Arquivo:** `app/api/v2/patients_crud.py`

```
POST /api/v2/patients
```

### 2. Fluxo de Execução

```
API Endpoint (patients_crud.py)
    ↓
PatientService.create_patient()
    ↓
SagaOrchestrator.execute_patient_onboarding_saga()
    ↓
┌─────────────────────────────────────────┐
│  SAGA STEPS (Transação Distribuída)    │
├─────────────────────────────────────────┤
│  1. Criar Paciente no Banco             │
│  2. Criar Flow State                    │
│  3. Enviar Mensagem WhatsApp            │
│  4. Marcar Saga como Completa           │
└─────────────────────────────────────────┘
```

### 3. Componentes Envolvidos

#### A. SagaOrchestrator
**Arquivo:** `app/coordination/saga_orchestrator.py`

- Gerencia transações distribuídas
- Garante atomicidade (tudo ou nada)
- Implementa compensação automática em caso de falha
- Persiste estado no Redis para retry

#### B. IdempotentMessageSender
**Arquivo:** `app/domain/messaging/delivery/idempotent_sender.py`

- Garante que mensagens não sejam duplicadas
- Usa chaves de idempotência
- Integra com Evolution API

#### C. EvolutionClient
**Arquivo:** `app/integrations/evolution.py`

- Cliente para Evolution API
- Envia mensagens via WhatsApp
- Gerencia retry e rate limiting

#### D. Welcome Message Template
**Arquivo:** `app/templates/whatsapp/welcome_message.py`

- Gera mensagem personalizada de boas-vindas
- Inclui nome do paciente e informações da clínica

## 🔧 Configuração Atual

### Evolution API (✅ Configurado)
```env
EVOLUTION_API_URL=https://evolution.axisvanguard.site
EVOLUTION_INSTANCE_NAME=instancia-teste
EVOLUTION_API_KEY=8635EBA73252-46A9-A9...
ENABLE_EVOLUTION=true
```

### Saga Pattern (✅ Ativo por Padrão)
O Saga Pattern está **habilitado por padrão** no código:

```python
# app/services/patient.py
use_saga = self.saga_orchestrator is not None and getattr(settings, "ENABLE_SAGA_PATTERN", True)
```

**Nota:** Como `ENABLE_SAGA_PATTERN` não está definido no `.env`, o valor padrão é `True`.

### Redis (✅ Configurado)
```env
REDIS_URL=redis://default:...@redis-14149.c322.us-east-1-2.ec2.redns.redis-cloud.com:14149
```

Usado para:
- Persistência de estado do Saga
- Idempotência de mensagens
- Cache de dados

## 📝 O Que Acontece Quando um Paciente é Criado

### Passo a Passo

1. **Validação Inicial**
   - Verifica se o médico existe
   - Valida unicidade de email, CPF e telefone
   - Normaliza CPF e formata telefone para E.164

2. **Inicialização do Saga**
   - Cria SagaOrchestrator com DB, Redis e EvolutionClient
   - Gera ID único para o saga
   - Prepara contexto com dados do paciente

3. **Execução dos Steps**

   **Step 1: Criar Paciente**
   - Insere registro na tabela `patients`
   - Gera hash de integridade
   - Commit no banco de dados

   **Step 2: Criar Flow State**
   - Busca template ativo `initial_15_days`
   - Cria registro em `patient_flow_states`
   - Define `current_step = 0`

   **Step 3: Enviar Mensagem WhatsApp**
   - Gera mensagem de boas-vindas personalizada
   - Cria registro em `messages` com status PENDING
   - Envia via Evolution API
   - Atualiza status para SENT

4. **Finalização**
   - Marca saga como COMPLETED
   - Persiste saga no banco (`patient_onboarding_sagas`)
   - Commit de todas as alterações
   - Invalida caches relevantes

### Compensação em Caso de Falha

Se qualquer step falhar após retries:

1. **Compensação Reversa**
   - Desfaz steps completados em ordem reversa
   - Remove flow state se criado
   - Remove paciente se criado

2. **Persistência do Erro**
   - Saga marcada como COMPENSATED ou FAILED
   - Erro registrado para análise
   - Possibilidade de retry manual

## 🧪 Testes Realizados

### Teste Manual (✅ Sucesso)
**Script:** `scripts/test_evolution_api.py`

```bash
python scripts/test_evolution_api.py
```

**Resultado:**
- ✅ Evolution API client inicializado
- ✅ Mensagem de boas-vindas gerada (721 caracteres)
- ✅ Mensagem enviada com sucesso
- ✅ Status: PENDING (aguardando entrega)
- ✅ Message ID: 3EB0DD34C2E771D0F9119B038B7A24ACBDB76753

## 🔍 Verificação de Configuração

### Como Verificar se Está Funcionando

1. **Verificar Evolution API**
```bash
python scripts/test_evolution_api.py
```

2. **Criar Paciente via API**
```bash
curl -X POST http://localhost:8000/api/v2/patients \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -d '{
    "name": "João Silva",
    "phone": "+5511999999999",
    "email": "joao@example.com",
    "doctor_id": "DOCTOR_UUID"
  }'
```

3. **Verificar Logs**
```bash
# Procurar por:
# - "Creating patient using Saga Pattern"
# - "Saga step completed: create_patient"
# - "Saga step completed: create_flow_state"
# - "Saga step completed: send_initial_message"
# - "Saga completed successfully"
```

4. **Verificar Banco de Dados**
```sql
-- Verificar paciente criado
SELECT * FROM patients WHERE phone = '+5511999999999';

-- Verificar flow state
SELECT * FROM patient_flow_states WHERE patient_id = 'PATIENT_UUID';

-- Verificar mensagem
SELECT * FROM messages WHERE patient_id = 'PATIENT_UUID';

-- Verificar saga
SELECT * FROM patient_onboarding_sagas WHERE patient_id = 'PATIENT_UUID';
```

## 🚨 Troubleshooting

### Mensagem Não Foi Enviada

1. **Verificar Evolution API**
   - URL está correta?
   - API Key está válida?
   - Instância está ativa?

2. **Verificar Logs**
   ```bash
   # Procurar por erros:
   grep "Evolution API" logs/app.log
   grep "Saga step failed" logs/app.log
   ```

3. **Verificar Redis**
   ```bash
   redis-cli -h redis-14149.c322.us-east-1-2.ec2.redns.redis-cloud.com -p 14149 -a PASSWORD
   KEYS saga:*
   ```

### Saga Falhou

1. **Verificar Tabela de Sagas**
   ```sql
   SELECT * FROM patient_onboarding_sagas 
   WHERE status IN ('FAILED', 'COMPENSATED')
   ORDER BY started_at DESC;
   ```

2. **Tentar Retry Manual**
   ```python
   from app.coordination.saga_orchestrator import SagaOrchestrator
   
   saga_id = "SAGA_UUID"
   result = await orchestrator.resume_saga(saga_id)
   ```

## 📊 Métricas e Monitoramento

### Logs Estruturados

O sistema gera logs estruturados para cada step:

```json
{
  "saga_id": "saga_abc123",
  "saga_type": "patient_onboarding",
  "step_name": "send_initial_message",
  "status": "completed",
  "patient_id": "uuid",
  "doctor_id": "uuid",
  "duration_ms": 623
}
```

### Tabelas de Auditoria

- `patient_onboarding_sagas`: Histórico de todas as execuções
- `messages`: Registro de todas as mensagens enviadas
- `audit_logs`: Logs de auditoria gerais

## ✅ Conclusão

O sistema está **CORRETAMENTE CONFIGURADO** para:

1. ✅ Criar pacientes via API
2. ✅ Enviar mensagens de boas-vindas automaticamente
3. ✅ Iniciar flow de acompanhamento
4. ✅ Garantir atomicidade com Saga Pattern
5. ✅ Compensar falhas automaticamente
6. ✅ Permitir retry de sagas falhadas

**Próximos Passos:**
- Testar criação de paciente via interface web
- Monitorar logs de produção
- Configurar alertas para sagas falhadas
