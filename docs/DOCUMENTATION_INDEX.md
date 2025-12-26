# Indice de Documentacao - Sistema Hormonia

**Data:** 2025-12-26
**Status:** Refatorado

---

## Documentacao Consolidada

Esta documentacao foi refatorada de ~151 arquivos dispersos para guias organizados por dominio.

---

## Guias Principais

| Guia | Arquivo | Descricao |
|------|---------|-----------|
| README | [README.md](./README.md) | Visao geral do sistema |
| Arquitetura | [architecture/ARCHITECTURE_OVERVIEW.md](./architecture/ARCHITECTURE_OVERVIEW.md) | Padroes e componentes |
| API | [api/API_REFERENCE.md](./api/API_REFERENCE.md) | Referencia de endpoints |
| Database | [database/DATABASE_GUIDE.md](./database/DATABASE_GUIDE.md) | Modelos e migrations |
| Seguranca | [security/SECURITY_GUIDE.md](./security/SECURITY_GUIDE.md) | Auth, CSRF, CORS, LGPD |
| Testes | [testing/TESTING_GUIDE.md](./testing/TESTING_GUIDE.md) | Estrutura e comandos |

---

## Dominios

### Patient Flow
- Onboarding com Saga Pattern
- State Machine para flows
- Soft delete (LGPD)

### Quiz System
- Templates personalizaveis
- Humanizacao com IA
- Sessoes via token

### WhatsApp Integration
- Evolution API
- Webhooks
- Tipos de mensagem

### AI Integration
- Google Gemini 2.5 Flash
- Cache híbrido (Redis + Memory)
- Circuit Breaker

---

## Metricas do Sistema

| Componente | Metrica |
|------------|---------|
| Tabelas | 77 |
| Indices | 479+ |
| Migrations | 37 |
| Endpoints | 60+ |
| Testes | 5,423 |

---

## Documentacao Legada

Os arquivos originais permanecem na raiz de `/docs` para referencia.
A documentacao consolidada esta nos subdiretorios tematicos.

---

**Gerado por:** SPARC Documenter Mode (13 agentes paralelos)
**Data:** 2025-12-26
