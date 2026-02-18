# Follow-Up System - Guia Rápido de Correção

**Versão:** 1.0
**Data:** 2025-12-24
**Objetivo:** Correções prioritárias para o sistema de follow-up

---

## 🚨 Correções Críticas Imediatas

### **Fix #1: Import Error (5 minutos)**

**Arquivo:** `/mnt/c/Meu Projetos/clinica-oncologica-v02-1/backend-hormonia/app/tasks/follow_up.py`

**Linha:** 49

**Mudar de:**
```python
from app.services.follow_up_system import FollowUpSystemService
```

**Para:**
```python
from app.services.follow_up_system.service import FollowUpSystemService
```

**Verificar:**
```bash
cd /mnt/c/Meu\ Projetos/clinica-oncologica-v02-1/backend-hormonia
python3 -c "from app.services.follow_up_system.service import FollowUpSystemService; print('✅ Import OK')"
```

---

### **Fix #2: Redis Sync Bidirecional (30 minutos)**

**Arquivo:** `/mnt/c/Meu Projetos/clinica-oncologica-v02-1/backend-hormonia/app/services/follow_up_system/service.py`

**Adicionar método após `rehydrate_from_redis()`:**

```python
async def sync_memory_to_redis(self) -> Dict[str, int]:
    """
    Sync in-memory state back to Redis when it recovers.

    Called after Redis recovery to persist any actions/alerts
    created while Redis was down.

    Returns:
        Dict with sync statistics
    """
    synced = {"actions": 0, "alerts": 0, "errors": 0}

    try:
        # Check if Redis is healthy
        if not await self.redis_store.is_healthy():
            logger.warning("Redis not healthy, skipping sync")
            return synced

        # Sync pending actions
        for action_id, action in list(self.pending_actions.items()):
            try:
                # Check if already in Redis
                existing = await self.redis_store.get_action(action_id)
                if not existing:
                    # Store new action
                    await self.redis_store.store_action(
                        action_id=action.action_id,
                        patient_id=action.patient_id,
                        follow_up_type=action.follow_up_type.value,
                        priority=action.priority,
                        scheduled_for=action.scheduled_for,
                        parameters=action.parameters,
                        status=action.status,
                        created_at=action.created_at,
                        created_by=action.created_by
                    )
                    synced["actions"] += 1
            except Exception as e:
                logger.error(f"Failed to sync action {action_id}: {e}")
                synced["errors"] += 1

        # Sync active alerts
        for alert_id, alert in list(self.active_alerts.items()):
            try:
                existing = await self.redis_store.get_alert(alert_id)
                if not existing:
                    await self.redis_store.store_alert(
                        alert_id=alert.alert_id,
                        patient_id=alert.patient_id,
                        escalation_level=alert.escalation_level.value,
                        concern_type=alert.concern_type.value,
                        description=alert.description,
                        original_message=alert.original_message,
                        recommended_actions=alert.recommended_actions,
                        notification_channels=[ch.value for ch in alert.notification_channels],
                        requires_immediate_response=alert.requires_immediate_response,
                        created_at=alert.created_at
                    )
                    synced["alerts"] += 1
            except Exception as e:
                logger.error(f"Failed to sync alert {alert_id}: {e}")
                synced["errors"] += 1

        logger.info(
            f"Memory→Redis sync complete: {synced['actions']} actions, "
            f"{synced['alerts']} alerts, {synced['errors']} errors"
        )
        return synced

    except Exception as e:
        logger.error(f"Memory→Redis sync failed: {e}", exc_info=True)
        return synced
```

**Atualizar `execute_pending_follow_ups` task:**

```python
# Em app/tasks/follow_up.py, após rehydrate_from_redis (linha ~66)

# Rehydrate state from Redis before processing
try:
    asyncio.run(follow_up_service.rehydrate_from_redis())
except Exception as e:
    logger.warning(f"Failed to rehydrate from Redis: {e}")

# ✅ ADICIONAR: Sync memory back to Redis if it just recovered
try:
    asyncio.run(follow_up_service.sync_memory_to_redis())
except Exception as e:
    logger.warning(f"Failed to sync memory to Redis: {e}")
```

---

### **Fix #3: FlowService Integration (45 minutos)**

**Arquivo:** `/mnt/c/Meu Projetos/clinica-oncologica-v02-1/backend-hormonia/app/domain/flows/core/flow_service.py`

**Passo 1:** Adicionar importação no `__init__`:

```python
# Linha ~26, após outros imports
from app.services.follow_up_system.service import get_follow_up_system_service
```

**Passo 2:** Inicializar no construtor:

```python
# Em FlowService.__init__ (linha ~86)
def __init__(
    self,
    db: Session,
    enhanced_flow_engine: Optional[EnhancedFlowEngine] = None,
    message_scheduler: Optional[MessageScheduler] = None,
    message_sender: Optional[MessageSender] = None,
    template_loader: Optional[EnhancedTemplateLoader] = None,
    analytics_service: Optional[FlowAnalyticsService] = None,
    use_unified_service: bool = True,
):
    self.db = db
    self._logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")

    # ... código existente ...

    # ✅ ADICIONAR: Initialize follow-up service
    try:
        self.follow_up_service = get_follow_up_system_service(db)
        self._logger.info("Follow-up service initialized successfully")
    except Exception as e:
        self._logger.warning(f"Failed to initialize follow-up service: {e}")
        self.follow_up_service = None
```

**Passo 3:** Adicionar método de integração:

```python
# Adicionar novo método na classe FlowService
async def register_flow_message_for_followup(
    self,
    patient_id: UUID,
    message_id: UUID,
    flow_context: dict[str, Any]
) -> bool:
    """
    Register flow message in follow-up system for tracking.

    Args:
        patient_id: Patient UUID
        message_id: Sent message UUID
        flow_context: Flow metadata (day, type, etc.)

    Returns:
        True if registered successfully
    """
    if not self.follow_up_service:
        logger.warning("Follow-up service not available")
        return False

    try:
        # Schedule follow-up check after 24 hours
        from datetime import timedelta
        from app.services.follow_up_system.models import FollowUpAction
        from app.services.follow_up_system.enums import FollowUpType

        check_time = now_sao_paulo() + timedelta(hours=24)

        action = FollowUpAction(
            action_id=uuid4(),
            patient_id=patient_id,
            follow_up_type=FollowUpType.CONVERSATION_CONTINUATION,
            priority="medium",
            scheduled_for=check_time,
            parameters={
                "message_id": str(message_id),
                "flow_day": flow_context.get("flow_day"),
                "flow_type": flow_context.get("flow_type"),
                "check_type": "response_expected"
            },
            created_by="flow_service"
        )

        # Schedule the action
        await self.follow_up_service._schedule_action_by_type(action)

        logger.info(
            f"Registered flow message {message_id} for follow-up check at {check_time}"
        )
        return True

    except Exception as e:
        logger.error(f"Failed to register message for follow-up: {e}")
        return False
```

**Passo 4:** Integrar no `_process_patient_daily_flow`:

```python
# Em _process_patient_daily_flow (linha ~252, após message_result)

# Create and schedule message
message_result = await self.message_handler.create_and_schedule_flow_message(
    patient_id,
    flow_state,
    message_template,
    personalized_content,
    current_day,
    send_time,
)

# ✅ ADICIONAR: Register for follow-up
if message_result and self.follow_up_service:
    await self.register_flow_message_for_followup(
        patient_id=patient_id,
        message_id=message_result.get("message_id"),  # Assumindo que message_result retorna ID
        flow_context={
            "flow_day": current_day,
            "flow_type": flow_state.flow_type,
            "template_intent": message_template.intent
        }
    )
```

---

## 🔧 Correções Importantes (P1)

### **Fix #4: Message Deduplication (1 hora)**

**Criar novo arquivo:** `/mnt/c/Meu Projetos/clinica-oncologica-v02-1/backend-hormonia/app/services/message_deduplication.py`

```python
"""
Message Deduplication Service.

Prevents duplicate messages from being sent to patients
within a configurable time window.
"""

import hashlib
import logging
from datetime import timedelta
from typing import Optional
from uuid import UUID

from app.core.redis_unified import get_async_redis

logger = logging.getLogger(__name__)


class MessageDeduplicationService:
    """
    Prevents duplicate messages using Redis-backed cache.

    Uses content hash + patient ID + message type to detect duplicates.
    """

    def __init__(self, redis_client=None):
        """Initialize with Redis client."""
        self.redis = redis_client or get_async_redis()
        self.default_window_hours = 2

    def _generate_content_hash(self, content: str) -> str:
        """Generate hash of message content."""
        normalized = content.strip().lower()
        return hashlib.md5(normalized.encode('utf-8')).hexdigest()

    async def should_send_message(
        self,
        patient_id: UUID,
        message_type: str,
        content: str,
        window_hours: Optional[int] = None
    ) -> bool:
        """
        Check if message should be sent.

        Args:
            patient_id: Patient UUID
            message_type: Type of message (flow, follow_up, etc.)
            content: Message content
            window_hours: Deduplication window in hours (default: 2)

        Returns:
            True if message should be sent (no duplicate), False otherwise
        """
        try:
            content_hash = self._generate_content_hash(content)
            window = window_hours or self.default_window_hours

            # Build cache key
            key = f"msg_dedup:{patient_id}:{message_type}:{content_hash}"

            # Check if exists
            exists = await self.redis.exists(key)

            if exists:
                logger.info(
                    f"Duplicate message detected for patient {patient_id}, "
                    f"type: {message_type}, blocking send"
                )
                return False  # Don't send, duplicate detected

            # Mark as sent
            await self.redis.setex(
                key,
                timedelta(hours=window),
                "1"
            )

            logger.debug(
                f"Message approved for patient {patient_id}, "
                f"type: {message_type}, cached for {window}h"
            )
            return True  # OK to send

        except Exception as e:
            logger.error(f"Deduplication check failed: {e}, defaulting to SEND")
            # Fail open: if check fails, allow send
            return True

    async def mark_as_sent(
        self,
        patient_id: UUID,
        message_type: str,
        content: str,
        window_hours: Optional[int] = None
    ) -> bool:
        """
        Manually mark message as sent (for external tracking).

        Use when message is sent through another system but you want
        to prevent duplicates here.
        """
        try:
            content_hash = self._generate_content_hash(content)
            window = window_hours or self.default_window_hours

            key = f"msg_dedup:{patient_id}:{message_type}:{content_hash}"

            await self.redis.setex(
                key,
                timedelta(hours=window),
                "1"
            )

            logger.info(f"Message manually marked as sent: {key}")
            return True

        except Exception as e:
            logger.error(f"Failed to mark message as sent: {e}")
            return False

    async def clear_patient_cache(self, patient_id: UUID) -> int:
        """
        Clear all deduplication cache for a patient.

        Use when you want to allow resending messages immediately.

        Returns:
            Number of keys deleted
        """
        try:
            pattern = f"msg_dedup:{patient_id}:*"
            keys = await self.redis.keys(pattern)

            if keys:
                deleted = await self.redis.delete(*keys)
                logger.info(
                    f"Cleared {deleted} deduplication entries for patient {patient_id}"
                )
                return deleted

            return 0

        except Exception as e:
            logger.error(f"Failed to clear patient cache: {e}")
            return 0


# Singleton instance
_deduplication_service = None


def get_message_deduplication_service() -> MessageDeduplicationService:
    """Get singleton message deduplication service."""
    global _deduplication_service
    if _deduplication_service is None:
        _deduplication_service = MessageDeduplicationService()
    return _deduplication_service
```

**Integrar no MessageHandler:**

```python
# Em app/domain/flows/core/message_handler.py

from app.services.message_deduplication import get_message_deduplication_service

class MessageHandler:
    def __init__(self, ...):
        # ... código existente ...
        self.dedup_service = get_message_deduplication_service()

    async def create_and_schedule_flow_message(
        self,
        patient_id: UUID,
        flow_state: PatientFlowState,
        message_template: MessageTemplate,
        personalized_content: str,
        current_day: int,
        send_time: datetime,
    ) -> bool:
        # ✅ ADICIONAR: Check for duplicates BEFORE creating message
        should_send = await self.dedup_service.should_send_message(
            patient_id=patient_id,
            message_type="flow_message",
            content=personalized_content,
            window_hours=2  # 2-hour dedup window
        )

        if not should_send:
            logger.warning(
                f"Skipping duplicate message for patient {patient_id} "
                f"on day {current_day}"
            )
            return False

        # ... resto do código de criação de mensagem ...
```

---

## 🧪 Testes Rápidos

### **Test Script: Verificar Correções**

**Criar:** `/mnt/c/Meu Projetos/clinica-oncologica-v02-1/backend-hormonia/tests/quick_follow_up_test.py`

```python
"""Quick test script for follow-up system fixes."""

import asyncio
import sys
from uuid import uuid4

# Add project to path
sys.path.insert(0, '/mnt/c/Meu Projetos/clinica-oncologica-v02-1/backend-hormonia')

from app.services.follow_up_system.service import get_follow_up_system_service
from app.services.message_deduplication import get_message_deduplication_service
from app.tasks.base import get_db_session


async def test_imports():
    """Test critical imports."""
    print("🧪 Testing imports...")

    try:
        from app.services.follow_up_system.service import FollowUpSystemService
        print("✅ FollowUpSystemService import OK")
    except ImportError as e:
        print(f"❌ FollowUpSystemService import FAILED: {e}")
        return False

    try:
        from app.services.message_deduplication import MessageDeduplicationService
        print("✅ MessageDeduplicationService import OK")
    except ImportError as e:
        print(f"❌ MessageDeduplicationService import FAILED: {e}")
        return False

    return True


async def test_follow_up_service():
    """Test follow-up service initialization."""
    print("\n🧪 Testing follow-up service...")

    try:
        with get_db_session() as db:
            service = get_follow_up_system_service(db)
            print("✅ Service initialized OK")

            # Test health check
            health = await service.health_check()
            if health.get("healthy"):
                print("✅ Service health check PASSED")
            else:
                print(f"⚠️ Service health check FAILED: {health}")

            return True
    except Exception as e:
        print(f"❌ Service test FAILED: {e}")
        return False


async def test_deduplication():
    """Test message deduplication."""
    print("\n🧪 Testing message deduplication...")

    try:
        dedup = get_message_deduplication_service()
        patient_id = uuid4()
        content = "Test message content"

        # First send should be OK
        should_send_1 = await dedup.should_send_message(
            patient_id=patient_id,
            message_type="test",
            content=content
        )
        if not should_send_1:
            print("❌ First send should be allowed")
            return False
        print("✅ First send allowed")

        # Second send (duplicate) should be blocked
        should_send_2 = await dedup.should_send_message(
            patient_id=patient_id,
            message_type="test",
            content=content
        )
        if should_send_2:
            print("❌ Duplicate send should be blocked")
            return False
        print("✅ Duplicate send blocked")

        # Clear cache and try again
        cleared = await dedup.clear_patient_cache(patient_id)
        print(f"✅ Cleared {cleared} cache entries")

        should_send_3 = await dedup.should_send_message(
            patient_id=patient_id,
            message_type="test",
            content=content
        )
        if not should_send_3:
            print("❌ Send after clear should be allowed")
            return False
        print("✅ Send after cache clear allowed")

        return True

    except Exception as e:
        print(f"❌ Deduplication test FAILED: {e}")
        return False


async def main():
    """Run all quick tests."""
    print("=" * 60)
    print("Follow-Up System Quick Test Suite")
    print("=" * 60)

    results = []

    # Test imports
    results.append(await test_imports())

    # Test follow-up service
    results.append(await test_follow_up_service())

    # Test deduplication
    results.append(await test_deduplication())

    # Summary
    print("\n" + "=" * 60)
    print("Test Summary")
    print("=" * 60)
    passed = sum(results)
    total = len(results)
    print(f"Passed: {passed}/{total}")

    if passed == total:
        print("✅ All tests PASSED!")
        return 0
    else:
        print("❌ Some tests FAILED!")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
```

**Executar:**
```bash
cd /mnt/c/Meu\ Projetos/clinica-oncologica-v02-1/backend-hormonia
python tests/quick_follow_up_test.py
```

---

## 📋 Checklist de Deploy

### **Pré-Deploy**
- [ ] Executar `quick_follow_up_test.py` com sucesso
- [ ] Verificar imports manualmente
- [ ] Testar deduplicação em desenvolvimento
- [ ] Code review das mudanças

### **Deploy para Staging**
- [ ] Backup do Redis atual
- [ ] Deploy das alterações
- [ ] Verificar logs de follow-up tasks
- [ ] Monitorar métricas de execução
- [ ] Testar manualmente follow-up flow

### **Deploy para Produção**
- [ ] Todas validações de staging passaram
- [ ] Plano de rollback preparado
- [ ] Deploy em horário de baixo tráfego
- [ ] Monitoring ativo por 24h
- [ ] Validação de métricas

---

## 🆘 Troubleshooting

### **Problema: Import Error Persiste**

```bash
# Verificar estrutura do módulo
ls -la /mnt/c/Meu\ Projetos/clinica-oncologica-v02-1/backend-hormonia/app/services/follow_up_system/

# Deve mostrar:
# - service.py
# - __init__.py
# - context/
# - execution/
# - generators/
# - scheduling/
```

**Solução:**
```python
# Verificar se __init__.py exporta a classe
# Em app/services/follow_up_system/__init__.py
from .service import FollowUpSystemService, get_follow_up_system_service

__all__ = ["FollowUpSystemService", "get_follow_up_system_service"]
```

---

### **Problema: Redis Sync Não Funciona**

```python
# Test Redis connectivity
import asyncio
from app.core.redis_unified import get_async_redis

async def test_redis():
    redis = get_async_redis()
    await redis.set("test_key", "test_value")
    value = await redis.get("test_key")
    print(f"Redis test: {value}")
    await redis.delete("test_key")

asyncio.run(test_redis())
```

**Solução:**
- Verificar se Redis está rodando
- Verificar configuração de conexão
- Verificar logs de erro do Redis

---

### **Problema: Deduplicação Muito Agressiva**

**Sintoma:** Mensagens legítimas sendo bloqueadas

**Solução:**
```python
# Aumentar window ou fazer hash mais específico
await dedup.should_send_message(
    patient_id=patient_id,
    message_type="flow_message",
    content=content,
    window_hours=1  # Reduzir de 2h para 1h
)

# Ou limpar cache manualmente
await dedup.clear_patient_cache(patient_id)
```

---

## 📞 Contato e Suporte

**Dúvidas sobre este guia:**
- Verificar relatório completo em `FOLLOW_UP_SYSTEM_DEBUG_REPORT.md`
- Consultar código-fonte com comentários inline
- Executar tests de validação

**Prioridades:**
1. Fix #1 (Import) - **CRÍTICO**
2. Fix #2 (Redis Sync) - **CRÍTICO**
3. Fix #3 (FlowService Integration) - **ALTO**
4. Fix #4 (Deduplicação) - **MÉDIO**

---

**Última Atualização:** 2025-12-24
**Versão:** 1.0
**Status:** ✅ Pronto para implementação
