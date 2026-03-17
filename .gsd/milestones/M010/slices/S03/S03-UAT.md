# S03: UAT — Limpeza do código morto /medico/*

## Testes

### 1. Código morto removido
1. Executar: `find src/pages/medico -name "MedicoDashboard*" -o -name "PacientesList*" -o -name "ProntuarioView*"`
2. Deve retornar vazio
3. ✅ Arquivos deletados

### 2. Login do médico ainda funciona
1. Navegar para `/medico/login`
2. Verificar que a tela de login aparece
3. ✅ MedicoLogin.tsx preservado e funcional

### 3. Redirects funcionam
1. Navegar para `/medico/dashboard` → deve redirecionar para `/physician/dashboard`
2. ✅ Redirects ativos em routeDefinitions.tsx

### 4. Build limpo
1. Executar `npx vite build`
2. Deve completar sem erros
3. ✅ Build green
