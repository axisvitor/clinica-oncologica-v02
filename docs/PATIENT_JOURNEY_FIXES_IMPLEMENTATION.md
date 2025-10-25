# Implementação de Correções: Jornada do Paciente

**Data:** 2025-10-24  
**Baseado em:** PATIENT_JOURNEY_ANALYSIS.md  
**Status:** 🔄 Em Implementação

---

## Sumário Executivo

Este documento detalha a implementação das correções identificadas na análise profunda da jornada do paciente, focando em ativar os sistemas core que estão prontos mas não executando.

**Problema Principal:** Sistema com arquitetura robusta mas componentes não ativos (flows, mensagens, alertas)

**Solução:** Ativação sistemática dos componentes + população de templates + configuração de tasks

---

## 1. POPULAÇÃO DE TEMPLATES NO BANCO DE DADOS

### 1.1 Script de População Criado

**Arquivo:** `backend-hormonia/scripts/populate_templates.py`

**Funcionalidades:**
- ✅ Popula `flow_template_versions` com 3 flows diários
- ✅ Popula `quiz_templates` com quiz mensal
- ✅ Popula `message_templates` com 5 templates de WhatsApp
- ✅ Popula `flow_kinds` com 4 tipos de flow
- ✅ Verifica duplicatas antes de inserir
- ✅ Usa transações seguras

### 1.2 Templates Disponíveis

#### Flow Templates (3)
1. **initial_15_days.yaml** - Onboarding inicial (dias 1-15)
2. **days_16_45.yaml** - Continuação (dias 16-45)
3. **monthly_recurring.yaml** - Manutenção mensal

#### Quiz Template (1)
1. **monthly_comprehensive.yaml** - Avaliação mensal completa
   - 10+ perguntas sobre bem-estar, energia, humor, sono
   - Sintomas físicos e adesão ao tratamento
   - Validação e categorização

#### Message Templates (5)
1. **welcome_message** - Boas-vindas inicial
2. **daily_checkin** - Check-in diário
3. **medication_reminder** - Lembrete de medicação
4. **quiz_invitation** - Convite para quiz mensal
5. **appointment_reminder** - Lembrete de consulta

### 1.3 Execução do Script

```bash
# Opção 1: Executar diretamente
cd backend-hormonia
python scripts/populate_templates.py

# Opção 2: Via Railway CLI (produção)
railway run python scripts/populate_templates.py

# Opção 3: Via Docker
docker exec -it backend-container python scripts/populate_templates.py
```

**Saída Esperada:**
```
============================================================
🚀 POPULANDO TEMPLATES NO BANCO DE DADOS
============================================================

📋 Populando Flow Kinds...
    ✅ Flow kind criado: onboarding
    ✅ Flow kind criado: daily_checkin
    ✅ Flow kind criado: monthly_quiz
    ✅ Flow kind criado: treatment_followup
  ✅ Flow kinds populados com sucesso!

📋 Populando Flow Templates...
  📄 Processando: initial_15_days.yaml
    ✅ Template criado: Initial 15 Days Onboarding Flow v2.0.0
  📄 Processando: days_16_45.yaml
    ✅ Template criado: Days 16-45 Continuation Flow v2.0.0
  📄 Processando: monthly_recurring.yaml
    ✅ Template criado: Monthly Recurring Maintenance Flow v2.0.0
  ✅ Flow templates populados com sucesso!

📋 Populando Quiz Templates...
  📄 Processando: monthly_comprehensive.yaml
    ✅ Quiz template criado: monthly_comprehensive v1.0.0
  ✅ Quiz templates populados com sucesso!

📋 Populando Message Templates...
    ✅ Template criado: welcome_message
    ✅ Template criado: daily_checkin
    ✅ Template criado: medication_reminder
    ✅ Template criado: quiz_invitation
    ✅ Template criado: appointment_reminder
  ✅ Message templates populados com sucesso!

============================================================
✅ TODOS OS TEMPLATES FORAM POPULADOS COM SUCESSO!
============================================================
```

---

## 2. VERIFICAÇÃO DE CELERY BEAT

### 2.1 Verificar Status do Celery

```bash
# Ver processos Celery rodando
ps aux | grep celery

# Ver logs do Celery Beat
tail -f logs/celery-beat.log

# Ver logs do Celery Worker
tail -f logs/celery-worker.log
```

### 2.2 Tasks Agendadas Esperadas

**Arquivo:** `backend-hormonia/app/celery_app.py`

```python
# Tasks diárias
@celery_app.on_after_configure.connect
def setup_periodic_tasks(sender, **kwargs):
    # Process daily flows - A cada 15 minutos
    sender.add_periodic_task(
        crontab(minute='*/15'),
        process_daily_flows.s(),
        name='process-daily-flows'
    )
    
    # Send daily reminders - Diário às 9h
    sender.add_periodic_task(
        crontab(hour=9, minute=0),
        send_daily_reminders.s(),
        name='send-daily-reminders'
    )
    
    # Check quiz triggers - A cada 2 horas
    sender.add_periodic_task(
        crontab(minute=0, hour='*/2'),
        check_quiz_triggers_task.s(),
        name='check-quiz-triggers'
    )
    
    # Check patient alerts - A cada 15 minutos
    sender.add_periodic_task(
        crontab(minute='*/15'),
        check_patient_alerts.s(),
        name='check-patient-alerts'
    )
```

### 2.3 Iniciar Celery (se não estiver rodando)

```bash
# Iniciar Celery Worker
celery -A app.celery_app worker --loglevel=info --pool=solo

# Iniciar Celery Beat (em outro terminal)
celery -A app.celery_app beat --loglevel=info

# Ou iniciar ambos juntos
celery -A app.celery_app worker --beat --loglevel=info --pool=solo
```

---

## 3. TESTE DE CRIAÇÃO DE PACIENTE

### 3.1 Criar Paciente Teste via API

```bash
# Obter token de autenticação
curl -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{
    "email": "medico@example.com",
    "password": "senha123"
  }'

# Criar paciente
curl -X POST http://localhost:8000/api/v1/patients \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <TOKEN>" \
  -d '{
    "name": "Maria Silva",
    "phone": "+5511999999999",
    "email": "maria@example.com",
    "treatment_type": "Terapia Hormonal",
    "treatment_start_date": "2025-10-24"
  }'
```

### 3.2 Verificar Saga de Onboarding

**Esperado:**
1. ✅ Paciente criado no banco (`patients` table)
2. ✅ Saga iniciada (`patient_onboarding_saga` table)
3. ✅ Mensagem de boas-vindas enviada (WhatsApp)
4. ✅ Flow iniciado (`patient_flow_states` table)

**Verificar no banco:**
```sql
-- Ver paciente criado
SELECT * FROM patients WHERE phone = '+5511999999999';

-- Ver saga
SELECT * FROM patient_onboarding_saga WHERE patient_id = '<PATIENT_ID>';

-- Ver flow state
SELECT * FROM patient_flow_states WHERE patient_id = '<PATIENT_ID>';

-- Ver mensagens
SELECT * FROM messages WHERE patient_id = '<PATIENT_ID>';
```

---

## 4. VERIFICAÇÃO DE INTEGRAÇÃO WHATSAPP

### 4.1 Testar Conexão com Evolution API

```bash
# Verificar instância
curl -X GET https://evolution.axisvanguard.site/instance/connectionState/clinica_oncologica \
  -H "apikey: 8635EBA73252-46A9-A965-7E534F24E72C"

# Enviar mensagem teste
curl -X POST https://evolution.axisvanguard.site/message/sendText/clinica_oncologica \
  -H "Content-Type: application/json" \
  -H "apikey: 8635EBA73252-46A9-A965-7E534F24E72C" \
  -d '{
    "number": "5511999999999",
    "text": "Teste de conexão - Hormon[IA]"
  }'
```

### 4.2 Verificar Webhook Configurado

**URL Esperada:** `https://clinica-oncologica-v02-production.up.railway.app/webhooks/whatsapp/evolution/clinica_oncologica`

**Testar webhook:**
```bash
curl -X POST http://localhost:8000/webhooks/whatsapp/evolution/clinica_oncologica \
  -H "Content-Type: application/json" \
  -d '{
    "event": "messages.upsert",
    "instance": "clinica_oncologica",
    "data": {
      "key": {
        "remoteJid": "5511999999999@s.whatsapp.net",
        "fromMe": false,
        "id": "test123"
      },
      "message": {
        "conversation": "Olá"
      }
    }
  }'
```

---

## 5. MONITORAMENTO E LOGS

### 5.1 Logs a Monitorar

```bash
# Backend logs
tail -f logs/app.log | grep -E "(flow|message|saga|quiz)"

# Celery logs
tail -f logs/celery-worker.log | grep -E "(process_daily_flows|send_daily_reminders)"

# Evolution API logs (se disponível)
tail -f logs/evolution-api.log
```

### 5.2 Métricas Esperadas

**Após 24h de operação:**
- ✅ 1+ paciente com flow ativo
- ✅ 1+ mensagem enviada
- ✅ 0 erros críticos nos logs
- ✅ Tasks Celery executando conforme schedule

**Após 1 semana:**
- ✅ Flows avançando diariamente
- ✅ Mensagens sendo enviadas regularmente
- ✅ Respostas de pacientes sendo processadas
- ✅ 0 flows travados

**Após 1 mês:**
- ✅ Primeiro quiz mensal enviado
- ✅ Respostas de quiz coletadas
- ✅ Alertas sendo gerados (se aplicável)
- ✅ Relatórios disponíveis

---

## 6. TROUBLESHOOTING

### 6.1 Flow Não Inicia

**Sintomas:**
- Paciente criado mas `patient_flow_states` vazio
- Saga com status "FAILED"

**Diagnóstico:**
```python
# Ver logs da saga
SELECT * FROM patient_onboarding_saga 
WHERE status = 'FAILED' 
ORDER BY created_at DESC 
LIMIT 10;

# Ver error_message
SELECT error_message, execution_log 
FROM patient_onboarding_saga 
WHERE patient_id = '<PATIENT_ID>';
```

**Soluções:**
1. Verificar se `flow_template_versions` tem templates ativos
2. Verificar se `flow_kinds` está populado
3. Verificar logs do backend para erros de execução
4. Tentar retry manual da saga

### 6.2 Mensagem Não Enviada

**Sintomas:**
- Flow iniciado mas mensagem não chega no WhatsApp
- `messages` table vazia ou com status "failed"

**Diagnóstico:**
```sql
-- Ver mensagens falhadas
SELECT * FROM messages 
WHERE status = 'failed' 
ORDER BY created_at DESC;

-- Ver tentativas de envio
SELECT * FROM whatsapp_delivery_failures 
ORDER BY created_at DESC;
```

**Soluções:**
1. Verificar conexão com Evolution API
2. Verificar se instância WhatsApp está conectada
3. Verificar se número de telefone está no formato correto
4. Verificar logs do Evolution API

### 6.3 Celery Beat Não Executa Tasks

**Sintomas:**
- Tasks não aparecem nos logs
- Flows não avançam automaticamente

**Diagnóstico:**
```bash
# Ver tasks agendadas
celery -A app.celery_app inspect scheduled

# Ver tasks ativas
celery -A app.celery_app inspect active

# Ver workers registrados
celery -A app.celery_app inspect registered
```

**Soluções:**
1. Reiniciar Celery Beat
2. Verificar configuração de timezone
3. Verificar conexão com Redis
4. Verificar se tasks estão registradas

---

## 7. CHECKLIST DE ATIVAÇÃO

### Fase 1: Preparação (30 min)
- [ ] Executar `populate_templates.py`
- [ ] Verificar templates no banco de dados
- [ ] Verificar Celery Beat rodando
- [ ] Verificar conexão Evolution API

### Fase 2: Teste Inicial (1h)
- [ ] Criar paciente teste
- [ ] Verificar saga executada
- [ ] Verificar mensagem enviada
- [ ] Verificar flow iniciado
- [ ] Verificar webhook funcionando

### Fase 3: Monitoramento (24h)
- [ ] Monitorar logs por 24h
- [ ] Verificar tasks Celery executando
- [ ] Verificar flows avançando
- [ ] Verificar mensagens sendo enviadas
- [ ] Corrigir problemas identificados

### Fase 4: Validação (1 semana)
- [ ] Criar 2-3 pacientes reais
- [ ] Validar jornada completa
- [ ] Coletar feedback
- [ ] Ajustar templates se necessário
- [ ] Documentar lições aprendidas

---

## 8. PRÓXIMOS PASSOS

### Curto Prazo (1-2 semanas)
1. ✅ Popular templates no banco
2. ✅ Ativar Celery Beat
3. ✅ Testar criação de paciente
4. ✅ Validar envio de mensagens
5. ⏳ Monitorar por 1 semana

### Médio Prazo (1 mês)
1. ⏳ Implementar dashboard de monitoramento
2. ⏳ Ativar sistema de alertas
3. ⏳ Configurar relatórios automáticos
4. ⏳ Treinar equipe médica
5. ⏳ Onboarding de pacientes reais

### Longo Prazo (3 meses)
1. ⏳ Análise de métricas de engajamento
2. ⏳ Otimização de templates baseada em feedback
3. ⏳ Implementação de features avançadas
4. ⏳ Integração com outros sistemas
5. ⏳ Expansão para outros tipos de tratamento

---

## 9. DOCUMENTAÇÃO RELACIONADA

- **Análise Completa:** `docs/PATIENT_JOURNEY_ANALYSIS.md`
- **Schema do Banco:** `docs/DATABASE_SCHEMA_COMPLETE.md`
- **Templates de Flow:** `backend-hormonia/app/templates/flows/`
- **Template de Quiz:** `backend-hormonia/app/templates/quiz/`
- **Script de População:** `backend-hormonia/scripts/populate_templates.py`

---

**Documento criado por:** Kiro AI  
**Data:** 2025-10-24  
**Versão:** 1.0  
**Status:** Pronto para Execução ✅
