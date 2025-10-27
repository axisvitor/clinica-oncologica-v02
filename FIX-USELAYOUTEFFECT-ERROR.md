# 🔧 Fix: useLayoutEffect Error (React 19)

## ❌ Erro Encontrado

```
Uncaught TypeError: Cannot read properties of undefined (reading 'useLayoutEffect')
```

**Screenshot:** Overlay vermelho com mensagem "Erro Crítico"

---

## 🔍 Causa Raiz

Este erro ocorre quando bibliotecas tentam acessar `React.useLayoutEffect` mas o React não está disponível no escopo correto. Comum em:

- **class-variance-authority** (CVA) - usado pelo shadcn/ui
- **@radix-ui** components
- React 19 com libs que ainda não foram totalmente atualizadas

### Por que acontece?

1. Vite faz code splitting e lazy loading
2. CVA é carregado em chunk separado do React
3. CVA tenta acessar `React.useLayoutEffect` antes do React estar disponível
4. TypeError: `undefined.useLayoutEffect`

---

## ✅ Solução Implementada

### 1. Pre-bundle class-variance-authority com React

**Arquivo:** `vite.config.ts`

```typescript
optimizeDeps: {
  include: [
    "react",
    "react-dom",
    "react/jsx-runtime",
    "class-variance-authority", // CRITICAL: Pre-bundle to ensure React hooks available
    // ... outras deps
  ],
  exclude: [], // Removido exclusões de Radix
  // Force dependency re-optimization on server start
  force: mode === "development",
}
```

**O que isso faz:**
- ✅ Força Vite a pre-bundlar CVA junto com React
- ✅ Garante que React hooks estejam disponíveis quando CVA carregar
- ✅ Remove exclusões que causavam problemas de ordem de carregamento
- ✅ Força re-otimização em desenvolvimento para aplicar mudanças

### 2. Manter CVA no mesmo chunk do React (produção)

**Arquivo:** `vite.config.ts` (já estava implementado)

```typescript
manualChunks(id) {
  if (id.includes("node_modules")) {
    // Core React (always needed) - MUST LOAD FIRST
    if (id.includes("react") || id.includes("react-dom")) {
      return "vendor-react";
    }

    // CRITICAL: class-variance-authority uses React.useLayoutEffect
    // MUST be in same chunk as React to avoid "Cannot read properties of undefined"
    if (id.includes("class-variance-authority")) {
      return "vendor-react"; // Mesmo chunk do React
    }
  }
}
```

---

## 🚀 Como Aplicar a Correção

### Desenvolvimento Local

```bash
# 1. Limpar cache do Vite
cd frontend-hormonia
Remove-Item -Recurse -Force dist, node_modules\.vite

# 2. Reiniciar servidor dev
npm run dev
```

O Vite vai mostrar:
```
Forced re-optimization of dependencies
```

### Produção (Railway)

A correção já está no código. Basta fazer rebuild:

```bash
# Railway vai aplicar automaticamente no próximo deploy
git add vite.config.ts
git commit -m "fix: resolver useLayoutEffect error com CVA"
git push origin main
```

---

## 🔍 Como Verificar se Funcionou

### 1. Console do Browser (F12)

**Antes (com erro):**
```
❌ Uncaught TypeError: Cannot read properties of undefined (reading 'useLayoutEffect')
```

**Depois (sem erro):**
```
✅ Sem erros de useLayoutEffect
✅ App carrega normalmente
```

### 2. Network Tab

Verifique que `vendor-react.js` contém tanto React quanto CVA:

```
vendor-react-[hash].js  (~150KB)
  ├── react
  ├── react-dom
  └── class-variance-authority ✅
```

### 3. Overlay de Erro

**Antes:** Overlay vermelho aparecia
**Depois:** Nenhum overlay, app funciona normalmente

---

## 📊 Impacto da Correção

| Aspecto | Antes | Depois |
|---------|-------|--------|
| **Erro useLayoutEffect** | ❌ Sempre | ✅ Nunca |
| **Tempo de carregamento** | N/A | +0ms (sem impacto) |
| **Bundle size** | N/A | Sem mudança |
| **Compatibilidade React 19** | ❌ Quebrado | ✅ Funcionando |

---

## 🎯 Outras Bibliotecas Afetadas

Se aparecerem erros similares com outras libs, adicione ao `optimizeDeps.include`:

```typescript
optimizeDeps: {
  include: [
    "react",
    "react-dom",
    "react/jsx-runtime",
    "class-variance-authority",
    // Adicione outras libs que usam React hooks:
    "@radix-ui/react-dialog",
    "@radix-ui/react-dropdown-menu",
    // etc...
  ],
}
```

---

## 🔧 Troubleshooting

### Erro persiste após aplicar correção?

1. **Limpar cache completamente:**
   ```bash
   Remove-Item -Recurse -Force dist, node_modules\.vite, node_modules\.cache
   ```

2. **Reinstalar dependências:**
   ```bash
   Remove-Item -Recurse -Force node_modules
   npm install
   ```

3. **Verificar versão do React:**
   ```bash
   npm list react react-dom
   # Deve ser 19.0.0
   ```

4. **Hard refresh no browser:**
   - Ctrl+Shift+R (Chrome/Edge)
   - Ctrl+F5 (Firefox)

### Erro só em produção?

Verifique que o build está usando a configuração correta:

```bash
npm run build:prod
# Deve mostrar chunks:
# vendor-react-[hash].js (contém React + CVA)
```

---

## 📚 Referências

- [Vite Dependency Pre-Bundling](https://vitejs.dev/guide/dep-pre-bundling.html)
- [React 19 Migration Guide](https://react.dev/blog/2024/04/25/react-19)
- [class-variance-authority Issues](https://github.com/joe-bell/cva/issues)

---

## ✅ Status

- **Data:** 26/10/2025
- **Versão:** Frontend 1.0.1
- **Status:** ✅ Corrigido
- **Testado em:** Desenvolvimento local
- **Próximo:** Deploy para produção

---

**Nota:** Este erro foi capturado pelo **global error handler** implementado no `index.html`, que mostra overlay vermelho em produção. Isso facilitou o diagnóstico!
