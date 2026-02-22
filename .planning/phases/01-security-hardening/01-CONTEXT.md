# Phase 1: Security Hardening - Context

**Gathered:** 2026-02-22
**Status:** Ready for planning

<domain>
## Phase Boundary

Eliminar exposições de segurança que bloqueiam go-live com pacientes reais: autenticar monitoring endpoints, remover debug bypasses do binário de produção, gerenciar credentials de forma segura, e validar configuração de deploy.

</domain>

<decisions>
## Implementation Decisions

### Auth approach
- Usar mesmo sistema de auth do resto da API: `get_current_user` padrão + role check
- Role mínima: admin OU médico podem acessar monitoring/métricas
- Health checks (`/health/live`, `/health/ready`) permanecem SEM auth — necessário para Railway health probes
- Monitoring endpoints requerem sessão autenticada com role adequada

### Debug code policy
- Claude's discretion on TEST_TOKEN_REGISTRY approach (conftest vs full removal)
- Claude's discretion on debug endpoints policy (remove from prod vs keep with strong auth)
- Claude's discretion on JWT default secret key handling

### Credential management
- Claude's discretion on Firebase service account key storage method (escolher baseado no deploy target Railway)
- Claude's discretion on local key file handling (delete vs keep with gitignore)

### Deploy validation
- Claude's discretion on validation approach (startup check, CI gate, or both)
- Claude's discretion on config validation scope (debug flag only vs broader security checklist)

### Claude's Discretion
- TEST_TOKEN_REGISTRY: escolher entre mover para conftest ou remover completamente — priorizar segurança máxima
- Debug endpoints: escolher entre remover de produção ou manter com auth forte — seguir melhores práticas OWASP
- JWT default secret: escolher entre remover default ou manter apenas em dev — seguir melhor prática de credential hygiene
- Firebase key storage: escolher método mais adequado para Railway (env var base64 é o padrão do Railway)
- Local key file: seguir abordagem mais segura
- Deploy validation: escolher entre startup check, CI gate, ou ambos
- Config validation scope: decidir se vale expandir além do debug flag nesta fase

</decisions>

<specifics>
## Specific Ideas

No specific requirements — open to standard approaches. User trusts Claude to follow security best practices (OWASP, LGPD) for all discretionary decisions.

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 01-security-hardening*
*Context gathered: 2026-02-22*
