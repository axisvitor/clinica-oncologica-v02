# ADR-0005: Evolution API for WhatsApp Integration

## Status

Accepted

Date: 2024-01-19

## Context

The Clínica Hormonia system requires WhatsApp integration to:
- Send quiz links to patients via WhatsApp
- Receive patient responses and confirmations
- Send appointment reminders and health alerts
- Enable two-way communication with patients
- Track message delivery status
- Handle multiple physician instances

Requirements:
- Official WhatsApp Business API compliance
- Multi-device support
- Webhook-based message receiving
- Message templates for compliance
- Media support (images, PDFs)
- Reliable message delivery
- Self-hosted option for data privacy

## Decision

We will use **Evolution API v2** as our WhatsApp integration layer.

Evolution API is an open-source WhatsApp Business API implementation that provides:
1. **Multi-instance support**: Each physician can have their own WhatsApp instance
2. **Webhook integration**: Real-time message receiving via HTTP webhooks
3. **Message templates**: Compliant message formatting
4. **Self-hosted**: Full control over data and infrastructure
5. **REST API**: Simple HTTP API for sending messages
6. **QR Code auth**: Easy instance setup via QR code scanning
7. **Status tracking**: Delivery receipts and read confirmations

## Consequences

### Positive Consequences

- **Cost-effective**: Free open-source solution vs. expensive official API
- **Self-hosted**: Complete data privacy and HIPAA compliance
- **Multi-instance**: Each physician gets isolated WhatsApp instance
- **Easy setup**: QR code authentication, no complex approval process
- **Real-time**: Webhook-based message receiving
- **Rich features**: Media support, groups, status updates
- **Active development**: Regular updates and bug fixes
- **Community support**: Large user base and documentation

### Negative Consequences

- **Infrastructure overhead**: Need to maintain Evolution API servers
- **Phone number requirement**: Each instance needs a phone number
- **Ban risk**: WhatsApp can ban unofficial API usage
- **Maintenance**: Need to update when WhatsApp changes protocols
- **Support**: Community support only, no official SLA
- **Scaling limits**: Each instance has message rate limits

### Risks

- **WhatsApp ban**: Account bans if detected as unofficial usage
- **Protocol changes**: WhatsApp updates could break compatibility
- **Performance**: High message volume could overwhelm instances
- **Reliability**: No official SLA or guaranteed uptime
- **Security**: Vulnerable to WhatsApp security changes

## Alternatives Considered

### Alternative 1: Official WhatsApp Business API

**Description**: Facebook's official WhatsApp Business Platform

**Pros**:
- Official support and SLA
- No ban risk
- Enterprise features
- Compliant with WhatsApp ToS
- Reliable infrastructure

**Cons**:
- Very expensive ($0.01-0.10 per message)
- Complex approval process
- Limited to approved message templates
- Vendor lock-in to Meta
- Facebook Business Manager required
- Estimated $500-2000/month for our volume

**Why rejected**: Cost prohibitive for Brazilian healthcare startup

### Alternative 2: Twilio API for WhatsApp

**Description**: Twilio's WhatsApp messaging service

**Pros**:
- Reliable third-party service
- Good documentation
- Compliance handled
- Pay-as-you-go pricing

**Cons**:
- Still expensive ($0.005-0.02 per message)
- Data passes through Twilio
- Template approval required
- Not self-hosted
- Estimated $200-800/month

**Why rejected**: Cost and data privacy concerns

### Alternative 3: Baileys (Direct WhatsApp Web)

**Description**: Low-level WhatsApp Web protocol implementation

**Pros**:
- Free and open source
- Full control
- No intermediary service

**Cons**:
- Very low-level (need to build everything)
- Frequent breaking changes
- High ban risk
- No support or documentation
- Need to handle authentication, sessions, media
- More maintenance than Evolution API

**Why rejected**: Too low-level, prefer Evolution API's higher-level abstractions

### Alternative 4: SMS Instead

**Description**: Use traditional SMS for patient communication

**Pros**:
- Official telecom services
- No ban risk
- Universal (no WhatsApp required)
- Reliable delivery

**Cons**:
- More expensive than WhatsApp in Brazil
- Lower engagement rates
- No rich media support
- No read receipts
- Patients prefer WhatsApp in Brazil

**Why rejected**: Lower engagement and higher cost in Brazilian market

## Implementation Notes

### Instance Management

```python
class EvolutionAPIService:
    def __init__(self, base_url: str, api_key: str):
        self.base_url = base_url
        self.api_key = api_key

    async def create_instance(self, physician_id: str, instance_name: str):
        """Create WhatsApp instance for physician"""
        response = await self.client.post(
            f"{self.base_url}/instance/create",
            json={
                "instanceName": instance_name,
                "qrcode": True,
                "integration": "WHATSAPP-BAILEYS"
            },
            headers={"apikey": self.api_key}
        )

        qr_code = response.json()["qrcode"]["base64"]
        return {"instance_name": instance_name, "qr_code": qr_code}

    async def send_message(self, instance_name: str, phone: str, message: str):
        """Send text message to patient"""
        response = await self.client.post(
            f"{self.base_url}/message/sendText/{instance_name}",
            json={
                "number": f"55{phone}",  # Brazil country code
                "text": message
            },
            headers={"apikey": self.api_key}
        )
        return response.json()
```

### Webhook Handler

```python
@router.post("/webhooks/evolution/{instance_name}")
async def evolution_webhook(
    instance_name: str,
    webhook_data: dict,
    background_tasks: BackgroundTasks
):
    """Handle incoming messages from Evolution API"""

    # Validate webhook signature
    if not verify_evolution_signature(webhook_data):
        raise HTTPException(status_code=401)

    # Process webhook asynchronously
    background_tasks.add_task(
        process_whatsapp_message,
        instance_name=instance_name,
        message_data=webhook_data
    )

    return {"status": "accepted"}

async def process_whatsapp_message(instance_name: str, message_data: dict):
    """Process incoming WhatsApp message"""

    # Extract message details
    phone = message_data["data"]["key"]["remoteJid"].replace("@s.whatsapp.net", "")
    text = message_data["data"]["message"]["conversation"]

    # Find patient by phone
    patient = await get_patient_by_phone(phone)

    # Handle message based on context
    if "quiz" in text.lower():
        await handle_quiz_response(patient, text)
    elif "agendar" in text.lower():
        await handle_appointment_request(patient, text)
    else:
        await send_default_response(instance_name, phone)
```

### Message Templates

```python
class WhatsAppTemplates:
    QUIZ_INVITATION = """
Olá {patient_name}! 👋

Seu questionário mensal está disponível.
Por favor, responda até {deadline}.

🔗 Link: {quiz_url}

Se tiver dúvidas, estamos à disposição!
    """

    APPOINTMENT_REMINDER = """
📅 Lembrete de Consulta

Olá {patient_name}!

Sua consulta está agendada para:
📆 {appointment_date}
🕐 {appointment_time}
📍 {clinic_address}

Confirme sua presença respondendo SIM.
    """

    ALERT_HIGH_RISK = """
⚠️ Alerta de Saúde

{patient_name}, identificamos alguns sintomas que requerem atenção.

Por favor, entre em contato urgente:
📞 {clinic_phone}

Ou acesse: {emergency_url}
    """
```

### Rate Limiting

```python
class EvolutionRateLimiter:
    """Rate limit WhatsApp messages to avoid bans"""

    def __init__(self):
        self.redis = get_redis_client()

    async def check_rate_limit(self, instance_name: str) -> bool:
        """
        Evolution API limits:
        - 40 messages per minute per instance
        - 1000 messages per day per instance
        """
        minute_key = f"whatsapp:rate:{instance_name}:minute"
        day_key = f"whatsapp:rate:{instance_name}:day"

        minute_count = await self.redis.incr(minute_key)
        day_count = await self.redis.incr(day_key)

        if minute_count == 1:
            await self.redis.expire(minute_key, 60)
        if day_count == 1:
            await self.redis.expire(day_key, 86400)

        if minute_count > 40:
            raise RateLimitExceeded("Too many messages per minute")
        if day_count > 1000:
            raise RateLimitExceeded("Daily message limit reached")

        return True
```

### Deployment Configuration

```yaml
# docker-compose.yml
services:
  evolution-api:
    image: atendai/evolution-api:latest
    ports:
      - "8080:8080"
    environment:
      - DATABASE_CONNECTION_URI=postgresql://user:pass@postgres:5432/evolution
      - DATABASE_CONNECTION_CLIENT_NAME=pg
      - AUTHENTICATION_API_KEY=${EVOLUTION_API_KEY}
      - WEBHOOK_GLOBAL_URL=${WEBHOOK_URL}
      - WEBHOOK_GLOBAL_ENABLED=true
    volumes:
      - evolution_instances:/evolution/instances
    restart: unless-stopped
```

### Migration Path

1. ✅ Evolution API v2 deployed
2. ✅ Instance creation API implemented
3. ✅ Message sending service created
4. ✅ Webhook endpoint configured
5. ✅ Rate limiting implemented
6. ✅ Message templates defined
7. 🔄 QR code UI for physician setup
8. 🔄 Message delivery monitoring
9. 🔄 Automatic reconnection handling

## References

- [Evolution API Documentation](https://doc.evolution-api.com/)
- [Evolution API GitHub](https://github.com/EvolutionAPI/evolution-api)
- [WhatsApp Business API](https://developers.facebook.com/docs/whatsapp)
- [Baileys Library](https://github.com/WhiskeySockets/Baileys)
- [WhatsApp Rate Limits](https://developers.facebook.com/docs/whatsapp/messaging-limits)

## Metadata

- **Author**: Integration Team
- **Reviewers**: Backend Team, Product Team
- **Last Updated**: 2024-01-19
- **Related ADRs**: ADR-0004 (Celery), ADR-0001 (FastAPI)
- **Tags**: integration, whatsapp, messaging, external-api
