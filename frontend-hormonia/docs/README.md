# Documentação Frontend - Clínica Oncológica

**Última Atualização**: 2025-10-02

## 📋 Índice Geral

### 🏗️ Arquitetura
- [Sistema de Tipos](architecture/TYPE_SYSTEM.md)

### 🔐 Autenticação
- [Uso do MedicoAuthContext](auth/MedicoAuthContext-Usage.md)

### 🧩 Componentes
- [Guia de Componentes](components/COMPONENTS_GUIDE.md)

### 🚀 Deployment
- [Guia de Deployment](deployment/DEPLOYMENT_GUIDE.md)

### 🧪 Testes
- [Guia de Testes](testing/TESTING_GUIDE.md)

### 📋 Relatórios Arquivados
- [Relatórios de Incidentes](incidents/_archive/)

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

## Convenções

- **Canônicos**: Documentos de referência atuais e mantidos
- **Arquivados**: Relatórios históricos em `incidents/_archive/`
- **Língua**: PT-BR (padrão do projeto)

---

**Stack:** React | TypeScript | Vite | Tailwind CSS | Firebase
