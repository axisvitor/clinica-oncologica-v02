# Quiz Mensal - Interface Next.js

Interface standalone para questionário mensal de bem-estar, integrada com o backend Hormonia.

## 📋 Funcionalidades

- ✅ Acesso via token JWT (link único por paciente)
- ✅ Validação automática de token e expiração
- ✅ Suporte para múltiplos tipos de questões:
  - Escolha única (single_choice)
  - Múltipla escolha (multiple_choice)
  - Escala numérica (scale)
  - Texto livre (text)
  - Sim/Não (yes_no)
- ✅ Progress bar em tempo real
- ✅ Submissão de respostas em tempo real
- ✅ Estados de loading e erro
- ✅ Navegação entre questões (avançar/voltar)
- ✅ Tela de conclusão
- ✅ Design responsivo (mobile-first)
- ✅ Toast notifications

## 🚀 Como Usar

### 1. Configuração

Copie o arquivo `.env.example` para `.env.local`:

```bash
cp .env.example .env.local
```

Ajuste as variáveis de ambiente:

```env
# API Configuration
# ⚠️ IMPORTANT: DO NOT include /api/v1 in the URL - it's auto-injected!
# WRONG: NEXT_PUBLIC_API_URL=http://localhost:8000/api/v1 ❌
# CORRECT OPTIONS:
NEXT_PUBLIC_API_URL=http://localhost:8000  # Base URL only (recommended)
# OR use explicit endpoint:
# NEXT_PUBLIC_QUIZ_PUBLIC_API_URL=http://localhost:8000/api/v1/monthly-quiz-public

# App Configuration
NEXT_PUBLIC_APP_NAME=Hormonia - Quiz Mensal de Bem-Estar

# Frontend URL
NEXT_PUBLIC_FRONTEND_URL=http://localhost:3000
```

### ⚠️ Critical: API URL Configuration

**The lib/api.ts file automatically appends `/api/v1/monthly-quiz-public` to the base URL!**

**Two ways to configure:**

1. **Method 1 (Recommended): Base URL Only**
   ```env
   NEXT_PUBLIC_API_URL=http://localhost:8000
   ```
   Result: `http://localhost:8000/api/v1/monthly-quiz-public` ✅

2. **Method 2: Explicit Full Path**
   ```env
   NEXT_PUBLIC_QUIZ_PUBLIC_API_URL=http://localhost:8000/api/v1/monthly-quiz-public
   ```
   Result: Uses explicit URL directly ✅

**❌ WRONG - Causes 404 Errors:**
```env
NEXT_PUBLIC_API_URL=http://localhost:8000/api/v1  # Will duplicate to /api/v1/api/v1/monthly-quiz-public
```

### 2. Instalação

```bash
npm install
# ou
pnpm install
# ou
yarn install
```

### 3. Desenvolvimento

```bash
npm run dev
```

Acesse: `http://localhost:3000?token=YOUR_TOKEN_HERE`

### 4. Build para Produção

```bash
npm run build
npm start
```

## 🔗 Integração com Backend

### Endpoints Utilizados

#### 1. POST `/api/v1/monthly-quiz/access`
Acessa o quiz usando o token:

```typescript
{
  token: string
}
```

Retorna:
```typescript
{
  quiz_session_id: string
  patient_name: string
  template_name: string
  template_version: string
  questions: QuizQuestion[]
  current_question_index: number
  total_questions: number
  expires_at: string
}
```

#### 2. POST `/api/v1/monthly-quiz/submit`
Submete uma resposta:

```typescript
{
  token: string
  question_id: string
  response_value: string
  response_metadata?: Record<string, any>
}
```

Retorna:
```typescript
{
  success: boolean
  response_id?: string
  message: string
  is_last_question?: boolean
}
```

## 📁 Estrutura de Arquivos

```
quiz-mensal-interface/
├── app/
│   ├── layout.tsx          # Layout principal com Toaster
│   └── page.tsx            # Página principal com auth guard
├── components/
│   ├── quiz-interface.tsx  # Componente principal do quiz
│   └── ui/                 # Componentes UI shadcn/ui
├── lib/
│   ├── api.ts              # Cliente API
│   └── utils.ts            # Utilitários
├── types/
│   └── quiz.ts             # Tipos TypeScript
├── .env.local              # Variáveis de ambiente (criar)
└── .env.example            # Template de env vars
```

## 🔐 Fluxo de Autenticação

1. Paciente recebe link via WhatsApp/Email/SMS: `https://quiz.app.com?token=XYZ`
2. Interface extrai token da URL
3. Token é validado no endpoint `/access`
4. Se válido, carrega sessão e questões
5. Se inválido/expirado, mostra erro apropriado

## 🎨 Tipos de Questões

### Single Choice (Escolha Única)
```json
{
  "type": "single_choice",
  "options": ["Opção 1", "Opção 2", "Opção 3"]
}
```

### Multiple Choice (Múltipla Escolha)
```json
{
  "type": "multiple_choice",
  "options": ["Opção A", "Opção B", "Opção C"]
}
```

### Scale (Escala Numérica)
```json
{
  "type": "scale",
  "min_value": 0,
  "max_value": 10
}
```

### Text (Texto Livre)
```json
{
  "type": "text"
}
```

### Yes/No (Sim/Não)
```json
{
  "type": "yes_no"
}
```

## 🛠️ Tecnologias

- **Next.js 14** - Framework React
- **TypeScript** - Tipagem estática
- **Tailwind CSS** - Estilização
- **shadcn/ui** - Componentes UI
- **Radix UI** - Primitivos acessíveis
- **Sonner** - Toast notifications

## 📱 Responsividade

A interface é totalmente responsiva e otimizada para:

- ✅ Mobile (320px+)
- ✅ Tablet (768px+)
- ✅ Desktop (1024px+)

## 🔒 Segurança

- ✅ Token JWT validado em cada requisição
- ✅ Verificação de expiração
- ✅ Rate limiting (backend)
- ✅ HTTPS em produção
- ✅ CORS configurado

## 📊 Estados da Interface

### Loading
- Spinner durante carregamento inicial
- "Carregando questionário..."

### Error
- Token inválido/ausente
- Token expirado
- Erro de rede
- Botão "Tentar Novamente" (quando aplicável)

### Quiz Ativo
- Progress bar
- Questão atual
- Navegação (Voltar/Próxima)
- Loading ao submeter

### Completado
- Ícone de sucesso
- Mensagem de conclusão
- Informações sobre confidencialidade

## 🚀 Deploy

### Railway (Recomendado para Produção)

A aplicação está configurada para deploy no Railway com suporte completo a Nixpacks.

**Guia Completo:** Veja [docs/RAILWAY_DEPLOYMENT.md](docs/RAILWAY_DEPLOYMENT.md) para instruções detalhadas.

**Quick Start:**

1. **Crie projeto no Railway:**
   ```bash
   railway init
   ```

2. **Configure variáveis de ambiente essenciais:**
   ```bash
   railway variables set NEXT_PUBLIC_QUIZ_PUBLIC_API_URL=https://your-backend.railway.app/api/v1/monthly-quiz-public
   railway variables set NEXTAUTH_URL=https://your-quiz-app.railway.app
   railway variables set NEXTAUTH_SECRET=$(openssl rand -base64 32)
   railway variables set JWT_SECRET=$(openssl rand -base64 32)
   railway variables set NODE_ENV=production
   ```

3. **Deploy:**
   ```bash
   railway up
   ```

**Variáveis Obrigatórias para Railway:**
- `NEXT_PUBLIC_QUIZ_PUBLIC_API_URL` - URL completa do backend
- `NEXTAUTH_URL` - URL da aplicação quiz
- `NEXTAUTH_SECRET` - Segredo NextAuth (gerar novo!)
- `JWT_SECRET` - Segredo JWT (gerar novo!)
- `NODE_ENV=production`

**⚠️ SEGURANÇA CRÍTICA:**
- Os secrets atuais no `.env.local` estão EXPOSTOS
- NUNCA use os secrets do `.env.local` em produção
- Gere novos secrets: `openssl rand -base64 32`
- Configure apenas via Railway dashboard/CLI

### Vercel (Alternativa)

```bash
vercel
```

Configure as env vars no dashboard:
- Todas as variáveis listadas em `.env.local.example`
- Especialmente: `NEXT_PUBLIC_QUIZ_PUBLIC_API_URL`, `NEXTAUTH_SECRET`, `JWT_SECRET`

### Docker

```dockerfile
FROM node:18-alpine AS deps
WORKDIR /app
COPY package*.json ./
RUN npm install --frozen-lockfile

FROM node:18-alpine AS builder
WORKDIR /app
COPY --from=deps /app/node_modules ./node_modules
COPY . .
RUN npm run build

FROM node:18-alpine AS runner
WORKDIR /app
ENV NODE_ENV production
COPY --from=builder /app/public ./public
COPY --from=builder /app/.next/standalone ./
COPY --from=builder /app/.next/static ./.next/static
EXPOSE 3000
ENV PORT 3000
CMD ["node", "server.js"]
```

## 🧪 Testando

1. Inicie o backend na porta 8000
2. Gere um link de quiz via admin
3. Copie o token do link gerado
4. Acesse: `http://localhost:3000?token=SEU_TOKEN`

## 📝 Notas de Desenvolvimento

- Respostas são enviadas em tempo real ao backend
- Progress é calculado baseado no índice da questão
- Navegação mantém estado local das respostas
- Toasts informam sucesso/erro de cada ação
- Link expira conforme configurado no backend (default: 72h)

## 🆘 Troubleshooting

### "Token não encontrado"
- Certifique-se de acessar com `?token=XXX` na URL

### "Link expirado"
- Solicite novo link ao médico/admin

### "Erro ao conectar" ou 404 Errors
- Verifique se backend está rodando
- **⚠️ CRITICAL**: Verifique `NEXT_PUBLIC_API_URL` - NÃO inclua `/api/v1` (use apenas `http://localhost:8000`)
- Ou use `NEXT_PUBLIC_QUIZ_PUBLIC_API_URL` com caminho completo
- Verifique CORS no backend
- Inspecione Network tab no DevTools para ver URL final sendo chamada

### Toasts não aparecem
- Verifique se `<Toaster />` está no layout.tsx

## 📄 Licença

Propriedade de Clínica Oncológica