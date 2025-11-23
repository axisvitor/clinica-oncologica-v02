# Getting Started - Frontend Hormonia

**Tempo estimado de setup**: 4 horas (de 1 dia para 4 horas!)

Este guia irá levá-lo do zero até ter o frontend rodando localmente em 4 horas, incluindo a compreensão da arquitetura e configuração de todas as ferramentas necessárias.

## Índice

1. [Pré-requisitos](#pré-requisitos)
2. [Instalação Rápida](#instalação-rápida)
3. [Configuração do Ambiente](#configuração-do-ambiente)
4. [Primeira Execução](#primeira-execução)
5. [Estrutura do Projeto](#estrutura-do-projeto)
6. [Configuração da IDE](#configuração-da-ide)
7. [Troubleshooting](#troubleshooting)
8. [Próximos Passos](#próximos-passos)

---

## Pré-requisitos

Antes de começar, certifique-se de ter instalado:

### Software Obrigatório

| Software | Versão Mínima | Verificação | Como Instalar |
|----------|---------------|-------------|---------------|
| **Node.js** | 18.0+ | `node --version` | [nodejs.org](https://nodejs.org/) |
| **npm** | 9.0+ | `npm --version` | Incluído com Node.js |
| **Git** | 2.0+ | `git --version` | [git-scm.com](https://git-scm.com/) |

### Software Recomendado

- **VS Code** - Editor recomendado com suporte TypeScript
- **Google Chrome** - Para desenvolvimento e debug
- **Postman/Insomnia** - Para testar APIs (opcional)

### Verificação Rápida

```bash
# Execute este comando para verificar todas as dependências
node --version && npm --version && git --version

# Saída esperada (versões podem variar):
# v18.17.0
# 9.8.1
# git version 2.42.0
```

---

## Instalação Rápida

### Passo 1: Clone o Repositório

```bash
# Clone o projeto
git clone https://github.com/axisvitor/clinica-oncologica-v01.git
cd clinica-oncologica-v01

# Navegue para o frontend
cd frontend-hormonia

# Verifique que está no branch correto
git branch
```

### Passo 2: Instale as Dependências

```bash
# Instalação padrão (recomendado)
npm install

# OU com cache limpo (se tiver problemas)
npm ci

# Tempo estimado: 3-5 minutos
```

**Nota**: Durante a instalação, você verá downloads de ~500MB de dependências. Isso é normal.

### Passo 3: Configure o Ambiente

```bash
# Copie o arquivo de exemplo
cp .env.example .env

# Abra o arquivo para edição
# No Windows: notepad .env
# No Mac/Linux: nano .env
```

**Configuração Mínima para Desenvolvimento Local:**

```env
# Backend API - LOCAL DEVELOPMENT
VITE_API_URL=http://localhost:8000/api/v2
VITE_API_BASE_URL=http://localhost:8000
VITE_WS_URL=ws://localhost:8000/ws

# Firebase (obter do console Firebase)
VITE_FIREBASE_API_KEY=your-firebase-api-key
VITE_FIREBASE_AUTH_DOMAIN=your-project-id.firebaseapp.com
VITE_FIREBASE_PROJECT_ID=your-project-id
VITE_FIREBASE_APP_ID=your-firebase-app-id
VITE_FIREBASE_MESSAGING_SENDER_ID=your-messaging-sender-id

# Ambiente
VITE_ENVIRONMENT=development
VITE_DEBUG_MODE=true
```

> **Dica**: Para obter as credenciais Firebase, veja a seção [Configuração Firebase](#configuração-firebase)

### Passo 4: Inicie o Servidor de Desenvolvimento

```bash
# Inicie o servidor
npm run dev

# Saída esperada:
# VITE v6.0.7  ready in 823 ms
# ➜  Local:   http://localhost:3000/
# ➜  Network: use --host to expose
```

### Passo 5: Acesse a Aplicação

Abra seu navegador em: **http://localhost:3000**

Você deverá ver a tela de login do sistema Hormonia.

**🎉 Parabéns! O frontend está rodando!**

---

## Configuração do Ambiente

### Arquivo .env Completo

O arquivo `.env` controla todo o comportamento da aplicação. Aqui está uma configuração completa comentada:

```env
# =============================================================================
# BACKEND API CONFIGURATION
# =============================================================================
# URL base da API (sem /api/v2 no final)
VITE_API_BASE_URL=http://localhost:8000

# URL completa da API (com /api/v2)
VITE_API_URL=http://localhost:8000/api/v2

# WebSocket URL para real-time features
VITE_WS_URL=ws://localhost:8000/ws
VITE_WS_BASE_URL=ws://localhost:8000/ws

# =============================================================================
# FIREBASE AUTHENTICATION
# =============================================================================
# Credenciais públicas do Firebase (seguras para o browser)
VITE_FIREBASE_API_KEY=AIzaSyExample123456789
VITE_FIREBASE_AUTH_DOMAIN=hormonia-dev.firebaseapp.com
VITE_FIREBASE_PROJECT_ID=hormonia-dev
VITE_FIREBASE_STORAGE_BUCKET=hormonia-dev.firebasestorage.app
VITE_FIREBASE_MESSAGING_SENDER_ID=123456789012
VITE_FIREBASE_APP_ID=1:123456789012:web:abc123def456

# =============================================================================
# APPLICATION SETTINGS
# =============================================================================
VITE_ENVIRONMENT=development
VITE_DEBUG_MODE=true
VITE_APP_NAME=Hormonia - Sistema de Gestão Oncológica
VITE_APP_VERSION=2.0.0

# =============================================================================
# FEATURE FLAGS
# =============================================================================
# Habilita/desabilita funcionalidades
VITE_ENABLE_WHATSAPP_INTEGRATION=true
VITE_ENABLE_AI_CHAT=true
VITE_AI_ANALYTICS_ENABLED=true
VITE_AI_INSIGHTS_ENABLED=true

# Features de desenvolvimento
VITE_ENABLE_DEBUG_TOOLS=true
VITE_USE_MOCK_DATA=false

# =============================================================================
# SECURITY & SESSION
# =============================================================================
# Timeout da sessão (1 hora em ms)
VITE_SESSION_TIMEOUT=3600000

# Tempo antes de renovar token (5 minutos em ms)
VITE_TOKEN_REFRESH_THRESHOLD=300000

# =============================================================================
# PERFORMANCE
# =============================================================================
# Timeout de requisições HTTP (30 segundos)
VITE_REQUEST_TIMEOUT=30000

# Tentativas de retry em caso de erro
VITE_REQUEST_RETRY_ATTEMPTS=3

# Cache de dados (5 minutos em ms)
VITE_CACHE_DURATION=300000

# =============================================================================
# FILE UPLOAD
# =============================================================================
# Tamanho máximo de arquivo (10MB em bytes)
VITE_MAX_FILE_SIZE=10485760

# Tipos de arquivo permitidos
VITE_SUPPORTED_FILE_TYPES=image/jpeg,image/png,image/gif,application/pdf
```

### Configuração Firebase

Para obter as credenciais Firebase:

1. **Acesse o Firebase Console**: [console.firebase.google.com](https://console.firebase.google.com/)

2. **Selecione/Crie o Projeto**:
   - Se existe: selecione "hormonia-dev" ou similar
   - Se não existe: clique em "Adicionar projeto"

3. **Obtenha as Credenciais**:
   - No menu lateral, clique no ícone de engrenagem ⚙️
   - Selecione "Configurações do projeto"
   - Role até "Seus apps" → "SDK setup and configuration"
   - Copie os valores de `firebaseConfig`

4. **Cole no .env**:
   ```env
   VITE_FIREBASE_API_KEY=<apiKey>
   VITE_FIREBASE_AUTH_DOMAIN=<authDomain>
   VITE_FIREBASE_PROJECT_ID=<projectId>
   VITE_FIREBASE_STORAGE_BUCKET=<storageBucket>
   VITE_FIREBASE_MESSAGING_SENDER_ID=<messagingSenderId>
   VITE_FIREBASE_APP_ID=<appId>
   ```

### Verificando a Configuração

Após configurar o `.env`, você pode verificar se tudo está correto:

```bash
# Execute o validador de configuração
npm run check:env

# Ou verifique manualmente no console do browser
# Abra: http://localhost:3000
# Pressione F12 → Console
# Digite: window.__RUNTIME_CONFIG__
```

---

## Primeira Execução

### Backend Local Necessário

O frontend **precisa** do backend rodando. Siga estes passos:

1. **Em outro terminal**, navegue até o backend:
   ```bash
   cd ../backend-hormonia
   ```

2. **Configure o backend** (primeira vez):
   ```bash
   # Copie o .env
   cp .env.example .env

   # Instale dependências Python
   pip install -r requirements.txt

   # Execute migrations
   alembic upgrade head
   ```

3. **Inicie o backend**:
   ```bash
   # Com uvicorn
   uvicorn app.main:app --reload --port 8000

   # OU com o script make
   make run
   ```

4. **Verifique que o backend está rodando**:
   ```bash
   # Em outro terminal
   curl http://localhost:8000/health

   # Resposta esperada:
   # {"status":"healthy","version":"2.0.0"}
   ```

### Testando a Integração

Com backend e frontend rodando:

1. **Acesse o frontend**: http://localhost:3000

2. **Tente fazer login** com credenciais de teste:
   ```
   Email: admin@hormonia.com.br
   Senha: Admin@123
   ```

3. **Verifique o console do browser** (F12):
   - Não deve haver erros vermelhos de CORS
   - Deve ver logs de "API client initialized"
   - Deve ver requisições bem-sucedidas em Network tab

### Seed Data (Dados de Teste)

Para popular o banco com dados de teste:

```bash
# No diretório backend-hormonia
cd backend-hormonia

# Execute o script de seed
python scripts/seed_database.py

# Ou com make
make seed
```

Isso criará:
- Usuário admin padrão
- Pacientes de exemplo
- Templates de questionários
- Fluxos de comunicação

---

## Estrutura do Projeto

Entender a estrutura é crucial para trabalhar eficientemente:

```
frontend-hormonia/
│
├── src/                          # Código-fonte principal
│   ├── components/               # Componentes React reutilizáveis
│   │   ├── ui/                   # Componentes base (shadcn/ui)
│   │   ├── admin/                # Componentes de administração
│   │   ├── ai/                   # Componentes de IA
│   │   ├── common/               # Componentes compartilhados
│   │   ├── forms/                # Componentes de formulários
│   │   ├── layout/               # Layout e navegação
│   │   ├── patients/             # Componentes de pacientes
│   │   ├── quiz/                 # Questionários
│   │   └── charts/               # Gráficos e visualizações
│   │
│   ├── pages/                    # Páginas/Rotas da aplicação
│   │   ├── DashboardPage.tsx     # Dashboard principal
│   │   ├── PatientsPage.tsx      # Listagem de pacientes
│   │   ├── LoginPage.tsx         # Tela de login
│   │   └── ...                   # Outras páginas
│   │
│   ├── hooks/                    # React Hooks customizados
│   │   ├── usePatients.ts        # Hook para gerenciar pacientes
│   │   ├── useAuth.ts            # Hook de autenticação
│   │   ├── useWebSocket.ts       # Hook para WebSocket
│   │   └── api/                  # Hooks específicos de API
│   │
│   ├── contexts/                 # React Contexts
│   │   ├── AuthContext.tsx       # Context de autenticação
│   │   └── MedicoAuthContext.tsx # Context específico de médicos
│   │
│   ├── lib/                      # Bibliotecas e utilitários
│   │   ├── api-client/           # Cliente API modular
│   │   │   ├── core.ts           # Cliente HTTP base
│   │   │   ├── auth.ts           # Endpoints de autenticação
│   │   │   ├── patients.ts       # Endpoints de pacientes
│   │   │   ├── monthly-quiz.ts   # Endpoints de questionários
│   │   │   └── analytics.ts      # Endpoints de analytics
│   │   ├── websocket.ts          # Gerenciador WebSocket
│   │   ├── logger.ts             # Sistema de logs
│   │   └── utils.ts              # Funções utilitárias
│   │
│   ├── types/                    # Definições TypeScript
│   │   ├── api.ts                # Types da API
│   │   ├── auth.ts               # Types de autenticação
│   │   ├── quiz.ts               # Types de questionários
│   │   └── ...                   # Outros types
│   │
│   ├── features/                 # Módulos de funcionalidades
│   │   ├── monthly-quiz/         # Feature de quiz mensal
│   │   └── ...                   # Outras features
│   │
│   └── tests/                    # Testes (organizados por tipo)
│       ├── unit/                 # Testes unitários
│       ├── integration/          # Testes de integração
│       ├── e2e/                  # Testes end-to-end
│       └── test-utils/           # Utilitários de teste
│
├── public/                       # Assets estáticos
│   ├── images/                   # Imagens e logos
│   └── config.js                 # Config runtime injetado
│
├── docs/                         # Documentação
│   ├── GETTING_STARTED.md        # 👈 Você está aqui!
│   ├── ENVIRONMENT_VARIABLES.md  # Guia de variáveis
│   ├── API_INTEGRATION.md        # Guia de integração API
│   └── ...                       # Outros docs
│
├── .env                          # Variáveis de ambiente (não commitado)
├── .env.example                  # Template de variáveis
├── package.json                  # Dependências e scripts
├── tsconfig.json                 # Configuração TypeScript
├── vite.config.ts                # Configuração Vite
└── tailwind.config.js            # Configuração Tailwind CSS
```

### Arquivos Importantes

| Arquivo | Propósito |
|---------|-----------|
| `src/main.tsx` | Entry point da aplicação |
| `src/App.tsx` | Componente raiz, rotas principais |
| `src/lib/api-client/index.ts` | Cliente API centralizado |
| `vite.config.ts` | Configuração do bundler |
| `package.json` | Dependências e scripts npm |

---

## Configuração da IDE

### VS Code (Recomendado)

#### Extensões Essenciais

Instale estas extensões para melhor experiência:

```json
{
  "recommendations": [
    "dbaeumer.vscode-eslint",           // ESLint
    "esbenp.prettier-vscode",           // Prettier
    "bradlc.vscode-tailwindcss",        // Tailwind CSS IntelliSense
    "yoavbls.pretty-ts-errors",         // Erros TypeScript legíveis
    "ms-vscode.vscode-typescript-next", // TypeScript mais recente
    "formulahendry.auto-rename-tag",    // Renomeia tags HTML/JSX
    "christian-kohler.path-intellisense", // Autocomplete de paths
    "dsznajder.es7-react-js-snippets"   // Snippets React
  ]
}
```

**Instalação Rápida**:
1. Copie o código acima
2. Crie `.vscode/extensions.json` na raiz do projeto
3. VS Code mostrará um popup para instalar todas

#### Configurações Recomendadas

Crie `.vscode/settings.json`:

```json
{
  // TypeScript
  "typescript.tsdk": "node_modules/typescript/lib",
  "typescript.enablePromptUseWorkspaceTsdk": true,

  // Format on save
  "editor.formatOnSave": true,
  "editor.defaultFormatter": "esbenp.prettier-vscode",

  // ESLint
  "eslint.validate": [
    "javascript",
    "javascriptreact",
    "typescript",
    "typescriptreact"
  ],
  "eslint.format.enable": true,

  // Tailwind CSS
  "tailwindCSS.experimental.classRegex": [
    ["cva\\(([^)]*)\\)", "[\"'`]([^\"'`]*).*?[\"'`]"],
    ["cn\\(([^)]*)\\)", "[\"'`]([^\"'`]*).*?[\"'`]"]
  ],

  // Auto-import
  "typescript.preferences.importModuleSpecifier": "relative",
  "typescript.updateImportsOnFileMove.enabled": "always",

  // Files
  "files.exclude": {
    "**/.git": true,
    "**/.DS_Store": true,
    "**/node_modules": true,
    "**/dist": true
  }
}
```

#### Snippets Úteis

Crie `.vscode/react.code-snippets`:

```json
{
  "React Functional Component": {
    "prefix": "rfc",
    "body": [
      "import React from 'react'",
      "",
      "interface ${1:ComponentName}Props {",
      "  $2",
      "}",
      "",
      "export const ${1:ComponentName}: React.FC<${1:ComponentName}Props> = ({",
      "  $3",
      "}) => {",
      "  return (",
      "    <div>",
      "      $0",
      "    </div>",
      "  )",
      "}",
      ""
    ],
    "description": "Create a React functional component with TypeScript"
  }
}
```

### Configuração de Debugging

Crie `.vscode/launch.json` para debugging no VS Code:

```json
{
  "version": "0.2.0",
  "configurations": [
    {
      "type": "chrome",
      "request": "launch",
      "name": "Launch Chrome against localhost",
      "url": "http://localhost:3000",
      "webRoot": "${workspaceFolder}/src",
      "sourceMaps": true
    }
  ]
}
```

---

## Troubleshooting

### Problemas Comuns e Soluções

#### 1. Erro: "Cannot find module '@/lib/api-client'"

**Causa**: Paths do TypeScript não configurados.

**Solução**:
```bash
# Verifique tsconfig.json
cat tsconfig.json | grep paths

# Deve conter:
# "paths": {
#   "@/*": ["./src/*"]
# }

# Se não estiver, adicione e reinicie o TS server
# No VS Code: Ctrl+Shift+P → "TypeScript: Restart TS Server"
```

#### 2. Erro: "CORS blocked"

**Causa**: Backend não está configurado para aceitar requisições do frontend.

**Solução**:
```python
# No backend-hormonia/app/main.py
# Verifique se CORS está configurado:

from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

#### 3. Erro: "Firebase: Error (auth/invalid-api-key)"

**Causa**: Credenciais Firebase incorretas ou não configuradas.

**Solução**:
```bash
# 1. Verifique o .env
grep VITE_FIREBASE .env

# 2. Certifique-se que as variáveis começam com VITE_
# 3. Reinicie o servidor de dev após alterar .env
npm run dev
```

#### 4. Página em branco após build

**Causa**: Paths incorretos em produção ou erro de runtime não capturado.

**Solução**:
```bash
# 1. Verifique erros no console do browser
# 2. Teste o build localmente
npm run build
npm run preview

# 3. Verifique base URL no vite.config.ts
# base: '/' (para root domain)
# base: '/app/' (para subdirectory)
```

#### 5. WebSocket não conecta

**Causa**: Backend WebSocket não está rodando ou URL incorreta.

**Solução**:
```bash
# 1. Verifique se backend está rodando
curl http://localhost:8000/health

# 2. Teste WebSocket manualmente
# No console do browser:
const ws = new WebSocket('ws://localhost:8000/ws')
ws.onopen = () => console.log('Connected!')

# 3. Verifique VITE_WS_URL no .env
echo $VITE_WS_URL
```

#### 6. Erros de TypeScript após atualização

**Causa**: Cache do TypeScript desatualizado.

**Solução**:
```bash
# Limpe o cache e reinstale
rm -rf node_modules package-lock.json
npm install

# No VS Code: Reload TypeScript
# Ctrl+Shift+P → "TypeScript: Restart TS Server"
```

#### 7. Testes falhando após mudanças

**Causa**: Snapshots desatualizados ou imports quebrados.

**Solução**:
```bash
# Atualize snapshots
npm run test -- -u

# Execute em modo watch para debug
npm run test:watch

# Verifique coverage
npm run test:coverage
```

### Debug Avançado

#### Habilitar Logs Detalhados

```env
# No .env
VITE_DEBUG_MODE=true
VITE_LOG_LEVEL=debug
```

```typescript
// No código
import { createLogger } from '@/lib/logger'

const logger = createLogger('MyComponent')

logger.debug('Estado atual:', state)
logger.error('Erro ao processar:', error)
```

#### React DevTools

1. **Instale a extensão**: [React Developer Tools](https://react.dev/learn/react-developer-tools)

2. **Use para inspecionar**:
   - Components tree
   - Props e state
   - Hooks
   - Performance profiling

#### Network Inspector

No Chrome DevTools (F12):

1. **Aba Network**:
   - Filtro: `XHR` para APIs
   - Filtro: `WS` para WebSockets

2. **Verifique requisições**:
   - Status code (200, 401, 500, etc.)
   - Headers (Authorization, Content-Type)
   - Payload (request/response body)
   - Timing (tempo de resposta)

---

## Próximos Passos

Agora que você tem o ambiente configurado, aqui estão os próximos passos recomendados:

### 1. Entenda a Arquitetura (30 minutos)

Leia estes documentos na ordem:

1. **[API Integration Guide](API_INTEGRATION.md)** - Como fazer requisições
2. **[Environment Variables](ENVIRONMENT_VARIABLES.md)** - Todas as variáveis explicadas
3. **[Type Safety Guidelines](TYPE_SAFETY_GUIDELINES.md)** - Padrões TypeScript

### 2. Explore o Código (1 hora)

Navegue por estes arquivos para entender o flow:

```bash
# 1. Entry point e rotas
src/main.tsx                    # Inicialização
src/App.tsx                     # Rotas principais

# 2. Autenticação
src/contexts/AuthContext.tsx    # Gerenciamento de sessão
src/pages/LoginPage.tsx         # Tela de login

# 3. Exemplo completo de CRUD
src/pages/PatientsPage.tsx      # Listagem
src/hooks/usePatients.ts        # Logic layer
src/lib/api-client/patients.ts  # API calls
```

### 3. Faça Sua Primeira Mudança (1 hora)

Exercício prático:

**Objetivo**: Adicionar um novo campo ao formulário de paciente

1. **Adicione o type**:
   ```typescript
   // src/types/api.ts
   export interface Patient {
     // ... campos existentes
     preferredContactTime?: string // NOVO
   }
   ```

2. **Adicione ao formulário**:
   ```tsx
   // src/components/patients/CreatePatientDialog.tsx
   <FormField
     name="preferredContactTime"
     label="Horário Preferido de Contato"
     // ...
   />
   ```

3. **Teste a mudança**:
   ```bash
   npm run dev
   # Abra o formulário e verifique o novo campo
   ```

### 4. Execute os Testes (30 minutos)

```bash
# Testes unitários
npm run test

# Testes E2E
npm run test:e2e

# Veja o coverage
npm run test:coverage
```

### 5. Estude os Componentes (1 hora)

Analise componentes reutilizáveis:

```bash
# Componentes base (shadcn/ui)
src/components/ui/button.tsx
src/components/ui/dialog.tsx
src/components/ui/form.tsx

# Componentes de negócio
src/components/patients/PatientCard.tsx
src/components/quiz/QuizForm.tsx
```

### 6. Aprenda React Query (30 minutos)

O projeto usa React Query para gerenciar estado do servidor:

```typescript
// Exemplo de uso
import { useQuery } from '@tanstack/react-query'

const { data, isLoading, error } = useQuery({
  queryKey: ['patients', filters],
  queryFn: () => apiClient.patients.list(filters),
  staleTime: 5 * 60 * 1000 // Cache por 5 minutos
})
```

Leia: [Guia de React Query](https://tanstack.com/query/latest/docs/react/overview)

---

## Recursos Adicionais

### Documentação Oficial

- **React**: [react.dev](https://react.dev/)
- **TypeScript**: [typescriptlang.org](https://www.typescriptlang.org/)
- **Vite**: [vitejs.dev](https://vitejs.dev/)
- **TanStack Query**: [tanstack.com/query](https://tanstack.com/query)
- **Tailwind CSS**: [tailwindcss.com](https://tailwindcss.com/)

### Documentação Interna

- **[Components Guide](components/COMPONENTS_GUIDE.md)** - Catálogo de componentes
- **[Testing Guide](testing/TESTING_GUIDE.md)** - Estratégias de teste
- **[Deployment Guide](deployment/DEPLOYMENT_GUIDE.md)** - Como fazer deploy
- **[Type Patterns](TYPE_PATTERNS.md)** - Padrões TypeScript comuns

### Comunidade e Suporte

- **Issues**: Reporte bugs no GitHub
- **Discussions**: Perguntas e discussões técnicas
- **Wiki**: Documentação adicional e FAQs

---

## Checklist de Configuração Completa

Use este checklist para garantir que tudo está funcionando:

- [ ] Node.js 18+ instalado
- [ ] npm 9+ instalado
- [ ] Repositório clonado
- [ ] Dependências instaladas (`npm install`)
- [ ] Arquivo `.env` criado e configurado
- [ ] Backend rodando em `http://localhost:8000`
- [ ] Frontend rodando em `http://localhost:3000`
- [ ] Login funcionando
- [ ] Consegue ver dashboard
- [ ] Consegue navegar entre páginas
- [ ] WebSocket conectado (verificar no console)
- [ ] VS Code configurado com extensões
- [ ] Testes executam sem erros (`npm test`)
- [ ] Build produção funciona (`npm run build`)

---

## Dúvidas Frequentes

**P: Preciso rodar o backend obrigatoriamente?**
R: Sim, o frontend depende da API do backend. Alternativamente, você pode usar mock data configurando `VITE_USE_MOCK_DATA=true`.

**P: Posso usar yarn ou pnpm ao invés de npm?**
R: Sim, mas recomendamos npm 9+ para consistência. Se usar outro, delete `package-lock.json` e gere o lock file equivalente.

**P: Como faço para trabalhar offline?**
R: Configure mocks: `VITE_USE_MOCK_DATA=true` no `.env`. Os dados virão de `src/mocks/`.

**P: O hot reload não está funcionando.**
R: Verifique se está usando `npm run dev` e não `npm start`. Limpe o cache: `rm -rf node_modules/.vite`.

**P: Erro "Port 3000 is already in use".**
R: Altere a porta com: `npm run dev -- --port 3001` ou mate o processo na porta 3000.

---

**Tempo Total Estimado**: ~4 horas

- Setup inicial: 1h
- Configuração e testes: 1h
- Exploração de código: 1h
- Primeiro desenvolvimento: 1h

**Próximo**: [Environment Variables Guide →](ENVIRONMENT_VARIABLES.md)

---

*Última atualização: 2025-11-13*
*Mantido por: Equipe Hormonia*
