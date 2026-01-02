# Documentacao Frontend Hormonia

**Versao**: 2.0 (Consolidada)
**Ultima Atualizacao**: 2025-12-26

---

## Quick Start

```bash
cd frontend-hormonia
npm install
npm run dev
# Acessar: http://localhost:5173
```

---

## Indice de Documentacao

### Onboarding (Comece Aqui!)

| Guia | Descricao |
|------|-----------|
| [Getting Started](./GETTING_STARTED.md) | Setup completo em 4 horas |
| [Environment Guide](./configuration/ENVIRONMENT_GUIDE.md) | Variaveis de ambiente |

### Desenvolvimento

| Guia | Descricao |
|------|-----------|
| [API Guide](./api/API_GUIDE.md) | Cliente HTTP, React Query, tratamento de erros |
| [TypeScript Guide](./types/TYPESCRIPT_GUIDE.md) | Padroes de tipos, seguranca, boas praticas |
| [Components Guide](./components/COMPONENTS_GUIDE.md) | Sistema de componentes |
| [Testing Guide](./testing/TESTING_GUIDE.md) | Testes unitarios e E2E |

### Arquitetura

| Guia | Descricao |
|------|-----------|
| [Type System](./architecture/TYPE_SYSTEM.md) | Sistema de tipos centralizado |
| [Responsive Design](./architecture/RESPONSIVE_DESIGN.md) | Mobile/tablet responsiveness |
| [TypeScript Fixes](./architecture/TYPESCRIPT_INITIALIZATION_FIXES.md) | Correcoes de inicializacao |

### Performance

| Guia | Descricao |
|------|-----------|
| [Performance Guide](./performance/PERFORMANCE_GUIDE.md) | React.memo, useMemo, lazy loading, monitoramento |

### Deploy

| Guia | Descricao |
|------|-----------|
| [Deployment Guide](./deployment/DEPLOYMENT_GUIDE.md) | Railway, Vercel, Netlify, Docker |

### Autenticacao

| Guia | Descricao |
|------|-----------|
| [MedicoAuthContext](./auth/MedicoAuthContext-Usage.md) | Contexto de autenticacao |

### Features

| Guia | Descricao |
|------|-----------|
| [Patient Import](./features/PATIENT_IMPORT_UI.md) | Interface de importacao de pacientes |

### Migracoes

| Guia | Descricao |
|------|-----------|
| [Migration Guide](./guides/MIGRATION_GUIDE.md) | Guia de migracao de API |

---

## Estrutura de Pastas

```
frontend-hormonia/docs/
├── README.md                    # Este arquivo
├── GETTING_STARTED.md           # Onboarding
├── api/
│   └── API_GUIDE.md             # Cliente HTTP consolidado
├── architecture/
│   ├── TYPE_SYSTEM.md           # Sistema de tipos
│   ├── RESPONSIVE_DESIGN.md     # Responsividade
│   └── TYPESCRIPT_INITIALIZATION_FIXES.md
├── auth/
│   └── MedicoAuthContext-Usage.md
├── components/
│   └── COMPONENTS_GUIDE.md
├── configuration/
│   └── ENVIRONMENT_GUIDE.md     # Variaveis de ambiente consolidado
├── deployment/
│   └── DEPLOYMENT_GUIDE.md      # Deploy consolidado
├── features/
│   └── PATIENT_IMPORT_UI.md
├── guides/
│   └── MIGRATION_GUIDE.md
├── performance/
│   └── PERFORMANCE_GUIDE.md     # Performance consolidado
├── testing/
│   └── TESTING_GUIDE.md
└── types/
    └── TYPESCRIPT_GUIDE.md      # TypeScript consolidado
```

---

## Stack Tecnologica

| Tecnologia | Versao | Proposito |
|------------|--------|-----------|
| React | 19.0 | Framework UI |
| TypeScript | 5.0+ | Tipagem estatica |
| Vite | 6.0+ | Build tool |
| TanStack Query | 5.62+ | Data fetching e cache |
| Radix UI | - | Componentes acessiveis |
| Tailwind CSS | 4.0+ | Estilizacao |
| Firebase Auth | 6.6+ | Autenticacao |

---

## Scripts

```bash
# Desenvolvimento
npm run dev              # Dev server
npm run preview          # Preview build

# Build
npm run build            # Build producao
npm run build:prod       # Build explicito

# Qualidade
npm run lint             # ESLint
npm run typecheck        # TypeScript check
npm run test             # Testes unitarios
npm run test:e2e         # Testes E2E
```

---

## Navegacao

- [Backend Docs](../../backend-hormonia/docs/README.md)
- [Quiz Interface](../../quiz-mensal-interface/docs/README.md)
- [Projeto Raiz](../../README.md)

---

*Documentacao consolidada de 51 arquivos para 15 guias organizados.*
