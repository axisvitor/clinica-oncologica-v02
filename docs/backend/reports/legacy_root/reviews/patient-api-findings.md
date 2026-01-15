## Finding #1: Saga validation errors return 400 instead of 422

**Severidade**: P2
**Componente**: backend-hormonia/app/domain/patient/onboarding/coordinator.py:161
**Descricao**: O OnboardingCoordinator levanta `ValidationError` a partir de `app.exceptions`, mas o endpoint de API captura `app.core.exceptions.ValidationError`. Falhas da saga acabam convertidas em `BusinessRuleError` (400) em vez de 422.
**Impacto**: Clientes recebem erro de regra de negocio em vez de erro de validacao; tratamento de erro inconsistente entre camadas.
**Recomendacao**: Padronizar o tipo de excecao na saga e API (ex.: usar `app.core.exceptions.ValidationError` ou mapear explicitamente).
**Ticket**: TBD

## Finding #2: Idempotency key nao expira no banco

**Severidade**: P2
**Componente**: backend-hormonia/app/models/patient.py:130
**Descricao**: `idempotency_key` fica armazenada no registro de paciente com indice unico sem expiracao. O Redis expira em 24h, mas o check no banco permanece indefinidamente.
**Impacto**: Reuso de idempotency key apos 24h continua bloqueado e pode impedir retries legitimos ou reprocessamento manual.
**Recomendacao**: Usar tabela de idempotencia com expiracao ou limpar `idempotency_key` apos a janela definida.
**Ticket**: TBD
