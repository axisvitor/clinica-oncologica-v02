# Quiz Mensal - Interface

Interface standalone para questionário mensal de bem-estar, construída com Next.js 14 e integrada ao backend Hormonia.

## 📋 Funcionalidades

- **Acesso Seguro:** Token JWT único por paciente com expiração automática.
- **Questões Dinâmicas:** Suporte a múltipla escolha, escala numérica, texto e binário.
- **Experiência em Tempo Real:** Submissão imediata de respostas e barra de progresso.
- **Design Responsivo:** Otimizado para mobile-first (acesso via WhatsApp).

## 🚀 Como Usar

### Configuração (.env.local)

```env
# Recomendado: Apenas a Base URL (o cliente adiciona o sufixo /api/v2/monthly-quiz-public)
NEXT_PUBLIC_API_URL=http://localhost:8000

# Opcional: URL Explícita Completa
# NEXT_PUBLIC_QUIZ_PUBLIC_API_URL=http://localhost:8000/api/v2/monthly-quiz-public
```

### Instalação e Execução

```bash
cd quiz-mensal-interface
npm install
npm run dev
# Acesse: http://localhost:3000?token=SEU_TOKEN
```

## 🏗️ Estrutura do Projeto

- `app/`: Páginas e Layouts (App Router).
- `components/`: UI (shadcn/ui) e Lógica do Quiz.
- `lib/`: Cliente API e Gerenciador de Tokens.

## 📚 Documentação Relacionada

- **[Guia de Deploy](./deployment/):** Instruções para Railway e Vercel.
- **[Integração](./integration/):** Detalhes da comunicação com o backend.
- **[Segurança](./security/):** Análises de vulnerabilidade e correções.
