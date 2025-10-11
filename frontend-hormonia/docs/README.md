# Documentação Frontend - Clínica Oncológica

**Última Atualização**: 2025-10-02

## 📋 Índice Geral

### 🏗️ Arquitetura
- [Sistema de Tipos](architecture/TYPE_SYSTEM.md)
- [Otimização de Performance](architecture/PERFORMANCE_OPTIMIZATION.md)
- [Correções TypeScript](architecture/TYPESCRIPT_INITIALIZATION_FIXES.md)

### 🔐 Autenticação
- [Uso do MedicoAuthContext](auth/MedicoAuthContext-Usage.md)

### 🧩 Componentes
- [Guia de Componentes](components/COMPONENTS_GUIDE.md)

### 📊 Charts & Visualizações
- [Recharts - Referência Rápida](RECHARTS_QUICK_REFERENCE.md)

### 📋 Queries & Cache
- [Migração Query Keys](QUERY_KEYS_MIGRATION_GUIDE.md)

### 🚀 Deployment
- [Guia de Deployment](deployment/DEPLOYMENT_GUIDE.md)

### 🧪 Testes
- [Guia de Testes](testing/TESTING_GUIDE.md)


## 📁 Estrutura do Frontend

```
frontend-hormonia/
├── src/
│   ├── components/         # Componentes React
│   ├── contexts/           # React Contexts (Auth, etc)
│   ├── pages/              # Páginas/Rotas
│   ├── services/           # API clients
│   ├── types/              # TypeScript types
│   └── utils/              # Utilidades
├── public/                 # Assets estáticos
└── docs/                   # Esta documentação
```

## 🚀 Quick Start

```bash
# Install
cd frontend-hormonia
npm install

# Configure
cp .env.example .env.local
# Edit .env.local with your API endpoints

# Run
npm run dev

# Test
npm test

# Build
npm run build
```

## 🔐 Autenticação

- **Context**: MedicoAuthContext para gerenciamento de sessão
- **Firebase**: Integração com Firebase Authentication
- **Tokens**: JWT access + refresh tokens sincronizados com backend

## 🎨 Componentes

- Design system consistente
- Componentes reutilizáveis
- TypeScript strict mode
- Props bem tipadas

## 🧪 Testing

```bash
# Unit tests
npm test

# E2E tests
npm run test:e2e

# Coverage
npm run test:coverage
```

## 📚 Navegação

- [← Backend](../../backend-hormonia/docs/README.md)
- [← Voltar para Raiz](../../README.md)
- [Quiz Interface →](../../quiz-mensal-interface/docs/README.md)

## 📈 Performance & Otimização

O frontend implementa otimizações abrangentes para melhor performance:

- **Lazy Loading:** Todas as rotas com React.lazy()
- **Code Splitting:** Chunks automáticos via Vite
- **Cache Persistente:** IndexedDB com React Query
- **Componente Optimization:** React.memo em componentes críticos
- **Bundle Reduction:** 50% redução no bundle inicial

Ver [Guia de Performance](architecture/PERFORMANCE_OPTIMIZATION.md) para detalhes completos.

## Convenções

- **Canônicos**: Documentos de referência atuais e mantidos
- **Arquitetura**: Documentos técnicos em `architecture/`
- **Língua**: PT-BR (padrão do projeto)

---

**Stack:** React | TypeScript | Vite | Tailwind CSS | Firebase
