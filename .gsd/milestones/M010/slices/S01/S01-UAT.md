# S01: UAT — API enriquecida + Dashboard patient-centric

## Pré-requisitos
- Backend rodando (`uvicorn app.main:app` ou Docker)
- Frontend rodando (`npm run dev`)
- Usuário logado com role doctor ou admin

## Testes

### 1. Dashboard carrega com lista de pacientes
1. Navegar para `/physician/dashboard`
2. Verificar que a tabela mostra pacientes com colunas: Paciente, Fase do Fluxo, Dia, Último Contato, Alertas, Status
3. ✅ Todos os pacientes do médico logado aparecem

### 2. Dados de fluxo visíveis
1. Na tabela, verificar que pacientes com fluxo ativo mostram:
   - Badge de fase (Onboarding, Follow-up Diário, ou Quiz Mensal)
   - Número do dia atual
   - Tempo relativo do último contato (ex: "2h atrás", "Ontem")
2. Pacientes com alertas não reconhecidos mostram badge vermelho com contagem
3. ✅ Contexto clínico visível sem clicar

### 3. Filtros funcionam
1. Digitar nome de paciente na busca → tabela filtra após 300ms
2. Selecionar "Onboarding" no filtro de fase → apenas pacientes em onboarding
3. Selecionar "Pausado" no filtro de status → apenas pacientes com fluxo pausado
4. Clicar "Limpar" → filtros resetados
5. ✅ Filtros funcionam combinados

### 4. Navegação para detalhe
1. Clicar em qualquer linha da tabela → navega para `/physician/patients/:id`
2. Clicar no ícone 🧠 (Brain) → navega para `/physician/patients/:id?tab=ai-summary`
3. ✅ Navegação funcional

### 5. Chat IA e Exportar
1. Clicar "Chat IA" → dialog abre
2. Clicar "Exportar" → dialog abre
3. ✅ Funcionalidades preservadas

### 6. Admin dashboard inalterado
1. Navegar para `/dashboard` (como admin)
2. Verificar que é o dashboard admin com métricas operacionais (não o physician)
3. ✅ Dashboards separados
