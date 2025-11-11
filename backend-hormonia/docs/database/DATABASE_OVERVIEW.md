# Database Overview – Clínica Oncológica

> Atualizado em **11/11/2025 09:49 Hora oficial do Brasil** com base no snapshot do ambiente real.

---

## Visão Geral

- **Motor**: PostgreSQL 17.4 on aarch64-unknown-linux-gnu, compiled by gcc (GCC) 12.4.0, 64-bit
- **Quantidade de tabelas**: 47
- **Principais módulos**:
  - Gestão de Pacientes (7 tabelas)
  - Sistema de Fluxos (8 tabelas)
  - Quiz Mensal (5 tabelas)
  - Integração WhatsApp (4 tabelas)
  - Mensagens & Comunicação (2 tabelas)
  - Notificações (1 tabela)
  - Gestão de Usuários (3 tabelas)
  - Administração (10 tabelas)
  - Auditoria e Logs (5 tabelas)
  - Webhooks & Eventos (1 tabelas)
  - Migrações (1 tabelas)
- **Chaves primárias**: ver referência por tabela em SCHEMA_REFERENCE.md
- **Relacionamentos**: 57 chaves estrangeiras ativas
- **Triggers**: 14 gatilhos
- **Enums personalizados**: 13 tipos
- **Índices**: 263 índices no total

---

## Status dos Dados (snapshot produção)

| Item | Valor |
|------|-------|
| Pacientes (estimativa) | 1 |
| Templates de quiz (estimativa) | 2 |
| Mensagens (estimativa) | 1 |
| WhatsApp mensagens (estimativa) | 0 |
| Usuários (estimativa) | 2 |
