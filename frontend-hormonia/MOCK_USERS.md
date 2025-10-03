# Usuários Mock para Desenvolvimento

Este documento lista todos os usuários mockados disponíveis para desenvolvimento e testes.

## Senha Padrão

**Todos os usuários usam a mesma senha:** `senha123`

---

## Usuários Admin

### Admin Principal
- **Email:** `admin@sistema.com`
- **Nome:** Administrador Sistema
- **Role:** admin
- **Permissões:** Todas (*)

### Admin Secundário
- **Email:** `admin2@sistema.com`
- **Nome:** Admin Secundário
- **Role:** admin
- **Permissões:** read:*, write:*, delete:patients, manage:users

---

## Usuários Médicos

### Dr. Carlos Silva
- **Email:** `123456@medico.local`
- **CRM:** 123456
- **Nome:** Dr. Carlos Silva
- **Role:** medico
- **Especialidade:** Oncologia
- **Conselho:** CRM-SC
- **Pacientes Atribuídos:** 3 pacientes (patient-001, patient-002, patient-003)

### Dra. Maria Santos
- **Email:** `789012@medico.local`
- **CRM:** 789012
- **Nome:** Dra. Maria Santos
- **Role:** medico
- **Especialidade:** Oncologia Clínica
- **Conselho:** CRM-SC
- **Pacientes Atribuídos:** 2 pacientes (patient-004, patient-005)

### Dr. João Oliveira
- **Email:** `345678@medico.local`
- **CRM:** 345678
- **Nome:** Dr. João Oliveira
- **Role:** medico
- **Especialidade:** Radioterapia
- **Conselho:** CRM-SC
- **Pacientes Atribuídos:** 1 paciente (patient-006)

---

## Usuário Regular

### Usuário de Teste
- **Email:** `user@sistema.com`
- **Nome:** Usuário Teste
- **Role:** user
- **Permissões:** read:pacientes, read:mensagens

---

## Pacientes Mock

O sistema inclui 8 pacientes mockados com dados completos:
- Ana Paula Costa
- Roberto Silva Santos
- Maria Helena Ferreira
- Carlos Eduardo Lima
- Juliana Oliveira Souza
- Pedro Henrique Alves
- Fernanda Costa Ribeiro
- João Carlos Martins

---

## Como Usar

1. **Desenvolvimento Local:**
   - As variáveis de ambiente já estão configuradas em `.env`
   - O modo mock está ativado automaticamente em desenvolvimento

2. **Login:**
   - Use qualquer email da lista acima
   - Senha: `senha123`
   - O sistema validará automaticamente as permissões baseado no role

3. **Dados Mockados:**
   - Todos os endpoints retornam dados mockados
   - As operações de CRUD são simuladas (não persistem entre reloads)
   - Delays de rede são simulados (200-600ms)
   - Erros ocasionais são simulados (5% de chance)

---

## Desabilitar Modo Mock

Para desabilitar o modo mock e usar autenticação real (Firebase):

1. Edite o arquivo `.env`:
   ```
   VITE_USE_MOCK_AUTH=false
   VITE_USE_MOCK_API=false
   ```

2. Implemente a configuração do Firebase quando necessário

---

## Notas Técnicas

- **Armazenamento:** Sessions são armazenadas em localStorage
- **Expiração:** Sessions expiram após 1 hora
- **Tokens:** Tokens mockados são gerados automaticamente
- **Permissões:** Sistema de permissões funcional com wildcards

---

**Última Atualização:** Outubro 2025
