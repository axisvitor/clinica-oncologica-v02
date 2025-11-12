# Correção do Endpoint de Webhook do WhatsApp

## 🐛 Problema Identificado

**Erro:** `405 Method Not Allowed` ao tentar enviar POST para `/api/v2/webhooks/whatsapp`

```
REQUEST | POST /api/v2/webhooks/whatsapp | Status: 405 | Total: 0.003s
```

## 🔍 Causa Raiz

O endpoint de webhook estava configurado apenas como `/api/v2/webhooks/inbound`, mas a Evolution API estava tentando enviar para `/api/v2/webhooks/whatsapp`.

## ✅ Solução Implementada

### 1. Refatoração do Código

Criamos uma função interna `_process_inbound_webhook()` que contém toda a lógica de processamento:

```python
async def _process_inbound_webhook(
    request: Request,
    event_data: WebhookInboundEvent,
    db: Session,
    redis_cache,
    verification: dict,
) -> WebhookInboundResponse:
    """
    Internal function to process inbound webhooks.
    Shared by both /inbound and /whatsapp endpoints.
    """
    # ... lógica de processamento ...
```

### 2. Dois Endpoints Públicos

Agora temos dois endpoints que apontam para a mesma função:

#### Endpoint Principal: `/api/v2/webhooks/inbound`
```python
@router.post("/inbound", response_model=WebhookInboundResponse)
async def receive_inbound_webhook(...):
    """
    Receive incoming webhook from external systems (Evolution API).
    """
    return await _process_inbound_webhook(request, event_data, db, redis_cache, verification)
```

#### Endpoint Alias: `/api/v2/webhooks/whatsapp`
```python
@router.post("/whatsapp", response_model=WebhookInboundResponse)
async def receive_whatsapp_webhook(...):
    """
    Receive incoming webhook from WhatsApp/Evolution API.
    
    This is an alias for /inbound endpoint for backward compatibility.
    """
    return await _process_inbound_webhook(request, event_data, db, redis_cache, verification)
```

## 📋 Funcionalidades Mantidas

Ambos os endpoints mantêm todas as funcionalidades de segurança:

✅ **HMAC Signature Verification**
- Valida assinatura HMAC-SHA256
- Previne adulteração de dados

✅ **Timestamp Validation**
- Janela de 5 minutos
- Previne ataques de replay

✅ **Idempotency Checking**
- Janela de 24 horas
- Previne processamento duplicado
- Cache em Redis + fallback para DB

✅ **Event Routing**
- Mensagens → `process_message_webhook()`
- Conexões → `process_connection_webhook()`
- Outros eventos → processamento genérico

## 🔧 Configuração da Evolution API

Agora você pode configurar o webhook da Evolution API para qualquer uma das URLs:

### Opção 1: Endpoint Principal
```
https://seu-dominio.com/api/v2/webhooks/inbound
```

### Opção 2: Endpoint Alias (WhatsApp)
```
https://seu-dominio.com/api/v2/webhooks/whatsapp
```

Ambos funcionam exatamente da mesma forma!

## 🧪 Testando

### Teste Manual com cURL

```bash
# Testar endpoint /inbound
curl -X POST https://seu-dominio.com/api/v2/webhooks/inbound \
  -H "Content-Type: application/json" \
  -H "X-Webhook-Signature: SIGNATURE" \
  -H "X-Webhook-Timestamp: $(date +%s)" \
  -H "X-Webhook-Id: test_123" \
  -d '{
    "event": "message.received",
    "data": {
      "from": "5511999999999",
      "message": "Olá!"
    }
  }'

# Testar endpoint /whatsapp (deve funcionar igual)
curl -X POST https://seu-dominio.com/api/v2/webhooks/whatsapp \
  -H "Content-Type: application/json" \
  -H "X-Webhook-Signature: SIGNATURE" \
  -H "X-Webhook-Timestamp: $(date +%s)" \
  -H "X-Webhook-Id: test_123" \
  -d '{
    "event": "message.received",
    "data": {
      "from": "5511999999999",
      "message": "Olá!"
    }
  }'
```

### Verificar Logs

```bash
# Procurar por webhooks recebidos
grep "Received inbound webhook" logs/app.log

# Verificar processamento de mensagens
grep "Message processed successfully" logs/app.log

# Verificar idempotência
grep "IDEMPOTENCY" logs/app.log
```

## 📊 Monitoramento

### Métricas Disponíveis

- **Taxa de sucesso**: Webhooks processados com sucesso
- **Taxa de duplicação**: Webhooks bloqueados por idempotência
- **Tempo de resposta**: Latência do processamento
- **Erros de autenticação**: Falhas de verificação de assinatura

### Endpoints de Monitoramento

```bash
# Listar webhooks configurados
GET /api/v2/webhooks

# Ver estatísticas de um webhook
GET /api/v2/webhooks/{webhook_id}/stats

# Ver histórico de entregas
GET /api/v2/webhooks/{webhook_id}/deliveries

# Ver logs de webhook
GET /api/v2/webhooks/{webhook_id}/logs
```

## 🔐 Segurança

### Headers Obrigatórios

Todos os webhooks devem incluir:

1. **X-Webhook-Signature**: Assinatura HMAC-SHA256
2. **X-Webhook-Timestamp**: Timestamp Unix (máx 5 min de diferença)
3. **X-Webhook-Id**: ID único para idempotência (opcional mas recomendado)

### Validação de Assinatura

```python
# Cálculo da assinatura
payload = f"{timestamp}.{json_body}"
signature = hmac.new(
    secret.encode('utf-8'),
    payload.encode('utf-8'),
    hashlib.sha256
).hexdigest()
```

### Configuração do Secret

O secret do webhook deve estar configurado no `.env`:

```env
EVOLUTION_WEBHOOK_SECRET=seu_secret_aqui
```

## 🚀 Próximos Passos

1. ✅ Atualizar configuração da Evolution API para usar o novo endpoint
2. ✅ Testar recebimento de mensagens
3. ✅ Monitorar logs para verificar processamento
4. ✅ Configurar alertas para falhas de webhook

## 📝 Notas Técnicas

### Por que Dois Endpoints?

- **Compatibilidade**: Alguns sistemas podem estar configurados para `/whatsapp`
- **Clareza**: O nome `/whatsapp` é mais descritivo para integrações WhatsApp
- **Flexibilidade**: `/inbound` é mais genérico para outros tipos de webhook

### Performance

- Ambos os endpoints compartilham a mesma lógica
- Não há overhead adicional
- Cache Redis é compartilhado
- Idempotência funciona entre ambos os endpoints

### Manutenção

Para adicionar novos tipos de webhook:

1. Adicione o tipo em `WebhookEventType` enum
2. Implemente o processador em `WebhookProcessor`
3. Adicione roteamento em `_process_inbound_webhook()`

## ✅ Conclusão

O erro 405 foi corrigido adicionando o endpoint `/api/v2/webhooks/whatsapp` como alias para `/api/v2/webhooks/inbound`. Ambos os endpoints funcionam identicamente e mantêm todas as funcionalidades de segurança e processamento.

**Status:** ✅ Corrigido e pronto para uso
