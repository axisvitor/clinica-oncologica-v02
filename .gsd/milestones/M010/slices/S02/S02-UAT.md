# S02: UAT — Tela de preparo pré-consulta consolidada

## Pré-requisitos
- Backend e frontend rodando
- Paciente existente com fluxo ativo e dados de AI summary

## Testes

### 1. Conteúdo primário visível sem tabs
1. Navegar para `/physician/patients/:id` (clicar num paciente no dashboard)
2. Verificar que o **Resumo IA** está visível na tela principal (não dentro de tab)
3. Verificar que o **Status do Fluxo** está visível na coluna direita
4. Verificar que a seção de **Quiz Mensal** (alertas) está visível
5. ✅ Todo o conteúdo de preparo pré-consulta visível sem clicar em tabs

### 2. Tabs secundários funcionam
1. Verificar que existem 3 tabs: Linha do Tempo, Respostas de Quiz, Mensagens
2. Clicar em cada tab — conteúdo carrega corretamente
3. ✅ Tabs funcionam para conteúdo secundário

### 3. Brain icon do dashboard funciona
1. No dashboard, clicar no ícone 🧠 de um paciente
2. Verificar que a página de detalhe abre com resumo IA **já visível**
3. ✅ 1 clique → resumo IA visível

### 4. Navegação de volta
1. Na tela de detalhe, verificar que existe link/botão para voltar ao dashboard
2. ✅ Navegação de volta funciona
