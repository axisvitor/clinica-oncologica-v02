# S04: UAT — Polish responsivo + verificação integrada

## Pré-requisitos
- Frontend rodando (`npm run dev`)

## Testes

### 1. Desktop — tabela densa
1. Abrir `/physician/dashboard` em viewport ≥768px
2. Verificar que pacientes aparecem em tabela com 7 colunas
3. Colunas visíveis: Paciente, Fase do Fluxo, Dia, Último Contato, Alertas, Status, Ações
4. ✅ Tabela densa funcional

### 2. Mobile — cards touch-friendly
1. Redimensionar viewport para <768px (ou abrir DevTools modo mobile)
2. Verificar que a tabela desaparece e cards empilhados aparecem
3. Cada card mostra: nome, alertas (se houver), badges de fase/status/dia, último contato, botão IA
4. Cards clicáveis levam ao detalhe do paciente
5. ✅ Cards mobile touch-friendly

### 3. Detalhe do paciente — responsivo
1. Abrir detalhe de um paciente
2. Em desktop (≥1024px): resumo IA à esquerda (2/3), flow status à direita (1/3)
3. Em mobile (<1024px): seções empilhadas verticalmente
4. ✅ Layout adapta corretamente

### 4. Filtros responsivos
1. Em mobile, verificar que filtros (busca + selects) empilham verticalmente
2. Em desktop, verificar que ficam em linha
3. ✅ Filtros adaptam ao viewport

### 5. Build verification
1. `npx tsc --noEmit` — sem erros novos
2. `npx vite build` — sucesso
3. ✅ Build green
