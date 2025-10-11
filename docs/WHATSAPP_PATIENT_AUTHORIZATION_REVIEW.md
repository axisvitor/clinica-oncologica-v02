# Revisão de Autorização de Pacientes no WhatsApp

**Data**: 2025-10-11
**Status**: ✅ **SISTEMA POSSUI AUTORIZAÇÃO BÁSICA FUNCIONAL**
**Escopo**: Análise completa do controle de acesso via WhatsApp
**Objetivo**: Garantir que apenas pacientes cadastrados possam interagir com o sistema

---

## 📊 Resumo Executivo

O sistema **JÁ POSSUI** um mecanismo básico de autorização que **bloqueia** mensagens de números não cadastrados. A implementação atual é **funcional** mas **silenciosa** - mensagens de não cadastrados são simplesmente ignoradas sem notificação ao remetente.

**Status Atual**: ✅ **7/10 - Funcional com melhorias recomendadas**

---

## 🔒 Mecanismo de Autorização Atual

### Fluxo de Validação (webhook_processor.py)

```python
# Linha 137-142 do webhook_processor.py
# Step 3: Find patient by phone number
patient = self._find_patient_by_phone(message_data["phone"])
if not patient:
    logger.warning(f"Patient not found for phone: {message_data['phone']}")
    # Future: Could implement auto-registration here
    return None  # ❌ Mensagem bloqueada aqui
```

**Como Funciona**:

1. **Webhook recebido** da Evolution API com mensagem do WhatsApp
2. **Número extraído** e normalizado para formato E.164 (+5511...)
3. **Busca no banco de dados** usando múltiplas estratégias de normalização:
   - E.164 com + (+5511987654321)
   - Sem + (5511987654321)
   - Com código de país adicionado
   - Últimos 10-11 dígitos (DDD + número)
4. **Se paciente NÃO encontrado**: Retorna `None` e **bloqueia** processamento
5. **Se paciente encontrado**: Prossegue com flow normal

---

## ✅ Pontos Fortes da Implementação Atual

### 1. **Validação Rigorosa** ✅

**Código**: `webhook_processor.py:615-691`

O sistema realiza **6 tentativas** de busca com diferentes formatos:

```python
def _find_patient_by_phone(self, phone: str) -> Optional[Patient]:
    # Strategy 1: E.164 format com + (+55...)
    # Strategy 2: Sem + prefix (55...)
    # Strategy 3: Adicionar +55 se ausente
    # Strategy 4: Também sem + (55{phone})
    # Strategy 5: Últimos 11 dígitos locais
    # Strategy 6: Últimos 10 dígitos locais
```

**Resultado**: Minimiza falsos negativos (pacientes legítimos rejeitados)

### 2. **Logging Compreensivo** ✅

**Código**: `webhook_processor.py:682-686`

```python
logger.warning(
    f"Patient not found after all phone lookup strategies. "
    f"Original: {phone}, Normalized: {normalized}, Tried: "
    f"[{normalized}, {without_plus}, +55{phone}, 55{phone}]"
)
```

**Benefício**: Facilita debug e auditoria de tentativas de acesso não autorizado

### 3. **Persistência de Webhooks** ✅

**Código**: `webhook_processor.py:97-102`

```python
# Step 0: Persist webhook event first (P0 FIX #2)
webhook_id = await self._persist_webhook_event(
    event_type="message.received",
    source="evolution_api",
    payload=event_data
)
```

**Benefício**: **Todos os webhooks** (incluindo de não cadastrados) são salvos na tabela `webhook_events` para **audit trail completo**

### 4. **Idempotência** ✅

**Código**: `webhook_processor.py:114-135`

O sistema previne processamento duplicado usando:
- Redis para cache rápido
- Database fallback para garantia
- Hash de evento para deduplicação

---

## ⚠️ Áreas de Melhoria Identificadas

### 1. **Falta de Notificação ao Usuário Não Autorizado** ⚠️

**Problema Atual**:
Quando um número não cadastrado envia mensagem, o webhook é bloqueado silenciosamente. O usuário não recebe nenhuma resposta explicando que ele não está autorizado.

**Impacto**:
- Usuário fica sem feedback
- Pode tentar repetidamente sem entender o motivo
- Má experiência de usuário

**Recomendação**: Implementar resposta automática informativa

---

### 2. **Ausência de Rate Limiting para Não Cadastrados** ⚠️

**Problema Atual**:
Não há proteção contra spam/abuso de números não autorizados enviando muitas mensagens.

**Impacto**:
- Logs podem ser poluídos
- Processamento de webhook desperdiçado
- Potencial DoS por webhook flood

**Recomendação**: Implementar rate limiting específico

---

### 3. **Falta de Audit Log Específico** ⚠️

**Problema Atual**:
Tentativas não autorizadas são logadas como warnings genéricos, não como eventos de segurança específicos.

**Impacto**:
- Dificulta análise de padrões de ataque
- Não integra com sistemas de monitoramento de segurança
- Não gera alertas para admin

**Recomendação**: Criar eventos de audit log dedicados

---

### 4. **Sem Bloqueio Permanente** ⚠️

**Problema Atual**:
Números que tentam acesso repetidamente não são bloqueados permanentemente.

**Impacto**:
- Permite tentativas infinitas
- Não previne abuso sistemático

**Recomendação**: Implementar blacklist temporária/permanente

---

## 🎯 Análise de Segurança

### Vetores de Ataque Identificados

| Vetor | Status Atual | Risco | Mitigação Atual |
|-------|--------------|-------|-----------------|
| **Spoofing de Número** | ⚠️ Parcial | Médio | Evolution API valida origem, mas não 2FA |
| **Webhook Flood** | ⚠️ Parcial | Médio | Sem rate limiting específico |
| **Enumeração de Números** | ✅ Protegido | Baixo | Resposta silenciosa não revela cadastrados |
| **Replay Attack** | ✅ Protegido | Baixo | Idempotência via whatsapp_id |
| **Man-in-the-Middle** | ✅ Protegido | Baixo | HMAC-SHA256 webhook signature |

### Pontos Críticos de Segurança

**✅ Implementados**:
1. Webhook signature validation (HMAC-SHA256) - **P0 FIX #1**
2. Idempotência de mensagens (Redis + DB)
3. Logging de todas as tentativas
4. Persistência de eventos para audit trail

**⚠️ Faltando**:
1. Rate limiting para não cadastrados
2. Blacklist temporária para abusadores
3. Notificação ao admin de tentativas suspeitas
4. Métricas de tentativas não autorizadas

---

## 📋 Checklist de Conformidade

### Controle de Acesso ✅
- [x] Apenas pacientes cadastrados processam mensagens
- [x] Validação de número de telefone rigorosa
- [x] Múltiplas estratégias de normalização
- [x] Bloqueio de números não encontrados
- [ ] ⚠️ Resposta automática para não autorizados

### Auditoria e Logging ✅
- [x] Webhooks persistidos em `webhook_events`
- [x] Logs de tentativas não autorizadas
- [x] Rastreamento de número original e normalizado
- [ ] ⚠️ Eventos de segurança em `audit_logs`
- [ ] ⚠️ Métricas de tentativas não autorizadas

### Proteção contra Abuso ⚠️
- [x] Idempotência de webhooks
- [x] Validação de signature (HMAC-SHA256)
- [ ] ⚠️ Rate limiting para não cadastrados
- [ ] ⚠️ Blacklist temporária
- [ ] ⚠️ Alertas de abuso

### Experiência do Usuário ⚠️
- [x] Pacientes cadastrados têm experiência normal
- [ ] ⚠️ Não cadastrados recebem feedback claro
- [ ] ⚠️ Instruções de como se cadastrar

---

## 🔧 Recomendações de Implementação

### Prioridade 1: Resposta Automática para Não Cadastrados

**Objetivo**: Informar usuário que ele não está autorizado

**Implementação** (`webhook_processor.py:138-142`):

```python
patient = self._find_patient_by_phone(message_data["phone"])
if not patient:
    logger.warning(f"Patient not found for phone: {message_data['phone']}")

    # NEW: Send unauthorized response via Evolution API
    await self._send_unauthorized_response(
        phone=message_data["phone"],
        message="Olá! Este número não está cadastrado no sistema de acompanhamento da clínica. "
                "Para se cadastrar, entre em contato com a recepção pelo telefone (11) XXXX-XXXX "
                "ou visite nosso site: https://clinica.example.com/cadastro"
    )

    # Log security event (NEW)
    await self._log_unauthorized_attempt(
        phone=message_data["phone"],
        message_content=message_data["content"],
        webhook_id=webhook_id
    )

    return None
```

**Tempo Estimado**: 2 horas
**Impacto**: Alto - Melhora UX e clareza

---

### Prioridade 2: Rate Limiting para Não Cadastrados

**Objetivo**: Prevenir flood de webhooks de números não autorizados

**Implementação** (`webhook_processor.py:138-142`):

```python
patient = self._find_patient_by_phone(message_data["phone"])
if not patient:
    # NEW: Check rate limit before processing
    redis_client = await get_async_redis()
    rate_limit_key = f"unauthorized:ratelimit:{message_data['phone']}"

    # Allow 5 messages per hour for unauthorized numbers
    attempt_count = await redis_client.incr(rate_limit_key)
    if attempt_count == 1:
        await redis_client.expire(rate_limit_key, 3600)  # 1 hour TTL

    if attempt_count > 5:
        logger.warning(f"Rate limit exceeded for unauthorized phone: {message_data['phone']}")
        # Don't send response, just block silently after 5 attempts
        return None

    # Send response only for first 5 attempts
    await self._send_unauthorized_response(...)
    return None
```

**Tempo Estimado**: 1 hora
**Impacto**: Médio - Previne abuso

---

### Prioridade 3: Audit Log de Segurança

**Objetivo**: Rastrear tentativas não autorizadas como eventos de segurança

**Implementação** (novo método):

```python
async def _log_unauthorized_attempt(
    self,
    phone: str,
    message_content: str,
    webhook_id: UUID
) -> None:
    """
    Log unauthorized access attempt to audit_logs table.

    Args:
        phone: Phone number that attempted access
        message_content: Content of the message
        webhook_id: Related webhook event ID
    """
    from app.models.audit_log import AuditLog, AuditEventType

    try:
        audit_entry = AuditLog(
            event_type=AuditEventType.ACCESS_DENIED,
            event_status="failure",
            user_id=None,  # No user ID for unauthorized
            user_email=None,
            ip_address=None,  # WhatsApp doesn't provide IP
            user_agent="WhatsApp/Evolution API",
            resource="whatsapp/message",
            action="send_message",
            event_metadata={
                "phone": phone,
                "message_preview": message_content[:100],  # First 100 chars only
                "webhook_id": str(webhook_id),
                "reason": "patient_not_found",
                "normalized_phone": self._normalize_phone_e164(phone)
            },
            message=f"Unauthorized WhatsApp message attempt from {phone}"
        )

        self.db.add(audit_entry)
        self.db.commit()

        logger.info(f"Logged unauthorized attempt from {phone} to audit_logs")

    except Exception as e:
        logger.error(f"Failed to log unauthorized attempt: {e}", exc_info=True)
```

**Tempo Estimado**: 2 horas
**Impacto**: Alto - Melhora auditoria e segurança

---

### Prioridade 4: Blacklist Temporária

**Objetivo**: Bloquear números abusivos temporariamente

**Implementação**:

```python
async def _check_blacklist(self, phone: str) -> bool:
    """
    Check if phone number is temporarily blacklisted.

    Auto-blacklist after 10 attempts in 1 hour.
    Blacklist duration: 24 hours

    Returns:
        True if blacklisted, False otherwise
    """
    redis_client = await get_async_redis()

    # Check if already blacklisted
    blacklist_key = f"unauthorized:blacklist:{phone}"
    is_blacklisted = await redis_client.exists(blacklist_key)

    if is_blacklisted:
        logger.warning(f"Phone {phone} is blacklisted")
        return True

    # Check attempt count
    attempt_key = f"unauthorized:attempts:{phone}"
    attempts = await redis_client.get(attempt_key)

    if attempts and int(attempts) >= 10:
        # Blacklist for 24 hours
        await redis_client.setex(blacklist_key, 86400, "1")
        logger.warning(f"Phone {phone} auto-blacklisted after {attempts} attempts")

        # Send notification to admin
        await self._notify_admin_blacklist(phone, int(attempts))

        return True

    return False
```

**Tempo Estimado**: 3 horas
**Impacto**: Médio - Previne abuso persistente

---

## 📊 Métricas Recomendadas

### Métricas de Segurança para Dashboard Admin

```python
# /api/v1/admin/security/whatsapp-unauthorized

class WhatsAppUnauthorizedMetrics:
    """Métricas de tentativas não autorizadas."""

    total_unauthorized_attempts: int  # Total de tentativas
    unique_unauthorized_numbers: int  # Números únicos
    blacklisted_numbers: int  # Números na blacklist
    attempts_last_hour: int  # Tentativas na última hora
    attempts_last_24h: int  # Tentativas em 24h
    top_offenders: List[Dict]  # Top 10 números com mais tentativas

    # Exemplo de output:
    {
        "total_unauthorized_attempts": 47,
        "unique_unauthorized_numbers": 12,
        "blacklisted_numbers": 2,
        "attempts_last_hour": 5,
        "attempts_last_24h": 23,
        "top_offenders": [
            {"phone": "+5511987654321", "attempts": 15, "last_attempt": "2025-10-11T05:30:00Z"},
            {"phone": "+5511999888777", "attempts": 8, "last_attempt": "2025-10-11T04:15:00Z"}
        ]
    }
```

**Tempo Estimado**: 2 horas
**Impacto**: Alto - Visibilidade para admin

---

## 🎓 Análise de Código Existente

### Estrutura de Busca de Paciente

**Arquivo**: `webhook_processor.py:615-691`

**Estratégias de Normalização**:

1. **E.164 com +** (+5511987654321)
2. **Sem +** (5511987654321)
3. **Adicionar +55** (+55{phone})
4. **Adicionar 55 sem +** (55{phone})
5. **Últimos 11 dígitos** (11987654321)
6. **Últimos 10 dígitos** (1198765432 1)

**Avaliação**: ✅ **Excelente** - Cobre todos os formatos brasileiros

### Log de Segurança Atual

**Arquivo**: `webhook_processor.py:140`

```python
logger.warning(f"Patient not found for phone: {message_data['phone']}")
```

**Avaliação**: ⚠️ **Básico** - Falta contexto e integração com audit_logs

---

## 🚀 Plano de Implementação Sugerido

### Fase 1: Melhorias Essenciais (4 horas)
1. ✅ Implementar resposta automática para não cadastrados (2h)
2. ✅ Adicionar logging em audit_logs (2h)

### Fase 2: Proteção contra Abuso (4 horas)
3. ✅ Implementar rate limiting (1h)
4. ✅ Implementar blacklist temporária (3h)

### Fase 3: Visibilidade (3 horas)
5. ✅ Criar endpoint de métricas (2h)
6. ✅ Adicionar dashboard admin (1h)

**Tempo Total**: 11 horas
**Complexidade**: Média

---

## 📚 Documentação Relacionada

- `docs/EVOLUTION_API_REVIEW_COMPLETE.md` - Configuração Evolution API
- `docs/WEBHOOK_FIXES_SUMMARY.md` - Fixes de webhook implementados
- `docs/DATABASE_REVIEW_COMPLETE.md` - Schema do banco de dados
- `backend-hormonia/app/models/audit_log.py` - Modelo de audit log
- `backend-hormonia/app/services/webhook_processor.py` - Processador de webhooks

---

## ✅ Conclusão

**Status Atual**: ✅ **SISTEMA FUNCIONAL COM AUTORIZAÇÃO BÁSICA**

O sistema **JÁ POSSUI** controle de acesso funcional que:
- ✅ Bloqueia mensagens de números não cadastrados
- ✅ Registra tentativas em logs e webhook_events
- ✅ Usa múltiplas estratégias de normalização de telefone
- ✅ Protege contra replay attacks com idempotência

**Áreas para Melhoria**:
- ⚠️ Falta resposta automática informativa
- ⚠️ Ausência de rate limiting específico
- ⚠️ Sem integração com audit_logs para eventos de segurança
- ⚠️ Blacklist temporária não implementada

**Recomendação**: ✅ **PRONTO PARA PRODUÇÃO** com melhorias incrementais

O sistema atual é **seguro e funcional**. As melhorias sugeridas são **não-bloqueantes** e podem ser implementadas incrementalmente após o deploy inicial.

---

**Relatório Gerado**: 2025-10-11 05:45 UTC
**Próxima Revisão**: Após implementação das melhorias (2 semanas)
**Autor**: Sistema de Análise Automatizada

---

**🔒 Sistema de autorização verificado e aprovado para produção!**
