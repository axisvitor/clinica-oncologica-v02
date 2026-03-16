# S02: WuzAPI conectado e enviando

**Goal:** WuzAPI rodando via Docker, conectado com número de teste via QR code, e envio de mensagem de teste chegando no WhatsApp real.
**Demo:** Mensagem de teste enviada via `WuzAPIClient.send_text()` chega no WhatsApp do número de teste. Verificado visualmente pelo usuário no telefone.

## Must-Haves

- WuzAPI container rodando e respondendo na porta configurada
- Número de teste conectado via QR code (etapa manual do usuário)
- `WuzAPIClient.send_text(phone, "mensagem de teste")` entrega mensagem real
- Webhook URL do WuzAPI configurado para apontar pro backend (para S05)
- WHATSAPP_WUZAPI_BASE_URL e WHATSAPP_WUZAPI_TOKEN configurados no .env

## Proof Level

- This slice proves: integration
- Real runtime required: yes (WuzAPI + WhatsApp real)
- Human/UAT required: yes (verificar mensagem no telefone, parear QR code)

## Verification

- `curl http://localhost:<wuzapi_port>/api/sessions/status` retorna sessão conectada
- Script Python executa `WuzAPIClient.send_text()` e retorna sucesso
- Mensagem chega no WhatsApp do número de teste (verificação visual)

## Observability / Diagnostics

- Runtime signals: WuzAPI container logs, send_text response status
- Inspection surfaces: `GET /api/sessions/status` no WuzAPI, container logs
- Failure visibility: WuzAPI error response com código e mensagem
- Redaction constraints: número de telefone nos logs

## Tasks

- [x] **T01: WuzAPI via Docker + conexão de número** `est:30m`
  - Why: sem WuzAPI rodando, nenhuma mensagem WhatsApp pode ser enviada
  - Files: `backend-hormonia/docker-compose.yml`, `backend-hormonia/.env`
  - Do: adicionar serviço WuzAPI ao docker-compose (ou rodar separado), configurar porta (evitar conflito com backend), configurar token. Subir container e apresentar QR code pro usuário parear o número de teste. Configurar webhook URL apontando pro backend.
  - Verify: `curl localhost:<wuzapi_port>/api/sessions/status` retorna connected
  - Done when: WuzAPI rodando, número conectado, webhook configurado

- [ ] **T02: Envio de mensagem de teste real** `est:20m`
  - Why: provar que o caminho WuzAPIClient → WuzAPI → WhatsApp funciona antes de wiring mais complexo
  - Files: `backend-hormonia/app/integrations/wuzapi/client.py`, `backend-hormonia/.env`
  - Do: WHATSAPP_WUZAPI_BASE_URL e WHATSAPP_WUZAPI_TOKEN configurados no .env. Criar script de teste que instancia WuzAPIClient e chama send_text() com o número de teste. Executar e confirmar que resposta é sucesso.
  - Verify: mensagem chega no WhatsApp do número de teste
  - Done when: mensagem "Teste M008 - sistema funcionando" recebida no telefone

## Files Likely Touched

- `backend-hormonia/docker-compose.yml`
- `backend-hormonia/.env`
- `backend-hormonia/app/integrations/wuzapi/client.py` (se precisar de ajuste)
