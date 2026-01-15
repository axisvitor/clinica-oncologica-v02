# Sistema de Follow-Up - Relatório de Debug Completo

**Data:** 2025-12-24
**Sistema:** clinica-oncologica-v02-1
**Escopo:** Sistema de Follow-Up, Flow Service, Patient Flow Coordinator

---

## 📋 Sumário Executivo

### Status Geral
- **Arquitetura:** Modular com múltiplos pontos de integração
- **Estado:** Funcional com problemas de integração identificados
- **Complexidade:** Alta - 5 sistemas principais interconectados
- **Risco:** Médio - Falhas de integração podem causar perda de follow-ups

### Sistemas Analisados
1. **FollowUpSystemService** (`app/services/follow_up_system/`)
2. **Flow Service** (`app/domain/flows/core/`)
3. **Patient Flow Coordinator** (`app/agents/patient/flow_coordinator/`)
4. **Flow Automation Tasks** (`app/tasks/flow_automation.py`)
5. **Follow-Up Tasks** (`app/tasks/follow_up.py`)

---

## 🔄 Fluxo de Follow-Up - Arquitetura Completa

### 1. **Trigger de Follow-Up**

```
Patient Response → ResponseProcessor → FollowUpSystemService.process_response_follow_up()
                                     ↓
                              [Análise de Resposta]
                                     ↓
                              [Geração de Ações]
                                     ↓
                              [Agendamento]
```

#### Componentes Envolvidos:
- **ContextManager:** Gerencia contexto conversacional
- **EmpathyGenerator:** Gera respostas empáticas
- **MedicalConcernGenerator:** Detecta preocupações médicas
- **EscalationManager:** Gerencia escalações

### 2. **Tipos de Follow-Up**

```python
# app/services/follow_up_system/enums.py
class FollowUpType(str, Enum):
    EMPATHETIC_RESPONSE = "empathetic_response"
    MEDICAL_CLARIFICATION = "medical_clarification"
    ESCALATION_NOTIFICATION = "escalation_notification"
    PROVIDER_ALERT = "provider_alert"
    CONVERSATION_CONTINUATION = "conversation_continuation"
```

### 3. **Agendamento e Persistência**

```
FollowUpAction (criada) → ActionScheduler.schedule_action()
                          ↓
                   [Redis Store] ← [In-Memory Fallback]
                          ↓
              Persisted as JSON in Redis
                          ↓
              TTL: 7 days for contexts
              TTL: 30 days for actions
```

### 4. **Execução via Celery**

```
Celery Beat (every 5 min) → execute_pending_follow_ups()
                             ↓
                      [Rehydrate from Redis]
                             ↓
                      [Get Pending Actions]
                             ↓
                      [Execute by Type]
                             ↓
                      [Update Status in Redis]
```

---

## 🐛 Bugs Identificados

### **Bug #1: Missing FollowUpSystemService Import**
**Localização:** `app/tasks/follow_up.py:49`

**Problema:**
```python
from app.services.follow_up_system import FollowUpSystemService
```

O módulo `follow_up_system` existe mas o import não especifica o caminho correto.

**Causa:** Estrutura modular do `follow_up_system` package

**Correção:**
```python
from app.services.follow_up_system.service import FollowUpSystemService
```

**Impacto:** **CRÍTICO** - Task de follow-up falha na inicialização

---

### **Bug #2: Flow Service Integration Gap**
**Localização:** `app/domain/flows/core/flow_service.py`

**Problema:**
Não há integração direta entre `FlowService.process_daily_flows()` e o sistema de follow-up.

**Fluxo Atual:**
```python
# flow_service.py:182
async def _process_patient_daily_flow(self, flow_state):
    # Processa flow
    # Envia mensagem
    # ❌ NÃO registra no follow-up system
    return result
```

**Fluxo Esperado:**
```python
async def _process_patient_daily_flow(self, flow_state):
    result = await self._send_flow_message()

    # ✅ Registrar no follow-up system
    await self.follow_up_service.schedule_follow_up_check(
        patient_id=patient_id,
        message_id=message.id,
        check_after_hours=24
    )
    return result
```

**Impacto:** **ALTO** - Follow-ups de mensagens de flow não são rastreados

---

### **Bug #3: Async/Sync Mismatch in Celery Tasks**
**Localização:** `app/tasks/follow_up.py:63`

**Problema:**
```python
# ❌ asyncio.run() dentro de task Celery síncrona
try:
    asyncio.run(follow_up_service.rehydrate_from_redis())
except Exception as e:
    logger.warning(f"Failed to rehydrate from Redis: {e}")
```

**Causa:** Mixing async e sync em contexto Celery

**Correção:**
```python
# ✅ Usar helper para executar async em contexto sync
from app.utils.async_helpers import run_async_in_sync_context

try:
    run_async_in_sync_context(
        follow_up_service.rehydrate_from_redis()
    )
except Exception as e:
    logger.warning(f"Failed to rehydrate from Redis: {e}")
```

**Impacto:** **MÉDIO** - Pode causar deadlocks ou falhas de rehydration

---

### **Bug #4: Redis Fallback Inconsistency**
**Localização:** `app/tasks/follow_up.py:69-93`

**Problema:**
Lógica de fallback in-memory não sincroniza corretamente com Redis.

**Cenário de Falha:**
```
1. Redis disponível → Actions persistidas no Redis
2. Redis cai → Task usa in-memory fallback
3. Redis volta → Actions em in-memory NÃO são re-sincronizadas
4. Resultado: Ações perdidas
```

**Código Problemático:**
```python
# Se Redis retorna vazio, usa in-memory
if pending_action_dicts:
    for action_dict in pending_action_dicts:
        # Processa ações do Redis
else:
    # ❌ Fallback para in-memory pode estar desatualizado
    for action_id, action in list(follow_up_service.pending_actions.items()):
        actions_to_execute.append((action_id, action))
```

**Impacto:** **ALTO** - Perda de dados de follow-up

---

### **Bug #5: Flow Coordinator Decision Engine Not Integrated**
**Localização:** `app/agents/patient/flow_coordinator/coordinator.py`

**Problema:**
O FlowCoordinatorAgent tem engine de decisão sofisticado mas não é usado pelo FlowService.

**Gap de Integração:**
```python
# flow_service.py NÃO usa FlowCoordinatorAgent
class FlowService:
    def __init__(self, db):
        # ❌ FlowCoordinatorAgent não é inicializado
        self.enhanced_flow_engine = EnhancedFlowEngine(db)
        # Falta:
        # self.flow_coordinator = FlowCoordinatorAgent(db)
```

**Capabilities Perdidas:**
- Análise de progressão de flow
- Decisões baseadas em consenso multi-agente
- Otimização de timing baseada em engagement
- Personalização de conteúdo adaptativa

**Impacto:** **MÉDIO** - Funcionalidades avançadas de IA não são utilizadas

---

### **Bug #6: Message Status Callback Race Condition**
**Localização:** `app/domain/flows/core/message_handler.py:411-487`

**Problema:**
Callbacks de status de mensagem podem criar race conditions.

**Cenário:**
```
Thread 1: _on_flow_message_sent() → Updates flow_state
Thread 2: _on_flow_message_status_updated() → Updates flow_state
Resultado: Last write wins, dados podem ser perdidos
```

**Código Problemático:**
```python
async def _on_flow_message_sent(self, message, flow_context):
    flow_state.state_data["last_message_sent"] = {...}  # ❌ No lock
    self.db.commit()

async def _on_flow_message_status_updated(self, message, status, ...):
    flow_state.state_data["message_status_updates"].append(...)  # ❌ No lock
    self.db.commit()
```

**Impacto:** **MÉDIO** - Possível corrupção de state_data

---

## 🔗 Problemas de Integração

### **Integração #1: Follow-Up ↔ Flow Service**

**Status:** ❌ DESCONECTADO

**Problema:**
- FlowService envia mensagens diárias mas não registra no FollowUpSystem
- Follow-ups de respostas a mensagens de flow não são rastreados
- Nenhum checkpoint de verificação após envio de mensagem

**Solução Necessária:**
```python
# Em FlowService
async def _process_patient_daily_flow(self, flow_state):
    message = await self._send_message()

    # ✅ ADICIONAR: Registrar no follow-up system
    await self.follow_up_service.register_flow_message_sent(
        patient_id=patient_id,
        message_id=message.id,
        flow_day=current_day,
        expected_response_window_hours=24
    )
```

---

### **Integração #2: Flow Coordinator ↔ Flow Service**

**Status:** ⚠️ PARCIALMENTE CONECTADO

**Problema:**
- FlowCoordinatorAgent existe mas não é usado pelo FlowService
- Decisões de flow são baseadas em lógica simples ao invés do DecisionEngine
- Consensus Manager não é utilizado para decisões críticas

**Exemplo de Gap:**
```python
# FlowService usa lógica simples:
if current_day == 45:
    transition_to_monthly()

# Mas FlowCoordinatorAgent tem:
async def make_flow_decision(context, analysis):
    # - Análise de engagement
    # - Risk level assessment
    # - Consensus building
    # - Adaptive timing
    return FlowDecision  # Muito mais sofisticado
```

---

### **Integração #3: Redis Store ↔ In-Memory Fallback**

**Status:** ⚠️ IMPLEMENTADO MAS BUGGY

**Problema:**
- Rehydration de Redis funciona mas pode perder dados
- Fallback in-memory não sincroniza de volta para Redis quando volta
- Cleanup de ações antigas pode deletar dados do Redis sem sincronizar in-memory

**Cenário de Bug:**
```
1. Redis DOWN → Usa in-memory
2. Nova ação criada → Vai para in-memory
3. Redis UP → rehydrate_from_redis()
4. ❌ Ação em in-memory NÃO é transferida para Redis
5. Cleanup roda → Deleta ação antiga do in-memory
6. Resultado: Ação perdida
```

---

### **Integração #4: Flow Automation Tasks ↔ Follow-Up Tasks**

**Status:** ❌ INDEPENDENTES

**Problema:**
- `send_daily_flow_questions` (flow_automation.py) e `execute_pending_follow_ups` (follow_up.py) rodam separadamente
- Nenhuma coordenação entre eles
- Possível duplicação de mensagens
- Nenhum mecanismo de deduplicação

**Exemplo de Conflito:**
```
08:00 - flow_automation.send_daily_flow_questions()
        → Envia "Como você está hoje?"

08:05 - follow_up.execute_pending_follow_ups()
        → Envia follow-up empático da resposta de ontem
        → Possível: "Obrigado por compartilhar!"

Resultado: Paciente recebe 2 mensagens em 5 minutos
```

---

### **Integração #5: Message Handler Callbacks ↔ Follow-Up System**

**Status:** ⚠️ PARCIALMENTE CONECTADO

**Problema:**
- Callbacks de message handler atualizam flow_state mas não notificam follow-up system
- Follow-up system não monitora mudanças de status de mensagem
- Sem tracking de mensagens não respondidas

**Gap:**
```python
# message_handler.py
async def _on_flow_message_sent(self, message, flow_context):
    # Atualiza flow_state
    # ✅ Broadcast evento
    # ❌ NÃO registra no follow-up system

    # DEVERIA:
    await self.follow_up_service.track_message_sent(
        message_id=message.id,
        expected_response_hours=24
    )
```

---

## 📊 Análise de Risco

### **Riscos Críticos (P0)**

| Risco | Impacto | Probabilidade | Mitigação |
|-------|---------|---------------|-----------|
| **Perda de Follow-Up Actions** | Alto | Média | Implementar sync bidirecional Redis ↔ In-Memory |
| **Import Error em Production** | Alto | Alta | Corrigir import do FollowUpSystemService |
| **Deadlock em Celery Tasks** | Médio | Média | Usar async helpers apropriados |

### **Riscos Altos (P1)**

| Risco | Impacto | Probabilidade | Mitigação |
|-------|---------|---------------|-----------|
| **Mensagens Duplicadas** | Médio | Baixa | Implementar deduplicação |
| **Race Condition em Callbacks** | Médio | Média | Adicionar locks otimistas |
| **Flow Coordinator não utilizado** | Baixo | Alta | Integrar no FlowService |

---

## 🛠️ Recomendações de Correção

### **Prioridade Crítica (P0)**

#### **1. Corrigir Import do FollowUpSystemService**
```python
# Em app/tasks/follow_up.py linha 49
- from app.services.follow_up_system import FollowUpSystemService
+ from app.services.follow_up_system.service import FollowUpSystemService
```

**Teste:**
```bash
python -c "from app.services.follow_up_system.service import FollowUpSystemService; print('OK')"
```

#### **2. Implementar Sync Bidirecional Redis**
```python
# Em FollowUpSystemService
async def sync_memory_to_redis(self):
    """Sync in-memory actions back to Redis when it comes back online."""
    if not await self.redis_store.is_healthy():
        return

    for action_id, action in self.pending_actions.items():
        await self.redis_store.store_action(action)

    for alert_id, alert in self.active_alerts.items():
        await self.redis_store.store_alert(alert)
```

#### **3. Adicionar Integração Flow Service ↔ Follow-Up**
```python
# Em FlowService.__init__
from app.services.follow_up_system.service import get_follow_up_system_service

self.follow_up_service = get_follow_up_system_service(db)

# Em _process_patient_daily_flow
async def _process_patient_daily_flow(self, flow_state):
    # ... envio de mensagem ...

    # ✅ ADICIONAR
    await self.follow_up_service.register_flow_message(
        patient_id=patient_id,
        message_id=message.id,
        flow_context={
            "flow_day": current_day,
            "flow_type": flow_state.flow_type,
            "expected_response_hours": 24
        }
    )
```

---

### **Prioridade Alta (P1)**

#### **4. Implementar Deduplicação de Mensagens**
```python
# Nova classe: MessageDeduplicationService
class MessageDeduplicationService:
    def __init__(self, redis_client):
        self.redis = redis_client

    async def should_send_message(
        self,
        patient_id: UUID,
        message_type: str,
        content_hash: str,
        window_hours: int = 2
    ) -> bool:
        """Check if similar message was sent recently."""
        key = f"msg_dedup:{patient_id}:{message_type}:{content_hash}"

        if await self.redis.exists(key):
            return False  # Don't send, duplicate

        # Mark as sent
        await self.redis.setex(
            key,
            timedelta(hours=window_hours),
            "1"
        )
        return True  # OK to send
```

#### **5. Adicionar Locks Otimistas em Callbacks**
```python
# Em MessageHandler
async def _on_flow_message_sent(self, message, flow_context):
    max_retries = 3
    for attempt in range(max_retries):
        try:
            flow_state = self.flow_state_repo.get(flow_state_id)

            # ✅ Check version antes de atualizar
            original_version = flow_state.version

            flow_state.state_data["last_message_sent"] = {...}
            flow_state.version += 1

            # ✅ Commit com check de versão
            self.db.execute(
                "UPDATE patient_flow_states SET state_data = :data, version = :new_ver "
                "WHERE id = :id AND version = :old_ver",
                {
                    "data": flow_state.state_data,
                    "new_ver": flow_state.version,
                    "id": flow_state.id,
                    "old_ver": original_version
                }
            )

            if self.db.rowcount == 0:
                # ❌ Version mismatch, retry
                continue

            self.db.commit()
            break

        except Exception as e:
            if attempt == max_retries - 1:
                raise
            await asyncio.sleep(0.1 * (2 ** attempt))
```

#### **6. Integrar FlowCoordinatorAgent**
```python
# Em FlowService.__init__
from app.agents.patient.flow_coordinator import FlowCoordinatorAgent

self.flow_coordinator = FlowCoordinatorAgent(
    db_session=db,
    template_loader=template_loader
)

# Em _process_patient_daily_flow
async def _process_patient_daily_flow(self, flow_state):
    # ✅ Usar FlowCoordinator para decisões
    decision_result = await self.flow_coordinator.process_task({
        "type": "process_daily_flow",
        "payload": {
            "patient_id": str(patient_id),
            "current_day": current_day
        }
    })

    # Executar decisão
    if decision_result.get("success"):
        return decision_result
```

---

### **Prioridade Média (P2)**

#### **7. Adicionar Monitoring e Alertas**
```python
# Nova classe: FollowUpMonitoringService
class FollowUpMonitoringService:
    async def check_stale_actions(self):
        """Alert on actions pending > 6 hours."""
        stale_threshold = datetime.now(timezone.utc) - timedelta(hours=6)

        stale_actions = [
            action for action in self.pending_actions.values()
            if action.status == "pending"
            and action.scheduled_for < stale_threshold
        ]

        if stale_actions:
            logger.error(
                f"Found {len(stale_actions)} stale follow-up actions!"
            )
            # Send alert to monitoring system
```

#### **8. Implementar Health Checks Completos**
```python
# Em FollowUpSystemService
async def comprehensive_health_check(self) -> Dict[str, Any]:
    """Complete health check including integration points."""
    checks = {
        "redis_store": await self.redis_store.health_check(),
        "message_sender": await self.message_sender.health_check(),
        "escalation_manager": self.escalation_manager.is_healthy(),
        "pending_actions_count": len(self.pending_actions),
        "active_alerts_count": len(self.active_alerts),
        "stale_actions": await self._count_stale_actions(),
        "integration_status": {
            "flow_service": await self._check_flow_service_integration(),
            "flow_coordinator": await self._check_coordinator_integration()
        }
    }

    overall_healthy = all([
        checks["redis_store"].get("healthy"),
        checks["stale_actions"] == 0
    ])

    return {
        "healthy": overall_healthy,
        "checks": checks,
        "timestamp": datetime.now(timezone.utc).isoformat()
    }
```

---

## 📈 Métricas Recomendadas

### **Follow-Up System Metrics**

```python
# Adicionar em FollowUpSystemService
async def get_metrics(self) -> Dict[str, Any]:
    """Get comprehensive follow-up system metrics."""
    return {
        "actions": {
            "total_pending": len([a for a in self.pending_actions.values() if a.status == "pending"]),
            "total_completed": len([a for a in self.pending_actions.values() if a.status == "completed"]),
            "total_failed": len([a for a in self.pending_actions.values() if a.status == "failed"]),
            "by_type": self._count_by_type(),
            "avg_execution_time_seconds": self._calculate_avg_execution_time()
        },
        "alerts": {
            "total_active": len([a for a in self.active_alerts.values() if not a.resolved_at]),
            "total_resolved": len([a for a in self.active_alerts.values() if a.resolved_at]),
            "by_level": self._count_alerts_by_level(),
            "avg_resolution_time_hours": self._calculate_avg_resolution_time()
        },
        "storage": {
            "redis_healthy": (await self.redis_store.health_check()).get("healthy"),
            "fallback_active": not (await self.redis_store.is_healthy())
        }
    }
```

---

## 🧪 Testes Recomendados

### **Test Suite: Follow-Up System Integration**

```python
# tests/integration/test_follow_up_system.py

async def test_follow_up_flow_integration():
    """Test complete follow-up flow from patient response to execution."""

    # 1. Setup
    patient = create_test_patient()
    response = create_test_response(patient.id)

    # 2. Process response
    follow_up_service = get_follow_up_system_service(db)
    actions = await follow_up_service.process_response_follow_up(response)

    # 3. Verify actions created
    assert len(actions) > 0
    assert actions[0].status == "pending"

    # 4. Execute actions
    execution_result = await follow_up_service.execute_pending_actions()

    # 5. Verify execution
    assert execution_result["executed_count"] > 0
    assert execution_result["failed_count"] == 0


async def test_redis_fallback_sync():
    """Test Redis fallback and sync back when Redis recovers."""

    # 1. Start with Redis healthy
    service = get_follow_up_system_service(db)
    action = create_test_action()
    await service.action_scheduler.schedule_action(action)

    # 2. Verify in Redis
    redis_data = await service.redis_store.get_action(action.action_id)
    assert redis_data is not None

    # 3. Simulate Redis failure
    await service.redis_store._simulate_failure()

    # 4. Create action (should go to in-memory)
    action2 = create_test_action()
    await service.action_scheduler.schedule_action(action2)
    assert action2.action_id in service.pending_actions

    # 5. Redis recovers
    await service.redis_store._simulate_recovery()
    await service.sync_memory_to_redis()

    # 6. Verify both actions in Redis
    redis_data2 = await service.redis_store.get_action(action2.action_id)
    assert redis_data2 is not None


async def test_message_deduplication():
    """Test message deduplication prevents duplicate sends."""

    dedup_service = MessageDeduplicationService(redis_client)
    patient_id = uuid4()
    message_type = "empathetic_response"
    content = "Obrigado por compartilhar!"
    content_hash = hashlib.md5(content.encode()).hexdigest()

    # 1. First send should be OK
    should_send_1 = await dedup_service.should_send_message(
        patient_id, message_type, content_hash
    )
    assert should_send_1 is True

    # 2. Second send (within window) should be blocked
    should_send_2 = await dedup_service.should_send_message(
        patient_id, message_type, content_hash
    )
    assert should_send_2 is False

    # 3. After window expires, should be OK again
    await asyncio.sleep(2 * 3600)  # Wait 2 hours
    should_send_3 = await dedup_service.should_send_message(
        patient_id, message_type, content_hash
    )
    assert should_send_3 is True
```

---

## 📝 Checklist de Implementação

### **Fase 1: Correções Críticas (1-2 dias)**
- [ ] Corrigir import do FollowUpSystemService
- [ ] Implementar sync bidirecional Redis ↔ In-Memory
- [ ] Adicionar integração básica FlowService ↔ Follow-Up
- [ ] Testar em ambiente de desenvolvimento
- [ ] Deploy para staging

### **Fase 2: Integrações (3-5 dias)**
- [ ] Implementar deduplicação de mensagens
- [ ] Adicionar locks otimistas em callbacks
- [ ] Integrar FlowCoordinatorAgent no FlowService
- [ ] Criar testes de integração
- [ ] Code review e ajustes

### **Fase 3: Monitoring (2-3 dias)**
- [ ] Implementar métricas de follow-up
- [ ] Adicionar health checks completos
- [ ] Configurar alertas para ações stale
- [ ] Dashboard de monitoring
- [ ] Documentação operacional

---

## 🎯 Conclusão

O sistema de follow-up tem uma arquitetura bem desenhada mas sofre de problemas de integração que podem causar perda de dados e funcionalidades não utilizadas.

### **Principais Achados:**
1. **FollowUpSystemService** bem estruturado mas desconectado do FlowService
2. **FlowCoordinatorAgent** sofisticado mas não utilizado
3. **Redis fallback** implementado mas com bugs de sincronização
4. **Message callbacks** sem proteção contra race conditions
5. **Deduplicação** de mensagens ausente

### **Próximos Passos:**
1. Implementar correções críticas (P0)
2. Adicionar testes de integração
3. Melhorar monitoring e observabilidade
4. Documentar fluxos completos
5. Training da equipe sobre o sistema

---

**Responsável pela Análise:** Claude Code Quality Analyzer
**Versão do Relatório:** 1.0
**Última Atualização:** 2025-12-24
