# Legacy v1 Routes (Not Mounted)

Este diretório contém endpoints e módulos da API v1 que pertencem a domínios legados ou a outros serviços do sistema. No aplicativo atual, **nenhum router v1 é montado**, para evitar confusão e garantir a migração para a v2.

## Status de Montagem
- ✅ API v2 é a API ativa (veja `app/api/v2/`)
- ✅ Health/Monitoring centralizados (veja `app/routers/health.py` e `/metrics`)
- ⚠️ Exceções ativas de v1:
  - `GET /api/v1/redis/health` (definido inline em `app/core/router_registry.py`)
  - `GET /api/v1/csrf-token` (definido em `app/core/application_factory.py`)

> Observação: As exceções acima são endpoints utilitários críticos (health e CSRF) e não representam a reativação da v1.

## Onde estão os arquivos novos (v2)
- Endpoints v2: `app/api/v2/{patients.py, quiz.py, analytics.py, router.py, dependencies.py}`
- Schemas v2: `app/schemas/v2/{patient.py, quiz.py, analytics.py, common.py}`
- Health central: `app/routers/health.py`
- Prometheus: `app/monitoring/prometheus_exporters.py` (montado como `/metrics`)

## Por que manter estes arquivos v1?
- Fazem parte de outros domínios/serviços do sistema e servem como referência histórica.
- Não estão montados e **não expõem endpoints** no app atual.
- Serão avaliados/arquivados gradualmente em PRs específicos.

## Como evitar reativação acidental da v1
- O registro de rotas central (`app/core/router_registry.py`) mantém **todas as inclusões v1 comentadas**.
- Um teste de integração garante que nenhum endpoint `/api/v1/*` (exceto as duas exceções citadas) esteja exposto.

## Como reativar algo da v1 (apenas se necessário)
1. Avaliar impacto e dependências.
2. Incluir explicitamente o router no `register_routers()` (arquivo `app/core/router_registry.py`).
3. Adicionar RBAC, rate limiting e validações compatíveis com os padrões v2.
4. Criar testes de integração e atualizar documentação.

---

Última atualização: manter este diretório como LEGACY para evitar confusão entre serviços/domínios. A migração para v2 é a fonte de verdade dos contratos.
