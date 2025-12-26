# Indice de Documentacao - Sistema Hormonia

**Data:** 2025-12-26
**Status:** Completo
**Versao:** 2.0

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

## Guias de Dominio

| Dominio | Arquivo | Descricao |
|---------|---------|-----------|
| Patient Flow | [patient/PATIENT_FLOW_GUIDE.md](./patient/PATIENT_FLOW_GUIDE.md) | Onboarding, Saga Pattern, State Machine |
| Quiz System | [quiz/QUIZ_SYSTEM_GUIDE.md](./quiz/QUIZ_SYSTEM_GUIDE.md) | Templates, humanizacao IA, sessoes token |
| WhatsApp | [whatsapp/WHATSAPP_INTEGRATION_GUIDE.md](./whatsapp/WHATSAPP_INTEGRATION_GUIDE.md) | Evolution API, webhooks, mensagens |
| AI | [ai/AI_INTEGRATION_GUIDE.md](./ai/AI_INTEGRATION_GUIDE.md) | Gemini, cache hibrido, circuit breaker |
| Erros | [errors/ERROR_HANDLING_GUIDE.md](./errors/ERROR_HANDLING_GUIDE.md) | Classificacao, recovery, retry |
| Performance | [performance/PERFORMANCE_GUIDE.md](./performance/PERFORMANCE_GUIDE.md) | Cache, pooling, indices, rate limiting |

---

## Resumo por Dominio

### Patient Flow
- **Saga Pattern** para onboarding distribuido
- **State Machine** para gerenciamento de fluxos
- **Soft Delete** com conformidade LGPD
- **Arquivo**: [patient/PATIENT_FLOW_GUIDE.md](./patient/PATIENT_FLOW_GUIDE.md)

### Quiz System
- **Templates** personalizaveis com scoring
- **Humanizacao IA** via Gemini 2.5 Flash
- **Sessoes Token** para acesso publico seguro
- **Arquivo**: [quiz/QUIZ_SYSTEM_GUIDE.md](./quiz/QUIZ_SYSTEM_GUIDE.md)

### WhatsApp Integration
- **Evolution API** como gateway
- **Webhooks** com HMAC-SHA256
- **Tipos de Mensagem**: texto, botoes, listas, midia
- **Arquivo**: [whatsapp/WHATSAPP_INTEGRATION_GUIDE.md](./whatsapp/WHATSAPP_INTEGRATION_GUIDE.md)

### AI Integration
- **Google Gemini 2.5 Flash** via LangChain
- **Cache Hibrido** (Redis L2 + Memory LRU L1)
- **Circuit Breaker** com 3 circuitos
- **Arquivo**: [ai/AI_INTEGRATION_GUIDE.md](./ai/AI_INTEGRATION_GUIDE.md)

### Error Handling
- **Classificacao** com 6 categorias
- **Recovery** com 7 estrategias
- **Retry** com backoff exponencial
- **Arquivo**: [errors/ERROR_HANDLING_GUIDE.md](./errors/ERROR_HANDLING_GUIDE.md)

### Performance Optimization
- **Cache 3 Camadas**: Redis L2 + Memory L1 + TanStack
- **Connection Pooling**: 10+10 (prod), 15+15 (staging)
- **620+ Indices** de banco de dados
- **Arquivo**: [performance/PERFORMANCE_GUIDE.md](./performance/PERFORMANCE_GUIDE.md)

---

## Metricas do Sistema

| Componente | Metrica |
|------------|---------|
| Tabelas | 77 |
| Indices | 620+ |
| Migrations | 37 |
| Endpoints | 60+ |
| Testes | 5,423 |
| Guias de Documentacao | 12 |

---

## Estrutura de Pastas

```
docs/
├── DOCUMENTATION_INDEX.md    # Este arquivo
├── README.md                  # Visao geral
├── architecture/              # Arquitetura do sistema
│   └── ARCHITECTURE_OVERVIEW.md
├── api/                       # Referencia de API
│   └── API_REFERENCE.md
├── database/                  # Database e migrations
│   └── DATABASE_GUIDE.md
├── security/                  # Seguranca e LGPD
│   └── SECURITY_GUIDE.md
├── testing/                   # Testes e CI/CD
│   └── TESTING_GUIDE.md
├── patient/                   # Dominio Patient Flow
│   └── PATIENT_FLOW_GUIDE.md
├── quiz/                      # Dominio Quiz System
│   └── QUIZ_SYSTEM_GUIDE.md
├── whatsapp/                  # Dominio WhatsApp
│   └── WHATSAPP_INTEGRATION_GUIDE.md
├── ai/                        # Dominio AI
│   └── AI_INTEGRATION_GUIDE.md
├── errors/                    # Dominio Error Handling
│   └── ERROR_HANDLING_GUIDE.md
└── performance/               # Dominio Performance
    └── PERFORMANCE_GUIDE.md
```

---

## Documentacao Legada

Os arquivos originais permanecem na raiz de `/docs` para referencia.
A documentacao consolidada esta nos subdiretorios tematicos.

---

**Gerado por:** SPARC Documenter Mode (19 agentes paralelos)
**Data:** 2025-12-26
**Versao:** 2.0
